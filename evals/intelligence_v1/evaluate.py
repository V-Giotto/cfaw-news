"""Post-prediction evaluation; human gold and authored fixture expectations stay separate."""

import argparse
from itertools import combinations
from pathlib import Path

from .annotations import audit_bundle, gold_key
from .budget import apply_budget
from .contracts import BudgetPolicy, GoldLabel, MetricReport, RankedItem, SyntheticExpectation
from .exceptions import ContractError, DatasetValidationError
from .hashing import canonical_json, sha256_bytes
from .loader import json_value, load_bundle, load_step, parse_model, read_entry, read_records
from .metrics import aggregate_metrics, coverage_gaps, ratio, step_metrics, unavailable
from .metrics import ranking_metrics as ranking_metrics
from .oracle import reference_events, visible_reference_mapping
from .replay import _output_location, write_payloads
from .validate import validate_dataset


def group_errors(items, mapping, candidate_ids):
    assigned = {key: i for i, item in enumerate(items) for key in item["doc_version_ids"]}
    fp, fn, tp, tn = [], [], 0, 0
    for a, b in combinations(sorted(mapping), 2):
        predicted = assigned[a] == assigned[b]
        reference = mapping[a] == mapping[b]
        if predicted and not reference:
            fp.append([a, b])
        elif reference and not predicted:
            fn.append([a, b])
        elif predicted:
            tp += 1
        else:
            tn += 1
    return {"true_positive_pairs": tp, "true_negative_pairs": tn,
            "false_positive_pairs": fp, "false_negative_pairs": fn,
            "comparable_pair_count": tp + tn + len(fp) + len(fn),
            "unmapped_doc_version_ids": sorted(set(candidate_ids) - mapping.keys()),
            "scope": "synthetic_reference_diagnostic_not_independent_human_gold"}


def evaluate_run(run, manifest_path, *, manifest_sha256, out, label_source="gold"):
    if label_source not in {"gold", "synthetic-fixture"}:
        raise ContractError("UNKNOWN_LABEL_SOURCE")
    data = load_bundle(manifest_path, manifest_sha256=manifest_sha256)
    validation = validate_dataset(manifest_path, strict=True)
    if validation.manifest_sha256 != manifest_sha256.lower():
        raise ContractError("MANIFEST_SHA_MISMATCH")
    run = Path(run).resolve()
    output = _output_location(out, data.root)
    if output.is_relative_to(run) or run.is_relative_to(output):
        raise ContractError("OUTPUT_PATH_INVALID")
    metadata = json_value((run/"run_metadata.json").read_bytes())
    if metadata["algorithm_id"] not in {"b0", "b1", "b2-predicted", "b2-oracle", "b3", "b4"}:
        raise ContractError("UNKNOWN_ALGORITHM")
    if metadata["oracle_mode"] and "oracle" not in output.name.casefold():
        raise ContractError("ORACLE_OUTPUT_PATH_REQUIRED")
    if metadata["dataset_manifest_sha256"] != manifest_sha256.lower():
        raise ContractError("RUN_INPUT_MISMATCH")
    experiment = metadata["experiment"]
    override, half = experiment["budget_seconds_override"], experiment["half_life_days"]
    if (type(half) is not int or half not in data.config.registered_half_lives
            or (override is not None and (type(override) is not int
                or override not in data.config.registered_budgets))):
        raise ContractError("UNREGISTERED_EXPERIMENT")
    payloads = {}
    for name, field in (("predictions.jsonl", "predictions_sha256"),
                        ("input_snapshot.json", "input_snapshot_sha256"),
                        ("baseline_config.json", "config_snapshot_sha256")):
        raw = (run/name).read_bytes()
        if sha256_bytes(raw) != metadata[field]:
            raise ContractError("SHA_MISMATCH", field=name)
        payloads[name] = raw
    if json_value(payloads["baseline_config.json"]) != data.config.model_dump(mode="json"):
        raise ContractError("RUN_INPUT_MISMATCH")
    predictions = [json_value(line) for line in payloads["predictions.jsonl"].splitlines()]
    snapshots = json_value(payloads["input_snapshot.json"])["steps"]
    if len(predictions) != len(snapshots):
        raise ContractError("RUN_INPUT_MISMATCH")
    expected_steps = sorted((s for s in data.steps
        if (metadata["split"] is None or s.split == metadata["split"])
        and (metadata["timeline_id"] is None or s.timeline_id == metadata["timeline_id"])
        and (metadata["step_id"] is None or s.step_id == metadata["step_id"])),
        key=lambda s: (s.timeline_id, s.as_of, s.step_id))
    if len(expected_steps) != len(predictions):
        raise ContractError("RUN_INPUT_MISMATCH")
    if half != data.config.half_life_days and any(s.split != "dev" for s in expected_steps):
        raise ContractError("SENSITIVITY_REQUIRES_DEV")
    events = reference_events(data)
    annotation_audit = audit_bundle(data)
    confirmed_keys = {tuple(k) for k in annotation_audit["eligible_gold_keys"]}
    gold = []
    selected_role = "gold" if label_source == "gold" else "fixture_expectations"
    label_model = GoldLabel if label_source == "gold" else SyntheticExpectation
    for entry in data.manifest.file_hashes:
        if entry.role == selected_role:
            gold.extend(parse_model(label_model, r) for r in read_records(
                read_entry(data.root, entry), entry))
    results = []
    for row, snapshot, step in zip(predictions, snapshots, expected_steps, strict=True):
        context, candidates = load_step(data, timeline_id=step.timeline_id,
                                        step_id=step.step_id, config=data.config)
        expected_snapshot = {"context": context.model_dump(mode="json"),
                             "candidates": [d.model_dump(mode="json") for d in candidates]}
        if snapshot != expected_snapshot:
            raise ContractError("RUN_INPUT_MISMATCH")
        oracle = row["algorithm_id"] == "b2-oracle"
        if (row["algorithm_id"] != metadata["algorithm_id"] or row["oracle_mode"] != oracle
                or metadata["oracle_mode"] != oracle
                or row["timeline_id"] != step.timeline_id or row["step_id"] != step.step_id
                or row["as_of"] != context.model_dump(mode="json")["as_of"]
                or row["candidate_doc_count"] != len(candidates)
                or row["candidate_sha256"] != sha256_bytes(canonical_json(snapshot["candidates"]).encode())
                or row["context_sha256"] != sha256_bytes(canonical_json(snapshot["context"]).encode())):
            raise ContractError("RUN_INPUT_MISMATCH")
        ranked = [parse_model(RankedItem, r) for r in row["ranked_items"]]
        members = [key for r in ranked for key in r.doc_version_ids]
        if (len(set(members)) != len(members)
                or set(members) != set(context.candidate_doc_version_ids)
                or [r.rank for r in ranked] != list(range(1, len(ranked) + 1))):
            raise ContractError("GROUP_MEMBERS_INVALID")
        if any((r.predicted_event_id or "").startswith("oracle:") != oracle
               or ("oracle_reference" in r.merge_reasons) != oracle for r in ranked):
            raise ContractError("ORACLE_MARKER_INVALID")
        if row["algorithm_id"] in {"b0", "b1"} and any(
                len(r.doc_version_ids) != 1 or r.predicted_event_id is not None for r in ranked):
            raise ContractError("GROUP_MEMBERS_INVALID")
        presentation = apply_budget(ranked, BudgetPolicy(max_read_seconds=(
            context.attention_budget_seconds if override is None else override)))
        if row["presentation"] != presentation.model_dump(mode="json"):
            raise ContractError("BUDGET_PRESENTATION_MISMATCH")
        if row["algorithm_id"] in {"b3", "b4"} and any(
                r.score_components.half_life_days != half for r in ranked):
            raise ContractError("RUN_INPUT_MISMATCH")
        mapping = visible_reference_mapping(events, context.candidate_doc_version_ids,
                                             as_of=context.as_of)
        labels = [g for g in gold if (g.timeline_id, g.step_id, g.persona_version_id)
                  == (step.timeline_id, step.step_id, context.persona.persona_version_id)]
        eligible = {g.event_id: g.model_dump(mode="json") for g in labels if
                    label_source == "synthetic-fixture" or (gold_key(g) in confirmed_keys
                        and g.adjudication_status in {"agreed", "adjudicated"})}
        historic = visible_reference_mapping(events, tuple(m.doc_version_id
            for h in context.delivery_history for m in h.members), as_of=context.as_of)
        metrics, diagnostics = step_metrics(row, context, mapping, eligible,
            k=data.config.metric_k, evidence_times={d.doc_version_id: d.available_at
                                                   for d in data.documents},
            historical_mapping=historic)
        errors = group_errors(row["ranked_items"], mapping, context.candidate_doc_version_ids)
        tp, fp, fn = (errors["true_positive_pairs"], len(errors["false_positive_pairs"]),
                      len(errors["false_negative_pairs"]))
        metrics.update({"EventPairPrecision": ratio(tp, tp+fp, "no_predicted_positive_pairs"),
            "EventPairRecall": ratio(tp, tp+fn, "no_reference_positive_pairs"),
            "EventPairF1": ratio(2*tp, 2*tp+fp+fn, "no_positive_pairs")})
        if not eligible:
            reason = ("synthetic_expectation_not_available" if label_source == "synthetic-fixture"
                      else "gold_not_available" if not labels else "gold_pending_or_unresolved")
            for name in metrics:
                if (name.startswith(("Important", "EventnDCG", "Revisit", "NewText"))
                        or name == "RepeatedNoChangeRate"):
                    metrics[name] = unavailable(reason)
        results.append({"timeline_id": step.timeline_id, "step_id": step.step_id,
            "as_of": context.model_dump(mode="json")["as_of"],
            "persona_version_id": context.persona.persona_version_id,
            "visible_source_count": len({d.source_id for d in candidates}),
            "visible_reference_event_count": len(set(mapping.values())),
            "reference_focus_count": sum(g["tier"] == "focus" for g in eligible.values()) if eligible else None,
            "metrics": metrics, "label_count": len(labels), "eligible_label_count": len(eligible),
            "label_provenance_uris": sorted({g.provenance_uri or "unknown" for g in labels}),
            "family_ids": list(step.family_scope_ids), "candidate_sha256": row["candidate_sha256"],
            "context_sha256": row["context_sha256"], "candidate_doc_count": len(candidates),
            "predicted_item_count": len(ranked), "presented_item_count": len(presentation.presented_items),
            "budget_seconds": presentation.budget_seconds,
            "estimated_read_seconds": presentation.used_read_seconds,
            "top_k": row["ranked_items"][:data.config.metric_k],
            "presented_items": row["presentation"]["presented_items"],
            "coverage": coverage_gaps(context), "diagnostics": diagnostics,
            "coverage_scope": "known_source_windows_only",
            "uncovered_visible_source_ids": sorted({d.source_id for d in candidates}
                - {w.source_id for w in context.source_coverage}),
            "unlabelled_visible_event_ids": sorted(set(mapping.values()) - eligible.keys()),
            "group_errors": errors})
    report = {"algorithm_id": metadata["algorithm_id"], "oracle_mode": metadata["oracle_mode"],
        "dataset_manifest_sha256": manifest_sha256.lower(),
        "predictions_sha256": metadata["predictions_sha256"], "metric_k": data.config.metric_k,
        "input_snapshot_sha256": metadata["input_snapshot_sha256"],
        "baseline_config_sha256": data.manifest.baseline_config_sha256,
        "dataset_revision": data.manifest.dataset_revision, "experiment": experiment,
        "label_source": label_source, "model_tokens": 0, "model_cost": 0,
        "human_annotation": annotation_audit["human_annotation"], "semantic_support": "not_measured",
        "annotation_audit": annotation_audit,
        "scope": "PR5_offline_development_evaluation_not_real_world_evidence", "steps": results,
        "aggregate": {name: aggregate_metrics([s["metrics"][name] for s in results])
                      for name in sorted({k for s in results for k in s["metrics"]})
                      if all(name in s["metrics"] for s in results)}}
    parse_model(MetricReport, {k: report[k] for k in MetricReport.model_fields})
    payloads = {"metrics.json": (canonical_json(report) + "\n").encode(),
        "diagnostics.jsonl": "".join(canonical_json({"timeline_id": s["timeline_id"],
            "step_id": s["step_id"], **s["group_errors"], **s["diagnostics"],
            "coverage": s["coverage"]}) + "\n" for s in results).encode()}
    payloads["evaluation_metadata.json"] = (canonical_json({"run_path": str(run),
        "dataset_manifest_sha256": manifest_sha256.lower(), "label_source": label_source,
        "metrics_sha256": sha256_bytes(payloads["metrics.json"]),
        "diagnostics_sha256": sha256_bytes(payloads["diagnostics.jsonl"])})+"\n").encode()
    write_payloads(output, payloads)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--manifest-sha256", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--label-source", choices=["gold", "synthetic-fixture"], default="gold")
    args = parser.parse_args(argv)
    try:
        report = evaluate_run(args.run, args.manifest, manifest_sha256=args.manifest_sha256,
                              out=args.out, label_source=args.label_source)
    except DatasetValidationError as error:
        print(canonical_json(error.report.to_dict()))
        return 1
    except ContractError as error:
        print(canonical_json({"ok": False, "errors": [{"code": error.code, "field": error.field}]}))
        return 1
    except (OSError, ValueError, KeyError, TypeError):
        print(canonical_json({"ok": False, "errors": [{"code": "EVALUATION_IO_ERROR"}]}))
        return 1
    print(canonical_json({"ok": True, "algorithm_id": report["algorithm_id"],
                          "step_count": len(report["steps"])}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
