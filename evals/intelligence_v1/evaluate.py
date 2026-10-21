"""Post-prediction Recall@5/nDCG@5 and synthetic reference grouping diagnostics.

Full validation is mandatory here. This module never rewrites prediction files,
never labels missing relevance gold, and does not implement PR4 budget/revisit metrics.
"""

import argparse
import math
from itertools import combinations
from pathlib import Path

from .contracts import GoldLabel, RankedItem
from .exceptions import ContractError, DatasetValidationError
from .hashing import canonical_json, sha256_bytes
from .loader import json_value, load_bundle, load_step, parse_model, read_entry, read_records
from .oracle import reference_events, visible_reference_mapping
from .replay import _output_location, write_payloads
from .validate import validate_dataset


def ratio(numerator, denominator, reason):
    return {"numerator": numerator, "denominator": denominator,
            "value": numerator / denominator if denominator else None,
            "undefined_reason": None if denominator else reason}


def ranking_metrics(items, mapping, labels, *, k):
    visible_labels = {event: label for event, label in labels.items() if event in set(mapping.values())}
    focus = {event for event, label in visible_labels.items() if label["tier"] == "focus"}
    seen, dcg = set(), 0.0
    for position, item in enumerate(items[:k], 1):
        event = mapping.get(item["representative_doc_version_id"])
        if event in seen:
            continue  # The duplicate still consumed its displayed position.
        seen.add(event)
        grade = visible_labels.get(event, {}).get("graded_relevance", 0)
        dcg += (2**grade - 1) / math.log2(position + 1)
    grades = sorted((label["graded_relevance"] for label in visible_labels.values()), reverse=True)
    ideal = sum((2**grade - 1) / math.log2(i + 2) for i, grade in enumerate(grades[:k]))
    return {f"ImportantEventRecall@{k}": ratio(len(seen & focus), len(focus),
                                               "no_visible_gold_focus_events"),
            f"EventnDCG@{k}": ratio(dcg, ideal, "no_positive_gold_gain")}


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


def evaluate_run(run, manifest_path, *, manifest_sha256, out):
    data = load_bundle(manifest_path, manifest_sha256=manifest_sha256)
    validation = validate_dataset(manifest_path, strict=True)
    if validation.manifest_sha256 != manifest_sha256.lower():
        raise ContractError("MANIFEST_SHA_MISMATCH")
    run = Path(run).resolve()
    output = _output_location(out, data.root)
    if output.is_relative_to(run) or run.is_relative_to(output):
        raise ContractError("OUTPUT_PATH_INVALID")
    metadata = json_value((run/"run_metadata.json").read_bytes())
    if metadata["algorithm_id"] not in {"b0", "b1", "b2-predicted", "b2-oracle"}:
        raise ContractError("UNKNOWN_ALGORITHM")
    if metadata["oracle_mode"] and "oracle" not in output.name.casefold():
        raise ContractError("ORACLE_OUTPUT_PATH_REQUIRED")
    if metadata["dataset_manifest_sha256"] != manifest_sha256.lower():
        raise ContractError("RUN_INPUT_MISMATCH")
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
    events = reference_events(data)
    gold = []
    for entry in data.manifest.file_hashes:
        if entry.role == "gold":
            gold.extend(parse_model(GoldLabel, r) for r in read_records(read_entry(data.root, entry), entry))
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
        mapping = visible_reference_mapping(events, context.candidate_doc_version_ids,
                                             as_of=context.as_of)
        labels = [g for g in gold if (g.timeline_id, g.step_id, g.persona_version_id)
                  == (step.timeline_id, step.step_id, context.persona.persona_version_id)]
        eligible = {g.event_id: g.model_dump(mode="json") for g in labels
                    if g.adjudication_status in {"agreed", "adjudicated"}}
        metrics = ranking_metrics(row["ranked_items"], mapping, eligible, k=data.config.metric_k)
        if not eligible:
            reason = "gold_not_available" if not labels else "gold_pending_or_unresolved"
            for metric in metrics.values():
                metric.update(numerator=0, denominator=0, value=None, undefined_reason=reason)
        results.append({"timeline_id": step.timeline_id, "step_id": step.step_id,
            "metrics": metrics, "label_count": len(labels), "eligible_label_count": len(eligible),
            "unlabelled_visible_event_ids": sorted(set(mapping.values()) - eligible.keys()),
            "group_errors": group_errors(row["ranked_items"], mapping, context.candidate_doc_version_ids)})
    report = {"algorithm_id": metadata["algorithm_id"], "oracle_mode": metadata["oracle_mode"],
        "dataset_manifest_sha256": manifest_sha256.lower(),
        "predictions_sha256": metadata["predictions_sha256"], "metric_k": data.config.metric_k,
        "human_annotation": "not_confirmed", "semantic_support": "not_measured",
        "scope": "PR3_offline_development_diagnostics_no_budget_or_revisit_claim", "steps": results}
    write_payloads(output, {"metrics.json": (canonical_json(report) + "\n").encode(),
        "diagnostics.jsonl": "".join(canonical_json({"timeline_id": s["timeline_id"],
            "step_id": s["step_id"], **s["group_errors"]}) + "\n" for s in results).encode()})
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--manifest-sha256", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        report = evaluate_run(args.run, args.manifest, manifest_sha256=args.manifest_sha256, out=args.out)
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
