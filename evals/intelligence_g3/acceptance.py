"""Fail-closed offline development acceptance; no supplied PASS switches."""

import argparse
from pathlib import Path

from evals.intelligence_g2.contracts import digest, json_bytes, read_json

from .artifacts import fresh, release, seal, sealed, write
from .checks import verify_checks
from .contracts import fail
from .evaluate import evaluate_rows, verify_predictions
from .fact_signature import policy_sha256
from .report import markdown


def accept(*, run, run_pin, evaluation, evaluation_pin, checks, checks_pin, out):
    check_manifest, coverage = verify_checks(checks, checks_pin)
    ev = sealed(Path(evaluation).absolute(), evaluation_pin, "evaluation")
    campaign, predictions, pred = verify_predictions(run, run_pin)
    source_hash = digest(release())
    if (ev["prediction_pin"] != run_pin
            or {check_manifest["source_sha256"], pred["source_sha256"], ev["source_sha256"]} != {source_hash}):
        fail("G3_CHECK_EVIDENCE_MISMATCH", "same_source_and_prediction")
    expected, failures = evaluate_rows(campaign, predictions)
    root = Path(evaluation).absolute()
    if (read_json((root / "metrics.json").read_bytes()) != expected
            or (root / "failures.jsonl").read_bytes() != b"".join(json_bytes(r) for r in failures)
            or (root / "REPORT.md").read_text(encoding="utf-8") != markdown(expected, run)):
        fail("G3_EVALUATION_MISMATCH", "recomputed_metrics_report_failures")
    # B2 is a separate attribution control; check the actual scores/order against B1.
    by_job = {p["job_id"]: p for p in predictions}
    for p in predictions:
        if p["job"]["variant"] == "b2":
            other = by_job[p["job_id"].removesuffix("b2") + "b1"]
            def projection(v):
                return [(r["event_key"], r["score"]) for r in v["ranking"]["events"]]
            if projection(p) != projection(other):
                fail("G3_COMPARISON_INVALID", "b2_identity_control")
    if any(r["metrics"]["ConstraintViolationRate"]["numerator"] for r in expected["measurements"]):
        fail("G3_HARD_GATE_VIOLATION", "presented_ineligible")
    result = dict(schema_revision="g3-pr5-acceptance-v2", profile="ai_development",
        overall_status="PASS", source_sha256=source_hash, prediction_pin=run_pin,
        fact_signature_policy_sha256=policy_sha256(),
        evaluation_pin=evaluation_pin, checks_pin=checks_pin, junit=coverage,
        gates={name: dict(status="PASS", evidence=artifact) for name, artifact in (
            ("inputs_time_identity_history_evidence", "recomputed_predictions_and_required_regressions"),
            ("budget_coverage_archive", "recomputed_plans_and_required_regressions"),
            ("complete_matrix_and_determinism", "exact_jobs_and_two_seed_semantics"),
            ("reproducible_source_config_tests_artifacts", "three_externally_pinned_manifests"),
            ("regression_and_frozen_compatibility", "exact_full_JUnit_and_frozen_source_pins"),
            ("honest_metrics_and_failures", "recomputed_reference_counts_and_report"))},
        algorithm_decision=expected["decision"], human_research="not_evaluated_optional",
        independent_test_effect="not_evaluated", production_ready=False, real_user_effect=False,
        g4_implementation_authorized=False, next_step="Independent PR5 review and explicit owner approval")
    output = fresh(out)
    write(output, "acceptance.json", result)
    write(output, "REPORT.md", markdown(expected, run).encode("utf-8"))
    pin = seal(output, "acceptance", source_sha256=source_hash,
               prediction_pin=run_pin, evaluation_pin=evaluation_pin, checks_pin=checks_pin)
    print(json_bytes(dict(overall_status="PASS", acceptance_pin=pin, out=str(output))).decode(), end="")
    return result, pin


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("run", "run-pin", "evaluation", "evaluation-pin", "checks", "checks-pin", "out"):
        p.add_argument("--" + name, required=True)
    args = p.parse_args(argv)
    try:
        accept(**vars(args))
    except (ValueError, OSError, KeyError, TypeError) as error:
        print(json_bytes(dict(overall_status="NOT_MET", code=getattr(error, "code", "G3_EVIDENCE_INVALID"),
                              field=getattr(error, "field", "artifacts"))).decode(), end="")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
