"""Separate-process development diagnostics. No metrics flow back to extraction."""

import argparse
from collections import Counter
from pathlib import Path

from evals.intelligence_g2.contracts import PACKAGE, ROOT, json_bytes, read_json
from evals.intelligence_g2.replay import OUTPUT_BASE, output_location, safe_path, write_payloads
from evals.intelligence_v1.exceptions import ContractError
from evals.intelligence_v1.hashing import sha256_bytes

from .contracts import EvidenceResult, PR3RunManifest, data, digest, fail, parse
from .load_run import load_grouping_run, selected_digest
from .reference_loader import load_references
from .replay import STREAMS, current_sources, print_error, run_sequence


def ratio(n, d):
    return dict(numerator=n, denominator=d, value=n / d if d else None,
                unavailable_reason=None if d else "zero_denominator")


def load_evidence_run(directory):
    directory = safe_path(directory, areas=(OUTPUT_BASE,))
    raw = safe_path(directory / "run_manifest.json", areas=(directory,)).read_bytes()
    manifest = parse(PR3RunManifest, read_json(raw), stage="evaluation")
    if manifest.runtime_source_sha256 != current_sources():
        fail("RUNTIME_CODE_MISMATCH", "evaluation", "runtime_source_sha256")
    expected_schemas = {p.relative_to(PACKAGE).as_posix(): sha256_bytes(p.read_bytes())
                        for p in (PACKAGE / "schema/v3").glob("*.schema.json")}
    if manifest.schema_sha256 != expected_schemas:
        fail("SHA_MISMATCH", "evaluation", "schema_sha256")
    if set(manifest.dependency_lock_sha256) != {"requirements.lock", "frontend/package-lock.json"}:
        fail("SHA_MISMATCH", "evaluation", "dependency_locks")
    if any(sha256_bytes((ROOT / p).read_bytes()) != h for p, h in manifest.dependency_lock_sha256.items()):
        fail("SHA_MISMATCH", "evaluation", "dependency_locks")
    names = {n + ".jsonl" for n in STREAMS} | {"claim_history.jsonl", "config_snapshot.json", "validation_report.json"}
    payloads = {}
    for entry in manifest.artifacts:
        if entry.path not in names or entry.path in payloads:
            fail("G2_PR3_PARENT_RUN_MISMATCH", "evaluation", "artifact_path")
        content = safe_path(directory / entry.path, areas=(directory,)).read_bytes()
        if (sha256_bytes(content) != entry.sha256 or len(content) != entry.byte_count
                or entry.record_count is not None and entry.record_count != len(content.splitlines())):
            fail("SHA_MISMATCH", "evaluation", "artifact", entry.path)
        payloads[entry.path] = content
    if set(payloads) != names:
        fail("SHA_MISMATCH", "evaluation", "artifacts")
    from .contracts import PR3Config
    config = parse(PR3Config, read_json(payloads["config_snapshot.json"]), stage="evaluation")
    if digest(config) != manifest.config_sha256:
        fail("CONFIG_SHA_MISMATCH", "evaluation", "config")
    parent_path = safe_path(ROOT / manifest.parent_run_path, areas=(OUTPUT_BASE,))
    _, inputs, groups, parent_config = load_grouping_run(parent_path,
        manifest_sha256=manifest.parent_manifest_sha256, through_step=manifest.through_step)
    if selected_digest(inputs, groups) != manifest.selected_input_sha256:
        fail("G2_PR3_PARENT_RUN_MISMATCH", "evaluation", "selected_input_sha256")
    expected = run_sequence(inputs, groups, grouping_config=parent_config, config=config)
    columns = {field: [read_json(line) for line in payloads[name + ".jsonl"].splitlines()]
               for name, field in STREAMS.items()}
    history = [read_json(line) for line in payloads["claim_history.jsonl"].splitlines()]
    report = read_json(payloads["validation_report.json"])
    if (report.get("ok") is not True or len(report["steps"]) != len(expected)
            or len(history) != len(expected) or any(len(v) != len(expected) for v in columns.values())):
        fail("G2_PR3_STATE_CHAIN_INVALID", "evaluation", "steps")
    results = []
    for i, step in enumerate(expected):
        cursor = data(step.cursor)
        if history[i]["cursor"] != cursor or any(v[i]["cursor"] != cursor for v in columns.values()):
            fail("G2_PR3_STATE_CHAIN_INVALID", "evaluation", "cursor")
        row = {field: rows[i][field] for field, rows in columns.items()}
        result = parse(EvidenceResult, {**row, "cursor": cursor, "transitions": history[i]["transitions"],
            "memberships": history[i]["memberships"], "validation": report["steps"][i]}, stage="evaluation")
        if result != step:
            fail("G2_PR3_STATUS_INVALID", "evaluation", "result")
        results.append(result)
    return manifest, tuple(results)


def compare(results, *, references, directions, quality=(), reference_sha256):
    by_step = {(r.cursor.timeline_id, r.cursor.step_id): r for r in results}
    refs = {(r.case_id, r.step_id): r for r in references}
    direction_refs = {(r["case_id"], r["step_id"]): r for r in directions}
    quality_refs = {(r["case_id"], r["step_id"]): r for r in quality}
    counts = Counter(tp=0, fp=0, fn=0, exact_type=0, exact_state=0, scored_steps=0, unscored_steps=0,
        locator_total=0, direction_total=0, conflict_mismatches=0, unknown_links=0)
    errors, case_scores, type_matrix, direction_matrix = [], [], {}, {}
    unique = set()
    for key, result in sorted(by_step.items()):
        reference = refs.get(key)
        counts["locator_total"] += len(result.citations)
        counts["unknown_links"] += sum(link.direction == "unknown" for link in result.links)
        unique.update((c.doc_version_id, c.paragraph_id, c.quote_sha256) for c in result.citations)
        if reference is None:
            counts["unscored_steps"] += 1
            continue
        counts["scored_steps"] += 1
        citations = {r.ref_id: r for r in result.citations}
        actual = {(c.doc_version_id, citations[c.evidence_ref_ids[0]].paragraph_id, c.statement): c for c in result.claims}
        expected = {(c.doc_version_id, c.paragraph_id, c.statement): c for c in reference.claims}
        common = set(actual) & set(expected)
        tp, fp, fn = len(common), len(set(actual) - set(expected)), len(set(expected) - set(actual))
        counts.update(tp=tp, fp=fp, fn=fn)
        case_scores.append(ratio(tp, tp + fp)["value"])
        assessments = {a.claim_key: a for a in result.assessments}
        for anchor in set(actual) | set(expected):
            c, ref = actual.get(anchor), expected.get(anchor)
            if c is None or ref is None:
                errors.append(dict(case_id=key[0], step_id=key[1], kind="FN" if c is None else "FP",
                    doc_version_id=anchor[0], paragraph_id=anchor[1], claim_key=c.claim_key if c else None,
                    root_cause="extraction_or_unsupported_grammar"))
                continue
            label = ref.claim_type + "->" + c.claim_type
            type_matrix[label] = type_matrix.get(label, 0) + 1
            counts["exact_type"] += c.claim_type == ref.claim_type
            counts["exact_state"] += assessments[c.claim_key].verification_state == ref.verification_state
            if c.claim_type != ref.claim_type or assessments[c.claim_key].verification_state != ref.verification_state:
                errors.append(dict(case_id=key[0], step_id=key[1], kind="classification",
                    claim_key=c.claim_key, root_cause="type_or_verification_state"))
        if len(result.conflicts) != reference.conflict_count:
            counts["conflict_mismatches"] += 1
            errors.append(dict(case_id=key[0], step_id=key[1], kind="conflict_count", root_cause="relation_rule"))
        dref = direction_refs.get(key)
        if dref is not None:
            claims = {c.claim_key: c.doc_version_id for c in result.claims}
            actual_links = {(claims[link.target_claim_key], claims[link.evidence_claim_key]): link.direction for link in result.links}
            expected_links = {(p["target"], p["evidence"]): p["direction"] for p in dref["links"]}
            for pair in set(actual_links) | set(expected_links):
                predicted, wanted = actual_links.get(pair, "missing"), expected_links.get(pair, "missing")
                label = wanted + "->" + predicted
                direction_matrix[label] = direction_matrix.get(label, 0) + 1
                counts["direction_total"] += 1
                if wanted != predicted:
                    errors.append(dict(case_id=key[0], step_id=key[1], kind="direction", pair=pair,
                        expected=wanted, predicted=predicted, root_cause="scope_or_relation_rule"))
        qref = quality_refs.get(key)
        if qref:
            by_doc = {c.doc_version_id: c for c in result.claims}
            for doc_id, fields in qref["scope_values"].items():
                claim = by_doc.get(doc_id)
                for field, wanted in fields.items():
                    actual_field = getattr(claim.scope, field) if claim else None
                    counts["scope_fields_total"] += 1
                    counts["scope_fields_retained"] += bool(actual_field and actual_field.normalized_value == wanted)
            for doc_id, wanted in qref["quantities"].items():
                claim = by_doc.get(doc_id)
                predicted = [q.value.normalized_value for q in claim.proposition.quantities] if claim else None
                counts["numeric_claims_total"] += 1
                counts["numeric_claims_faithful"] += predicted == wanted
                if predicted != wanted:
                    errors.append(dict(case_id=key[0], step_id=key[1], kind="numeric_fidelity",
                        doc_version_id=doc_id, root_cause="numeric_grounding"))
            gaps = {g.code for g in result.validation.coverage_gaps}
            counts["required_gaps"] += len(qref["required_gap_codes"])
            counts["detected_gaps"] += sum(g in gaps for g in qref["required_gap_codes"])
            if {t.kind for t in result.transitions} != ({qref["transition_kind"]} if qref["transition_kind"] else set()):
                errors.append(dict(case_id=key[0], step_id=key[1], kind="transition", root_cause="history_target"))
    tp, fp, fn = counts["tp"], counts["fp"], counts["fn"]
    scored = [v for v in case_scores if v is not None]
    return dict(acceptance_profile="ai_development", review_origin="ai_development", independent_validation=False,
        reference_sha256=reference_sha256, counts=dict(counts), extraction_precision=ratio(tp, tp + fp),
        extraction_recall=ratio(tp, tp + fn), extraction_f1=ratio(2 * tp, 2 * tp + fp + fn),
        type_accuracy=ratio(counts["exact_type"], tp), state_accuracy=ratio(counts["exact_state"], tp),
        locator_rate=ratio(counts["locator_total"], counts["locator_total"]),
        unique_paragraphs=len(unique), step_macro_precision=sum(scored) / len(scored) if scored else None,
        type_confusion_matrix=type_matrix, direction_confusion_matrix=direction_matrix or None,
        scope_field_retention=ratio(counts["scope_fields_retained"], counts["scope_fields_total"]),
        numeric_fidelity=ratio(counts["numeric_claims_faithful"], counts["numeric_claims_total"]),
        coverage_gap_recall=ratio(counts["detected_gaps"], counts["required_gaps"]),
        independent_semantic_support=dict(value=None, unavailable_reason="not_evaluated"),
        ai_semantic_support=dict(value=None, unavailable_reason="reference_comparison_is_not_independent_semantic_review"),
        model_calls=0, token_usage=0, model_cost=0), errors


def evaluate_run(directory, *, reference_manifest, reference_sha256, out):
    output = output_location(out)
    _, results = load_evidence_run(directory)  # Freeze/validate prediction before opening labels.
    refs, directions, quality, _ = load_references(reference_manifest, pin=reference_sha256)
    metrics, errors = compare(results, references=refs, directions=directions, quality=quality, reference_sha256=reference_sha256)
    enriched = [{**e, "reference_sha256": reference_sha256, "review_origin": "ai_development",
        "non_blind": True, "recommended_change": None, "new_counterexample": None, "retest": "not_run"} for e in errors]
    write_payloads(output, {"metrics.json": json_bytes(metrics),
        "errors.jsonl": b"".join(json_bytes(e) for e in enriched),
        "errors.md": ("# AI development errors\n\n" + "\n".join(str(e) for e in enriched) + "\n").encode()})
    return dict(ok=True, scored_steps=metrics["counts"]["scored_steps"], errors=len(errors))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--reference-manifest", type=Path, required=True)
    parser.add_argument("--reference-sha256", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = evaluate_run(args.run, reference_manifest=args.reference_manifest,
                              reference_sha256=args.reference_sha256, out=args.out)
    except ContractError as error:
        print_error(error)
        return 1
    except (OSError, KeyError, ValueError, TypeError):
        from evals.intelligence_g2.contracts import G2Error
        print_error(G2Error("EXPORT_IO_ERROR", stage="evaluation", field="run"))
        return 1
    print(json_bytes(result).decode().strip())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
