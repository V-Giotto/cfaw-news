"""Verify pinned prediction semantics, then evaluate separate nonblind references."""

import argparse
from pathlib import Path

from evals.intelligence_g2.contracts import data, digest, json_bytes, read_json

from .artifacts import (
    fresh,
    load_campaign,
    pinned,
    relative,
    release,
    seal,
    sealed,
    verify_command,
    write,
)
from .contracts import PACKAGE, fail
from .experiments import predict
from .fact_signature import policy, policy_sha256
from .history_contracts import HistoryInput, parse_history
from .metrics import aggregate, measure
from .pr5_contracts import configuration
from .reproduce import jobs, worker_argv


def verify_predictions(run, pin, *, recompute=True):
    run = Path(run).absolute()
    manifest = sealed(run, pin, "prediction")
    campaign = load_campaign(manifest["campaign_path"], manifest["campaign_sha256"])
    source = release()
    if (read_json((run / "source_release.json").read_bytes()) != source
            or manifest["source_sha256"] != digest(source)
            or manifest.get("fact_signature_policy_sha256") != policy_sha256()
            or read_json((run / "configuration.json").read_bytes()) != configuration()
            or read_json((run / "fact_signature_policy.json").read_bytes()) != policy()
            or read_json((run / "campaign.json").read_bytes()) != data(campaign)):
        fail("G3_SOURCE_MISMATCH", "prediction_source_config")
    expected = jobs(campaign)
    rows_by_seed = []
    for seed in (1, 719):
        verify_command(run, f"worker-{seed}", worker_argv(
            manifest["campaign_path"], manifest["campaign_sha256"], run, seed), seed=seed)
        rows = [read_json(v) for v in (run / f"predictions-{seed}.jsonl").read_bytes().splitlines()]
        if ([r["job"] for r in rows] != [data(j) for j in expected]
                or [r["job_id"] for r in rows] != [j.job_id for j in expected]
                or read_json((run / f"semantic-{seed}.json").read_bytes()) !=
                   {r["job_id"]: digest(r) for r in rows}):
            fail("G3_MATRIX_INCOMPLETE", "exact_jobs_and_semantics")
        timings = read_json((run / f"timings-{seed}.json").read_bytes())
        if ([v["job_id"] for v in timings] != [j.job_id for j in expected]
                or any(v["elapsed_seconds"] < 0 for v in timings)):
            fail("G3_CHECK_EVIDENCE_MISMATCH", "timings")
        rows_by_seed.append(rows)
    if rows_by_seed[0] != rows_by_seed[1]:
        fail("G3_NONDETERMINISTIC", "two_seed_semantics")
    summary = read_json((run / "summary.json").read_bytes())
    if (summary["jobs_per_seed"] != len(expected) or summary["actual_prediction_runs"] != 2 * len(expected)
            or summary["all_semantics_equal"] is not True
            or summary["config_sha256"] != campaign.config_sha256
            or summary["model_calls"] != 0 or summary["external_requests"] != 0):
        fail("G3_CHECK_EVIDENCE_MISMATCH", "summary")
    sources = {c.case_id: parse_history(HistoryInput, read_json(pinned(
        PACKAGE / relative(c.input.path), c.input.sha256, PACKAGE / "fixtures/pr5")))
        for c in campaign.cases}
    contexts = {}
    for job, row in zip(expected, rows_by_seed[0], strict=True):
        key = (job.case_id, job.budget)
        identity = row["candidate_pool_sha256"], row["input_sha256"], row["context_sha256"]
        if contexts.setdefault(key, identity) != identity:
            fail("COMPARISON_INPUT_MISMATCH", "same_pool_persona_history_budget")
        if recompute and predict(sources[job.case_id], job) != row:
            fail("G3_PREDICTION_MISMATCH", job.job_id)
        plan = row["plan"]
        if (plan["diagnostics"]["used_seconds"] > job.budget
                or set(plan["archive_snapshot_ids"]) !=
                   {r["snapshot_id"] for r in row["ranking"]["events"]}):
            fail("G3_PLAN_INVALID", "budget_or_archive")
    return campaign, rows_by_seed[0], manifest


def evaluate_rows(campaign, predictions):
    refs = read_json(pinned(PACKAGE / relative(campaign.references.path),
                           campaign.references.sha256, PACKAGE / "fixtures/pr5"))
    if (refs["origin"] != "ai_development" or refs["synthetic"] is not True
            or refs["non_blind"] is not True or refs["independent_validation"] is not False
            or refs["human_gold"] is not False or refs["held_out"] is not False
            or refs["semantic_truth"] != "not_evaluated"
            or set(refs["cases"]) != {c.case_id for c in campaign.cases}):
        fail("G3_REFERENCE_MISMATCH", "provenance_and_cases")
    cases = {c.case_id: c for c in campaign.cases}
    measurements, failures = [], []
    b2 = []
    for row in predictions:
        c = cases[row["job"]["case_id"]]
        measured, errors = measure(row, refs["cases"][c.case_id], c.revisit_days)
        if row["job"]["variant"] == "b2":
            b2.append(measured)
        else:
            measurements.append(measured)
        failures.extend(errors)
    families = {r["family_id"] for rows in refs["cases"].values() for r in rows}
    report = dict(schema_revision="g3-pr5-evaluation-v2", profile="ai_development",
        fact_signature_policy=policy(),
        measurements=measurements, aggregates=aggregate(measurements),
        event_family_count=len(families), family_ids=sorted(families),
        uncertainty=dict(interval=None, undefined_reason="purposive_reused_nonblind_families_no_independent_holdout",
                         independent_test_families=0),
        b2_g2_contribution=dict(measurements=b2, aggregates=aggregate(b2),
            grouping_delta=None, undefined_reason="no_unmerged_document_arm_in_G3_event_pool",
            attribution="G2 grouping already applied; B2 is identity-preserving B1 control; no G3 gain claim"),
        decision=dict(selected_baseline="b4", replace_b4=False,
                      reason="No independent stable improvement established; development comparisons only"),
        metric_definition="micro ratios; each metric uses only its applicable scope; dataset_support is separate; correlated states are not independent users",
        failure_count=len(failures))
    return report, failures


def evaluate(run, pin, out):
    campaign, rows, manifest = verify_predictions(run, pin)
    metrics, failures = evaluate_rows(campaign, rows)
    output = fresh(out)
    write(output, "metrics.json", metrics)
    write(output, "failures.jsonl", b"".join(json_bytes(r) for r in failures))
    from .report import markdown

    write(output, "REPORT.md", markdown(metrics, run).encode("utf-8"))
    result = seal(output, "evaluation", prediction_pin=pin, source_sha256=manifest["source_sha256"])
    print(result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True)
    parser.add_argument("--run-pin", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    evaluate(Path(args.run).absolute(), args.run_pin, args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
