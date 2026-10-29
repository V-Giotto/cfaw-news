"""PR5 failure gates and experiment invariants; all test artifacts are synthetic."""

import ast
import copy
import sys
from uuid import uuid4

import pytest
from pydantic import ValidationError

from evals.intelligence_g2.contracts import data, json_bytes, read_json
from evals.intelligence_g3.acceptance import accept, main
from evals.intelligence_g3.artifacts import (
    OUTPUT_BASE,
    command,
    fresh,
    load_campaign,
    pinned,
    relative,
    seal,
    sealed,
    verify_command,
    write,
)
from evals.intelligence_g3.contracts import PACKAGE
from evals.intelligence_g3.evaluate import evaluate_rows
from evals.intelligence_g3.experiments import ExperimentInput, predict, project
from evals.intelligence_g3.history_contracts import HistoryInput, parse_history
from evals.intelligence_g3.metrics import aggregate, measure
from evals.intelligence_g3.pr5_contracts import DISABLED, Campaign, Metric, check_schemas
from evals.intelligence_g3.reproduce import jobs
from evals.intelligence_g3.revisit import rank_revisit
from evals.intelligence_v1.exceptions import ContractError
from evals.intelligence_v1.hashing import sha256_bytes

MANIFEST_PIN = "56f2244812449db5ddb5a8bd2384cb302a3f9d66fb1205be167e9308da530daf"


@pytest.fixture(scope="module")
def campaign():
    return load_campaign(PACKAGE / "manifests/pr5_campaign.json", MANIFEST_PIN)


@pytest.fixture
def artifact_root():
    return fresh(OUTPUT_BASE / "tests/pr5" / uuid4().hex)


def source(campaign, case_id):
    case = next(c for c in campaign.cases if c.case_id == case_id)
    return parse_history(HistoryInput, read_json((PACKAGE / case.input.path).read_bytes()))


def result_for(campaign, case_id, variant="p1", budget=180):
    job = next(j for j in jobs(campaign) if
               (j.case_id, j.variant, j.budget) == (case_id, variant, budget))
    return predict(source(campaign, case_id), job)


def labels_for(campaign, case_id):
    return read_json((PACKAGE / campaign.references.path).read_bytes())["cases"][case_id]


def test_complete_registered_matrix_and_honest_provenance(campaign):
    assert len(jobs(campaign)) == 858
    assert len({j.job_id for j in jobs(campaign)}) == 858
    assert {c.revisit_days for c in campaign.cases if c.cohort == "revisit"} == {1, 3, 7}
    assert campaign.independent_test_set is campaign.human_gold is False
    assert check_schemas()


@pytest.mark.parametrize("fault", ["wrong_pin", "duplicate_case", "config", "unknown_field"])
def test_campaign_rejects_untrusted_or_incompatible_inputs(campaign, fault):
    if fault == "wrong_pin":
        with pytest.raises(ContractError, match="G3_SHA_MISMATCH"):
            load_campaign(PACKAGE / "manifests/pr5_campaign.json", "0" * 64)
        return
    raw = data(campaign)
    if fault == "duplicate_case":
        raw["cases"].append(raw["cases"][0])
    elif fault == "config":
        raw["config_sha256"] = "0" * 64
    else:
        raw["gold"] = "must_not_enter_prediction"
    with pytest.raises((ContractError, ValidationError)):
        parse_history(Campaign, raw)


@pytest.mark.parametrize("name", ["../secret", "C:/secret", "x\\y", "/tmp/x", "."])
def test_artifact_paths_reject_escape(name):
    with pytest.raises(ContractError):
        relative(name)


@pytest.mark.parametrize("fault", ["missing", "changed", "extra", "wrong_pin", "wrong_role"])
def test_artifact_integrity_fails_closed(artifact_root, fault):
    write(artifact_root, "payload.json", dict(synthetic_test_only=True))
    pin = seal(artifact_root, "synthetic_test_only")
    assert sealed(artifact_root, pin, "synthetic_test_only")["files"]
    if fault == "missing":
        (artifact_root / "payload.json").unlink()
    elif fault == "changed":
        (artifact_root / "payload.json").write_bytes(b"tampered")
    elif fault == "extra":
        write(artifact_root, "extra.json", {})
    with pytest.raises((ContractError, OSError)):
        sealed(artifact_root, "0" * 64 if fault == "wrong_pin" else pin,
               "other" if fault == "wrong_role" else "synthetic_test_only")


@pytest.mark.parametrize("field", ["exit_code", "argv", "cwd", "environment", "log_sha256"])
def test_actual_command_record_tamper_is_rejected(artifact_root, field):
    argv = [sys.executable, "-c", "print('synthetic PR5 command-record test')"]
    record = command(artifact_root, "actual", argv)
    assert verify_command(artifact_root, "actual", argv)["exit_code"] == 0
    replacement = dict(exit_code=7, argv=["never_executed"], cwd="wrong",
                       environment={}, log_sha256="0" * 64)
    record[field] = replacement[field]
    (artifact_root / "actual.command.json").write_bytes(json_bytes(record))
    with pytest.raises(ContractError):
        verify_command(artifact_root, "actual", argv)


def test_actual_failed_command_never_passes(artifact_root):
    argv = [sys.executable, "-c", "raise SystemExit(7)"]
    with pytest.raises(ContractError, match="G3_COMMAND_FAILED"):
        command(artifact_root, "failure", argv)
    assert read_json((artifact_root / "failure.command.json").read_bytes())["exit_code"] == 7


def test_missing_tests_and_artifacts_cannot_be_accepted(artifact_root):
    # No fake successful JUnit or fake check logs are authored.
    with pytest.raises((OSError, ContractError)):
        accept(run=artifact_root, run_pin="0" * 64, evaluation=artifact_root,
               evaluation_pin="0" * 64, checks=artifact_root, checks_pin="0" * 64,
               out=artifact_root / "must_not_exist")
    assert not (artifact_root / "must_not_exist").exists()
    assert main(["--run", str(artifact_root), "--run-pin", "0" * 64,
        "--evaluation", str(artifact_root), "--evaluation-pin", "0" * 64,
        "--checks", str(artifact_root), "--checks-pin", "0" * 64,
        "--out", str(artifact_root / "must_not_exist")]) == 1


@pytest.mark.parametrize("variant", list(DISABLED))
def test_score_ablations_preserve_input_gates_and_change_only_registered_terms(campaign, variant):
    value = source(campaign, "material-ack-3d")
    before = json_bytes(value)
    base = rank_revisit(value)
    result = project(base, variant)
    for row in result.events:
        old = next(r for r in base.events if r.event_key == row.event_key)
        assert (row.eligible, row.protected, row.history, row.features) == (
            old.eligible, old.protected, old.history, old.features)
        for a, b in zip(row.components, old.components, strict=True):
            assert a == (b.model_copy(update={"weight": 0.0, "contribution": 0.0})
                         if a.feature in DISABLED[variant] else b)
    assert json_bytes(value) == before
    assert any(t.contribution for r in base.events for t in r.components
               if t.feature in {"novelty", "material_change"})


def test_experiment_wire_rejects_gate_or_score_forgery(campaign):
    source_value = source(campaign, "correction-ack-1d")
    base = rank_revisit(source_value)
    projection = project(base, "no_material")
    valid = ExperimentInput(history_input=source_value, base_ranking=base, ranking=projection)
    for field in ("score", "protected", "eligible"):
        raw = data(valid)
        raw["ranking"]["events"][0][field] = 999 if field == "score" else False
        with pytest.raises((ContractError, ValidationError)):
            parse_history(ExperimentInput, raw)


def test_same_pool_context_budget_for_baselines_and_ablations(campaign):
    results = [result_for(campaign, "hold-control", variant=v)
               for v in ("b0", "b1", "b2", "b3", "b4", "p1", "no_history")]
    assert len({r["candidate_pool_sha256"] for r in results}) == 1
    assert len({r["context_sha256"] for r in results}) == 1
    for row in results:
        excluded = {r["event_key"] for r in row["ranking"]["events"] if not r["eligible"]}
        assert excluded
        assert not excluded & set(row["plan"]["display_order"])
    assert [(r["event_key"], r["score"]) for r in results[1]["ranking"]["events"]] == [
        (r["event_key"], r["score"]) for r in results[2]["ranking"]["events"]]


def test_budget_misses_remain_in_denominators_and_failures(campaign):
    result = result_for(campaign, "protected6", budget=420)
    labels = labels_for(campaign, "protected6")
    measured, failures = measure(result, labels, None)
    assert result["plan"]["diagnostics"]["unmet_protected_event_keys"]
    assert measured["metrics"]["ImportantEventRecall@budget"]["denominator"] == 7
    assert measured["metrics"]["ImportantMissRate"]["numerator"] > 0
    protected_misses = [f for f in failures if f["protected"] and f["kind"] == "important_miss"]
    assert protected_misses and all(f["retained_in_denominator"] for f in protected_misses)


def test_zero_denominator_is_undefined_not_perfect(campaign):
    result = result_for(campaign, "repeat-ack-1d")
    measured, _ = measure(result, labels_for(campaign, "repeat-ack-1d"), 1)
    recall = measured["metrics"]["ImportantEventRecall@budget"]
    assert recall["numerator"] == recall["denominator"] == 0
    assert recall["value"] is None and recall["undefined_reason"]
    assert recall["sample_count"] == recall["event_family_count"] == 1


@pytest.mark.parametrize("fault", ["missing", "duplicate", "snapshot", "revision"])
def test_reference_completeness_and_identity_are_mandatory(campaign, fault):
    labels = copy.deepcopy(labels_for(campaign, "protected6"))
    if fault == "missing":
        labels.pop()
    elif fault == "duplicate":
        labels.append(labels[0])
    else:
        labels[0]["snapshot_id" if fault == "snapshot" else "event_revision"] = "wrong"
    with pytest.raises(ContractError, match="G3_REFERENCE_MISMATCH"):
        measure(result_for(campaign, "protected6"), labels, None)


def test_correlated_horizons_do_not_become_independent_families(campaign):
    rows = []
    for day in (1, 3, 7):
        case = f"material-ack-{day}d"
        row, _ = measure(result_for(campaign, case), labels_for(campaign, case), day)
        rows.append(row)
    all_cell = next(r for r in aggregate(rows) if r["axis"] == "all")
    assert all_cell["metrics"]["ImportantEventRecall@budget"]["sample_count"] == 3
    assert all_cell["metrics"]["ImportantEventRecall@budget"]["event_family_count"] == 1


def test_b2_is_separate_and_not_a_g3_aggregation_gain(campaign):
    values = [result_for(campaign, "crowded14", v) for v in ("b1", "b2", "p1")]
    metrics, _ = evaluate_rows(campaign, values)
    assert {r["variant"] for r in metrics["measurements"]} == {"b1", "p1"}
    assert metrics["b2_g2_contribution"]["grouping_delta"] is None
    assert metrics["uncertainty"]["independent_test_families"] == 0
    assert metrics["decision"]["replace_b4"] is False


def test_prediction_modules_do_not_import_labels_tests_or_metrics():
    for name in ("reproduce.py", "experiments.py", "revisit.py", "rankers.py"):
        module = ast.parse((PACKAGE / name).read_text(encoding="utf-8"))
        imports = [n.module or "" for n in ast.walk(module) if isinstance(n, ast.ImportFrom)]
        assert not any("tests" in i or "metrics" in i or "evaluate" in i for i in imports)


def test_no_silent_artifact_overwrite_or_untrusted_self_hash(artifact_root):
    with pytest.raises(ContractError):
        fresh(artifact_root)
    write(artifact_root, "input.json", dict(synthetic_test_only=True))
    with pytest.raises(ContractError):
        pinned(artifact_root / "input.json", "0" * 64, artifact_root)
    assert sha256_bytes((artifact_root / "input.json").read_bytes()) != "0" * 64


@pytest.mark.parametrize("numerator,denominator,value,reason", [(1, 0, None, "zero"),
    (0, 0, 1, "zero"), (0, 0, None, None), (1, 2, 1, None), (-1, 2, -.5, None)])
def test_metric_wire_rejects_false_ratios(numerator, denominator, value, reason):
    with pytest.raises((ValidationError, ContractError)):
        Metric(numerator=numerator, denominator=denominator, value=value, sample_count=1,
               event_family_count=1, undefined_reason=reason)
