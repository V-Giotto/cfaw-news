"""Post-prediction same-pool development diagnostics, never an Oracle predictor."""

import argparse
from itertools import combinations
from pathlib import Path

from evals.intelligence_g2.contracts import data, digest, json_bytes, parse, read_json
from evals.intelligence_g2.replay import OUTPUT_BASE, output_location, safe_path, write_payloads
from evals.intelligence_v1.exceptions import ContractError
from evals.intelligence_v1.hashing import sha256_bytes

from .contracts import GroupingInput, GroupingResult, PR2Config, PR2RunManifest, fail
from .reference_loader import load_references
from .relations import MERGE_RELATIONS
from .replay import candidate_pool, current_source_hashes, print_error
from .validate_output import validate_output


def load_run(directory):
    directory = safe_path(directory, areas=(OUTPUT_BASE,))
    manifest = parse(PR2RunManifest, read_json((directory / "run_manifest.json").read_bytes()),
                     stage="evaluation")
    if manifest.runtime_source_sha256 != current_source_hashes():
        fail("RUNTIME_CODE_MISMATCH", "evaluation", "runtime_source_sha256")
    payloads = {}
    for artifact in manifest.artifacts:
        path = safe_path(directory / artifact.path, areas=(directory,))
        raw = path.read_bytes()
        if sha256_bytes(raw) != artifact.sha256 or len(raw) != artifact.byte_count:
            fail("SHA_MISMATCH", "evaluation", "artifact", artifact.path)
        if artifact.path in payloads:
            fail("DUPLICATE_ID", "evaluation", "artifacts")
        payloads[artifact.path] = raw
    for name in ("input_snapshots.jsonl", "results.jsonl", "config_snapshot.json"):
        if name not in payloads:
            fail("SHA_MISMATCH", "evaluation", name)
    config = parse(PR2Config, read_json(payloads["config_snapshot.json"]))
    if digest(config) != manifest.config_sha256:
        fail("CONFIG_SHA_MISMATCH", "evaluation", "config_snapshot")
    inputs = tuple(parse(GroupingInput, read_json(line))
                   for line in payloads["input_snapshots.jsonl"].splitlines())
    results = tuple(parse(GroupingResult, read_json(line))
                    for line in payloads["results.jsonl"].splitlines())
    if not inputs or len(inputs) != len(results):
        fail("G2_PR2_STATE_CHAIN_INVALID", "evaluation", "steps")
    prior = None
    for value, result in zip(inputs, results, strict=True):
        if value.previous_state != prior or value.strategy != manifest.strategy:
            fail("G2_PR2_STATE_CHAIN_INVALID", "evaluation", "previous_state")
        validate_output(result, value, config)
        prior = result.next_state
    pool = digest(candidate_pool(inputs))
    if pool != manifest.candidate_pool_sha256:
        fail("G2_PR2_COMPARISON_POOL_MISMATCH", "evaluation", "candidate_pool_sha256")
    return manifest, inputs, results


def ratio(numerator, denominator):
    return {"value": numerator / denominator if denominator else None,
            "unavailable_reason": None if denominator else "zero_denominator"}


def metrics(counts):
    tp, fp, fn = (counts[k] for k in ("tp", "fp", "fn"))
    return {"precision": ratio(tp, tp + fp), "recall": ratio(tp, tp + fn),
            "f1": ratio(2 * tp, 2 * tp + fp + fn)}


def owner(result):
    return {m: e.event_key for e in result.events for m in e.member_doc_version_ids}


def compare_loaded(runs, *, pairs, continuity, reference_sha256):
    if len(runs) != 3 or {m.strategy for m, _, _ in runs} != {"r0", "r1", "r2"}:
        fail("G2_PR2_COMPARISON_POOL_MISMATCH", "evaluation", "strategies")
    base = runs[0][0]
    if any((m.candidate_pool_sha256, m.input_manifest_sha256, m.config_sha256,
            m.runtime_source_sha256, m.schema_sha256, m.dependency_lock_sha256) != (
                base.candidate_pool_sha256, base.input_manifest_sha256, base.config_sha256,
                base.runtime_source_sha256, base.schema_sha256, base.dependency_lock_sha256)
           for m, _, _ in runs):
        fail("G2_PR2_COMPARISON_POOL_MISMATCH", "evaluation", "candidate_pool_or_runtime")
    report, errors = {}, []
    for manifest, inputs, results in sorted(runs, key=lambda r: r[0].strategy):
        strategy = manifest.strategy
        counts = dict.fromkeys(("tp", "fp", "fn", "tn", "reference_uncertain", "unscored",
                                "predicted_uncertain", "abstained_positive_fn",
                                "predicted_pair_count", "positive_pairs_blocked"), 0)
        step_rows, unique = [], {k: set() for k in ("tp", "fp", "fn", "tn")}
        confusion = {}
        by_step = {}
        for value, result in zip(inputs, results, strict=True):
            cursor = result.cursor
            by_step[(cursor.timeline_id, cursor.step_id)] = result
            members = owner(result)
            predicted = {(p.left_doc_version_id, p.right_doc_version_id): p for p in result.relations}
            refs = [p for p in pairs if (p.timeline_id, p.step_id) == (cursor.timeline_id, cursor.step_id)]
            per_step = dict.fromkeys(counts, 0)
            per_step["predicted_pair_count"] = len(predicted)
            per_step["predicted_uncertain"] = sum(p.predicted_relation == "uncertain"
                                                   for p in predicted.values())
            per_step["positive_pairs_blocked"] = sum(p.predicted_relation in MERGE_RELATIONS
                and members[p.left_doc_version_id] != members[p.right_doc_version_id]
                for p in predicted.values())
            comparable = set()
            for ref in refs:
                if ref.as_of != cursor.as_of or not {ref.left_doc_version_id, ref.right_doc_version_id} <= members.keys():
                    fail("G2_PR2_REFERENCE_CONFLICT", "evaluation", "reference_candidates", ref.case_id)
                pair = (ref.left_doc_version_id, ref.right_doc_version_id)
                comparable.add(pair)
                decision = predicted.get(pair)
                if decision:
                    cell = ref.relation + " -> " + decision.predicted_relation
                    confusion[cell] = confusion.get(cell, 0) + 1
                if ref.relation == "uncertain":
                    per_step["reference_uncertain"] += 1
                    continue
                actual = members[pair[0]] == members[pair[1]]
                positive = ref.relation in MERGE_RELATIONS
                label = "tp" if positive and actual else "fn" if positive else "fp" if actual else "tn"
                per_step[label] += 1
                unique[label].add((cursor.timeline_id, *pair))
                if label == "fn" and decision and decision.predicted_relation == "uncertain":
                    per_step["abstained_positive_fn"] += 1
                if label in {"fp", "fn"}:
                    features = [f for f in result.features if f.doc_version_id in pair]
                    errors.append({"case_id": ref.case_id, "timeline_id": cursor.timeline_id,
                        "step_id": cursor.step_id, "as_of": data(cursor)["as_of"], "strategy": strategy,
                        "input_sha256": result.input_sha256, "config_sha256": manifest.config_sha256,
                        "code_sha256": digest(manifest.runtime_source_sha256),
                        "reference_sha256": reference_sha256, "pair": pair, "error": label,
                        "predicted_relation": decision.predicted_relation if decision else None,
                        "reference_relation": ref.relation, "predicted_groups": [
                            list(e.member_doc_version_ids) for e in result.events if set(pair) & set(e.member_doc_version_ids)],
                        "rule_id": decision.rule_id if decision else "fixed_g1_r0",
                        "feature_refs": [data(f) for f in features],
                        "cannot_link": list(decision.cannot_link) if decision else [],
                        "blocked_merges": [data(b) for b in result.partition.blocked_merges],
                        "previous_event_keys": [e.event_key for e in value.previous_state.registry]
                            if value.previous_state else [],
                        "current_events": [data(e) for e in result.events if set(pair) & set(e.member_doc_version_ids)],
                        "transition_ids": [t.transition_id for t in result.transitions],
                        "root_cause": decision.evidence_reasons[0] if decision else "fixed_r0_grouping",
                        "impact": "false_merge" if label == "fp" else "missed_merge",
                        "suggested_rule_change": None, "added_counterexample": None, "retest_result": None,
                        "label_origin": "synthetic_fixture", "review_origin": "ai_development",
                        "non_blind": True})
            per_step["unscored"] = len(list(combinations(members, 2))) - len(comparable)
            for k in counts:
                counts[k] += per_step[k]
            step_rows.append({"timeline_id": cursor.timeline_id, "step_id": cursor.step_id,
                "counts": per_step, **metrics(per_step),
                "member_retention": ratio(len(members), len(value.replay_input.visible_documents)),
                "representative_coverage": ratio(sum(len(v.source_pointers) for v in result.views), len(members)),
                "no_body_count": sum(not d.candidate.paragraphs for d in value.replay_input.visible_documents)})
        stable, eligible, unexplained = 0, 0, 0
        for reference in continuity:
            a = by_step.get((reference.timeline_id, reference.from_step_id))
            b = by_step.get((reference.timeline_id, reference.to_step_id))
            if a is None or b is None:
                continue
            oa, ob = owner(a), owner(b)
            if reference.from_doc_version_id not in oa or reference.to_doc_version_id not in ob:
                fail("G2_PR2_REFERENCE_CONFLICT", "evaluation", "continuity", reference.case_id)
            same = oa[reference.from_doc_version_id] == ob[reference.to_doc_version_id]
            eligible += 1
            stable += same == (reference.expected == "same")
            reachable = {oa[reference.from_doc_version_id]}
            for intermediate in results:
                if a.cursor.as_of < intermediate.cursor.as_of <= b.cursor.as_of:
                    for transition in intermediate.transitions:
                        if transition.kind in {"merge", "split", "complex"} and (
                                reachable & set(transition.from_keys)):
                            reachable.update(transition.to_keys)
            unexplained += (not same and reference.expected == "same"
                            and ob[reference.to_doc_version_id] not in reachable)
        macros = {}
        for metric in ("precision", "recall", "f1"):
            values = [r[metric]["value"] for r in step_rows if r[metric]["value"] is not None]
            macros[metric] = sum(values) / len(values) if values else None
        report[strategy] = {"counts": counts, **metrics(counts), "step_macro": macros,
            "unique_pair_counts": {k: len(v) for k, v in unique.items()},
            "confusion_matrix": confusion if strategy != "r0" else None,
            "abstention_rate": ratio(counts["predicted_uncertain"], counts["predicted_pair_count"])
                if strategy != "r0" else None,
            "blocked_positive_pair_count": counts["positive_pairs_blocked"] if strategy != "r0" else None,
            "stability": ratio(stable, eligible), "unexplained_key_changes": unexplained,
            "transition_counts": {kind: sum(t.kind == kind for r in results for t in r.transitions)
                                  for kind in ("merge", "split", "complex")},
            "steps": step_rows}
    return {"scope": "synthetic_ai_development_diagnostic", "review_origin": "ai_development",
            "independent_validation": False, "strategies": report}, tuple(errors)


def evaluate_runs(directories, *, reference_manifest, reference_sha256, out):
    output = output_location(out)
    # Freeze and verify prediction artifacts before touching references.
    runs = tuple(load_run(path) for path in directories)
    reference, pairs, continuity = load_references(reference_manifest, pin=reference_sha256)
    if any(m.input_manifest_sha256 not in reference.prediction_manifest_sha256 for m, _, _ in runs):
        fail("G2_PR2_REFERENCE_CONFLICT", "evaluation", "prediction_manifest_sha256")
    report, errors = compare_loaded(runs, pairs=pairs, continuity=continuity,
                                    reference_sha256=reference_sha256)
    table = ["| case | strategy | step | pair | error | rule |", "|---|---|---|---|---|---|"]
    table += ["| " + " | ".join(str(row[k]).replace("|", "\\|").replace("\n", " ")
              for k in ("case_id", "strategy", "step_id", "pair", "error", "rule_id")) + " |"
              for row in errors]
    payloads = {"metrics.json": json_bytes(report), "errors.jsonl": b"".join(json_bytes(e) for e in errors),
        "errors.md": ("\n".join(table) + "\n").encode(),
        "evaluation_manifest.json": json_bytes({"reference_manifest_sha256": reference_sha256,
            "runs": [{"strategy": m.strategy, "manifest_sha256": digest(m)} for m, _, _ in runs]})}
    write_payloads(output, payloads)
    return {"ok": True, "error_observations": len(errors), "scope": report["scope"]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", nargs=3, type=Path, required=True)
    parser.add_argument("--reference-manifest", type=Path, required=True)
    parser.add_argument("--reference-manifest-sha256", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = evaluate_runs(args.runs, reference_manifest=args.reference_manifest,
            reference_sha256=args.reference_manifest_sha256, out=args.out)
    except ContractError as error:
        print_error(error)
        return 1
    except (OSError, ValueError, TypeError, KeyError, RuntimeError):
        from evals.intelligence_g2.contracts import G2Error

        print_error(G2Error("EXPORT_IO_ERROR", stage="export"))
        return 1
    print(json_bytes(result).decode().strip())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
