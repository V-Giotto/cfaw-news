import json

import pytest
from test_replay_end_to_end import run

from evals.intelligence_v1.hashing import sha256_bytes


def test_separate_synthetic_labels_budget_metrics_and_no_false_human_claim(bundle, tmp_path):
    from evals.intelligence_v1.evaluate import evaluate_run

    output = tmp_path/"b4"
    run(bundle, output, "b4", timeline_id="REVISIT-7D", budget_seconds=180)
    manifest = bundle/"manifests/dataset_manifest.json"
    raw = (output/"predictions.jsonl").read_bytes()
    report = evaluate_run(output, manifest, manifest_sha256=sha256_bytes(manifest.read_bytes()),
        label_source="synthetic-fixture", out=tmp_path/"fixture-evaluation")
    d8 = next(s for s in report["steps"] if s["step_id"] == "D8")
    assert d8["metrics"]["ImportantEventRecall@budget:180s"]["denominator"] == 2
    assert d8["metrics"]["MaterialChange.recall"]["undefined_reason"] == "prediction_not_emitted"
    assert d8["metrics"]["EvidenceSupportPrecision"]["undefined_reason"] == "not_measured"
    assert report["label_source"] == "synthetic-fixture"
    assert report["human_annotation"] == "not_confirmed"
    assert (output/"predictions.jsonl").read_bytes() == raw
    gold = evaluate_run(output, manifest, manifest_sha256=sha256_bytes(manifest.read_bytes()),
        out=tmp_path/"gold-evaluation")
    assert all(s["metrics"]["ImportantEventRecall@5"]["value"] is None for s in gold["steps"])


def test_budget_presentation_tamper_cannot_change_metric_denominator(bundle, tmp_path):
    from evals.intelligence_v1.evaluate import evaluate_run
    from evals.intelligence_v1.exceptions import ContractError
    from evals.intelligence_v1.hashing import canonical_json

    output = tmp_path/"b3"
    run(bundle, output, "b3", timeline_id="REVISIT-7D", budget_seconds=180)
    rows = [json.loads(line) for line in (output/"predictions.jsonl").read_bytes().splitlines()]
    rows[-1]["presentation"]["presented_items"] = []
    raw = ''.join(canonical_json(r)+'\n' for r in rows).encode()
    (output/"predictions.jsonl").write_bytes(raw)
    metadata = json.loads((output/"run_metadata.json").read_bytes())
    metadata["predictions_sha256"] = sha256_bytes(raw)
    (output/"run_metadata.json").write_text(canonical_json(metadata)+'\n', encoding="utf-8")
    manifest = bundle/"manifests/dataset_manifest.json"
    with pytest.raises(ContractError, match="BUDGET_PRESENTATION_MISMATCH"):
        evaluate_run(output, manifest, manifest_sha256=sha256_bytes(manifest.read_bytes()),
                     out=tmp_path/"bad-evaluation")
    assert not (tmp_path/"bad-evaluation").exists()


def test_report_checks_replicates_separates_labels_and_has_d8_diagnostics(bundle, tmp_path):
    from evals.intelligence_v1.evaluate import evaluate_run
    from evals.intelligence_v1.report import build_report

    manifest = bundle/"manifests/dataset_manifest.json"
    pin = sha256_bytes(manifest.read_bytes())
    runs = tmp_path/"runs"
    for algorithm in ("b1", "b3", "b4"):
        output = runs/algorithm
        run(bundle, output, algorithm, timeline_id="REVISIT-7D")
        evaluate_run(output, manifest, manifest_sha256=pin, label_source="synthetic-fixture",
                     out=runs/(algorithm+"-evaluation"))
    result = build_report(runs, manifest, manifest_sha256=pin, out=tmp_path/"summary")
    text = (tmp_path/"summary/report.md").read_text("utf-8")
    assert "D8" in text and "synthetic-fixture" in text and "B1" in text
    assert result["human_annotation"] == "not_confirmed"
    assert result["comparisons"]
    from evals.intelligence_v1.exceptions import ContractError
    from evals.intelligence_v1.hashing import canonical_json

    metadata_path = runs/"b3/run_metadata.json"
    metadata = json.loads(metadata_path.read_bytes())
    metadata["dataset_manifest_sha256"] = "0"*64
    metadata_path.write_text(canonical_json(metadata)+"\n", encoding="utf-8")
    with pytest.raises(ContractError, match="RUN_INPUT_MISMATCH"):
        build_report(runs, manifest, manifest_sha256=pin, out=tmp_path/"tampered-summary")
    assert not (tmp_path/"tampered-summary").exists()


def comparison_runs(bundle, tmp_path, *, algorithm="b3", baseline_step=None,
                    comparison_step=None, half_life_days=7):
    from evals.intelligence_v1.evaluate import evaluate_run

    manifest = bundle/"manifests/dataset_manifest.json"
    pin = sha256_bytes(manifest.read_bytes())
    runs = tmp_path/"runs"
    for algo, step in (("b1", baseline_step), (algorithm, comparison_step)):
        output = runs/algo
        run(bundle, output, algo, timeline_id="REVISIT-7D", step_id=step,
            budget_seconds=180, half_life_days=7 if algo == "b1" else half_life_days)
        evaluate_run(output, manifest, manifest_sha256=pin, label_source="synthetic-fixture",
                     out=runs/(algo+"-evaluation"))
    return runs, manifest, pin


@pytest.mark.parametrize("algorithm", ["b3", "b4"])
@pytest.mark.parametrize("baseline_step,comparison_step", [
    ("D3", "D8"), (None, "D8"), ("D8", None),
], ids=["different-single-steps", "comparison-missing-steps", "baseline-missing-steps"])
def test_report_rejects_unmatched_comparison_steps(bundle, tmp_path, algorithm,
                                                  baseline_step, comparison_step):
    from evals.intelligence_v1.exceptions import ContractError
    from evals.intelligence_v1.report import build_report

    runs, manifest, pin = comparison_runs(bundle, tmp_path, algorithm=algorithm,
        baseline_step=baseline_step, comparison_step=comparison_step)
    output = tmp_path/"rejected-summary"
    with pytest.raises(ContractError, match="COMPARISON_INPUT_MISMATCH"):
        build_report(runs, manifest, manifest_sha256=pin, out=output)
    assert not output.exists()


@pytest.mark.parametrize("algorithm,half_life_days", [("b3", 7), ("b3", 3), ("b4", 7)])
def test_report_allows_matched_partial_comparisons(bundle, tmp_path, algorithm, half_life_days):
    from evals.intelligence_v1.report import build_report

    runs, manifest, pin = comparison_runs(bundle, tmp_path, algorithm=algorithm,
        baseline_step="D8", comparison_step="D8", half_life_days=half_life_days)
    result = build_report(runs, manifest, manifest_sha256=pin, out=tmp_path/"summary")
    assert result["comparisons"]
    assert all(c["algorithm_id"] == algorithm for c in result["comparisons"])
    assert all(len(c["steps"]) == 1 for c in result["cohorts"])


@pytest.mark.parametrize("field,value", [
    ("budget_seconds", 900), ("candidate_sha256", "0"*64), ("context_sha256", "0"*64),
])
def test_report_rejects_mismatched_per_step_inputs(bundle, tmp_path, field, value):
    from evals.intelligence_v1.exceptions import ContractError
    from evals.intelligence_v1.hashing import canonical_json
    from evals.intelligence_v1.report import build_report

    runs, manifest, pin = comparison_runs(bundle, tmp_path)
    path = runs/"b3-evaluation/metrics.json"
    metrics = json.loads(path.read_bytes())
    # Context hashes commit the Persona version, preferences and delivery history.
    # Rehash the evaluation artifact so the report's per-step comparison is tested.
    metrics["steps"][0][field] = value
    raw = (canonical_json(metrics)+"\n").encode()
    path.write_bytes(raw)
    metadata_path = path.parent/"evaluation_metadata.json"
    metadata = json.loads(metadata_path.read_bytes())
    metadata["metrics_sha256"] = sha256_bytes(raw)
    metadata_path.write_text(canonical_json(metadata)+"\n", encoding="utf-8")
    output = tmp_path/"rejected-summary"
    with pytest.raises(ContractError, match="COMPARISON_INPUT_MISMATCH|CANDIDATE_POOL_MISMATCH"):
        build_report(runs, manifest, manifest_sha256=pin, out=output)
    assert not output.exists()
