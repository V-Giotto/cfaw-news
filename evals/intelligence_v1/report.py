"""Verified local report for PR4 runs; no prediction writes or network access."""

import argparse
from pathlib import Path

from .exceptions import ContractError, DatasetValidationError
from .hashing import canonical_json, sha256_bytes
from .loader import json_value, load_bundle
from .metrics import aggregate_metrics
from .replay import _output_location, write_payloads
from .validate import validate_dataset


def checked_file(path, digest):
    raw = path.read_bytes()
    if sha256_bytes(raw) != digest:
        raise ContractError("SHA_MISMATCH", field=path.name)
    return raw


def comparison_inputs(cohort):
    # Context hashes include the Persona version/preferences and delivery history.
    # Match effective budgets per step, including runs without a budget override.
    return {(step["timeline_id"], step["step_id"]): (
        step["budget_seconds"], step["candidate_sha256"], step["context_sha256"]
    ) for step in cohort["steps"]}


def build_report(runs, manifest_path, *, manifest_sha256, out):
    data = load_bundle(manifest_path, manifest_sha256=manifest_sha256)
    validation = validate_dataset(manifest_path)
    if validation.manifest_sha256 != manifest_sha256.lower():
        raise ContractError("MANIFEST_SHA_MISMATCH")
    runs = Path(runs).resolve()
    output = _output_location(out, data.root)
    if output.is_relative_to(runs) or runs.is_relative_to(output):
        raise ContractError("OUTPUT_PATH_INVALID")
    cohorts, input_checks, performance = {}, {}, {}
    for path in sorted(runs.rglob("evaluation_metadata.json")):
        if not path.resolve().is_relative_to(runs):
            raise ContractError("RUN_INPUT_MISMATCH")
        identity = json_value(path.read_bytes())
        report = json_value(checked_file(path.parent/"metrics.json", identity["metrics_sha256"]))
        checked_file(path.parent/"diagnostics.jsonl", identity["diagnostics_sha256"])
        if (report["dataset_manifest_sha256"] != manifest_sha256.lower()
                or identity["dataset_manifest_sha256"] != manifest_sha256.lower()
                or report["baseline_config_sha256"] != data.manifest.baseline_config_sha256
                or report["label_source"] != identity["label_source"]):
            raise ContractError("RUN_INPUT_MISMATCH")
        run = Path(identity["run_path"]).resolve()
        if not run.is_relative_to(runs):
            raise ContractError("RUN_INPUT_MISMATCH")
        metadata = json_value((run/"run_metadata.json").read_bytes())
        checked_file(run/"predictions.jsonl", report["predictions_sha256"])
        checked_file(run/"input_snapshot.json", report["input_snapshot_sha256"])
        config_snapshot = json_value(checked_file(run/"baseline_config.json",
                                                  metadata["config_snapshot_sha256"]))
        if (config_snapshot != data.config.model_dump(mode="json")
                or metadata["dataset_manifest_sha256"] != manifest_sha256.lower()
                or metadata["predictions_sha256"] != report["predictions_sha256"]
                or metadata["input_snapshot_sha256"] != report["input_snapshot_sha256"]
                or metadata["experiment"] != report["experiment"]
                or metadata["algorithm_id"] != report["algorithm_id"]
                or metadata["oracle_mode"] != report["oracle_mode"]
                or report["oracle_mode"] != (report["algorithm_id"] == "b2-oracle")):
            raise ContractError("RUN_INPUT_MISMATCH")
        key = canonical_json([report["algorithm_id"], report["experiment"], report["label_source"]])
        cohort = cohorts.setdefault(key, {"algorithm_id": report["algorithm_id"],
            "experiment": report["experiment"], "label_source": report["label_source"],
            "oracle_mode": report["oracle_mode"], "steps": {}, "replicate_count": 0})
        cohort["replicate_count"] += 1
        for step in report["steps"]:
            step_key = step["timeline_id"]+"/"+step["step_id"]
            previous = cohort["steps"].setdefault(step_key, step)
            if previous != step:
                raise ContractError("NONDETERMINISTIC_METRICS")
            input_key = (step_key, step["budget_seconds"])
            inputs = (step["candidate_sha256"], step["context_sha256"])
            if input_checks.setdefault(input_key, inputs) != inputs:
                raise ContractError("CANDIDATE_POOL_MISMATCH")
        performance[str(run.relative_to(runs))] = {
            "execution_ms": metadata["execution_ms"], "steps": metadata["step_performance"],
            "model_tokens": metadata["model_tokens"], "model_cost": metadata["model_cost"]}
    if not cohorts:
        raise ContractError("REFERENCE_NOT_FOUND", field="evaluation_runs")
    summaries = []
    for _, cohort in sorted(cohorts.items()):
        steps = [s for _, s in sorted(cohort["steps"].items())]
        metrics = sorted({name for s in steps for name in s["metrics"]})
        cohort["aggregate"] = {name: aggregate_metrics([s["metrics"][name] for s in steps
                                                        if name in s["metrics"]]) for name in metrics}
        families = sorted({f for s in steps for f in s["family_ids"]})
        cohort["by_family"] = {f: {name: aggregate_metrics([s["metrics"][name] for s in steps
            if f in s["family_ids"] and name in s["metrics"]]) for name in metrics} for f in families}
        cohort["steps"] = steps
        summaries.append(cohort)
    comparisons = []
    for cohort in summaries:
        if cohort["algorithm_id"] not in {"b3", "b4"}:
            continue
        baseline = next((b for b in summaries if b["algorithm_id"] == "b1"
            and b["label_source"] == cohort["label_source"]
            and b["experiment"]["budget_seconds_override"] == cohort["experiment"]["budget_seconds_override"]
            and b["experiment"]["half_life_days"] == 7), None)
        if baseline is None:
            continue
        if comparison_inputs(cohort) != comparison_inputs(baseline):
            raise ContractError("COMPARISON_INPUT_MISMATCH")
        for name in cohort["aggregate"]:
            value = cohort["aggregate"][name]["macro"]
            base = baseline["aggregate"].get(name, {}).get("macro")
            comparisons.append({"algorithm_id": cohort["algorithm_id"],
                "label_source": cohort["label_source"], "experiment": cohort["experiment"],
                "metric": name, "delta_vs_B1": value-base if value is not None and base is not None else None})
    result = {"dataset_manifest_sha256": manifest_sha256.lower(),
        "dataset_revision": data.manifest.dataset_revision, "human_annotation": "not_confirmed",
        "semantic_support": "not_measured", "model_tokens": 0, "model_cost": 0,
        "cohorts": summaries, "comparisons": comparisons,
        "limitations": ["Synthetic development data only; no real-world efficacy claim.",
            "New text is a proxy, not a meaningful update/correction prediction.",
            "Exposure does not establish comprehension; gaps are unknown.",
            "Repeated runs are deduplicated before aggregation; families remain correlated.",
            "Zero or negative improvement is valid; frozen references must not be tuned."]}
    lines = ["# G1-PR4 offline technical report", "", f"Manifest: `{manifest_sha256.lower()}`", "",
        "Human annotation: **not_confirmed**; semantic support: **not_measured**.",
        "B2-oracle is a separate synthetic reference diagnostic.", "",
        "| Algorithm | Label source | Budget | Half-life | Step | Cards | Estimated seconds | Gaps | Focus misses |",
        "|---|---|---:|---:|---|---:|---:|---:|---|"]
    for cohort in summaries:
        for step in cohort["steps"]:
            lines.append(f"| {cohort['algorithm_id']} | {cohort['label_source']} | {step['budget_seconds']} | "
                f"{cohort['experiment']['half_life_days']} | {step['timeline_id']}/{step['step_id']} | "
                f"{step['presented_item_count']} | {step['estimated_read_seconds']} | "
                f"{step['coverage']['coverage_gap_count']} | {', '.join(step['diagnostics']['missed_focus_event_ids']) or '-'} |")
    lines += ["", "## D8 evidence, repetition and grouping diagnostics", ""]
    for cohort in summaries:
        for step in cohort["steps"]:
            if step["step_id"] != "D8":
                continue
            lines += [f"### {cohort['algorithm_id']} / {cohort['label_source']} / {step['timeline_id']} / "
                f"{step['budget_seconds']}s / half-life {cohort['experiment']['half_life_days']}", "",
                "| Rank | Representative | Score | Text proxy | Exposure penalty |",
                "|---:|---|---:|---|---:|"]
            for item in step["top_k"]:
                components = item["score_components"]
                lines.append(f"| {item['rank']} | {item['representative_doc_version_id']} | "
                    f"{item['score']} | {components.get('text_delta') or '-'} | "
                    f"{components.get('penalty', 0)} |")
            diag, groups = step["diagnostics"], step["group_errors"]
            lines += ["", "Supporting evidence in presented cards: `"+canonical_json(
                diag["supporting_evidence_presented"])+"`.",
                "Miss reasons: `"+canonical_json(diag["miss_reasons"])+"`.",
                "Repeated reference events: `"+canonical_json(diag["repeated_reference_event_ids"])+"`.",
                f"Grouping FP/FN pairs: {len(groups['false_positive_pairs'])}/"
                f"{len(groups['false_negative_pairs'])}; unknown source windows: "
                f"{step['coverage']['coverage_gap_count']}; sources without a window: "
                f"{', '.join(step['uncovered_visible_source_ids']) or '-' }.", ""]
    lines += ["## B1 comparison", "", "Zero or negative deltas are valid research outcomes.",
        "", "| Algorithm | Label source | Budget override | Half-life | Metric | Delta vs B1 |",
        "|---|---|---:|---:|---|---:|"]
    for comparison in comparisons:
        if (comparison['metric'].startswith('ImportantEventRecall@budget')
                or comparison['metric'] == 'DuplicateExposureRate'):
            exp = comparison['experiment']
            lines.append(f"| {comparison['algorithm_id']} | {comparison['label_source']} | "
                f"{exp['budget_seconds_override']} | {exp['half_life_days']} | "
                f"{comparison['metric']} | {comparison['delta_vs_B1']} |")
    lines += ["", "Full metrics, numerator/denominator, null reasons and family summaries: comparison.json.",
        "Formal material-change/correction/withdrawal predictions are not emitted; their metrics remain null.",
        "", "## Limits", ""]
    lines += ["- "+line for line in result["limitations"]]
    lines += ["", "Measured latency is in performance.json; it is excluded from deterministic metrics.",
              "Estimated reading seconds are proxies, not measured time savings.", ""]
    write_payloads(output, {"comparison.json": (canonical_json(result)+"\n").encode(),
        "report.md": "\n".join(lines).encode(),
        "performance.json": (canonical_json(performance)+"\n").encode()})
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--manifest-sha256", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = build_report(args.runs, args.manifest, manifest_sha256=args.manifest_sha256, out=args.out)
    except DatasetValidationError as error:
        print(canonical_json(error.report.to_dict()))
        return 1
    except ContractError as error:
        print(canonical_json({"ok": False, "code": error.code, "field": error.field}))
        return 1
    except (OSError, ValueError, KeyError, TypeError):
        print(canonical_json({"ok": False, "code": "REPORT_IO_ERROR"}))
        return 1
    print(canonical_json({"ok": True, "cohort_count": len(result["cohorts"])}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
