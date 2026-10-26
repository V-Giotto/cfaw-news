import asyncio
from types import SimpleNamespace

import pytest

from evals.intelligence_g2.pr6.acceptance import h02_ready
from evals.intelligence_g2.pr6.contracts import CaseExecution, data, digest, json_bytes
from evals.intelligence_g2.pr6.evaluate import compare, references, verify_job_set
from evals.intelligence_g2.pr6.manifest import PACKAGE, sha256_bytes
from evals.intelligence_g2.pr6.predict import run_job
from evals.intelligence_g2.pr6.reproduce import make_jobs
from evals.intelligence_v1.exceptions import ContractError

from .support import campaign, job, reference


@pytest.mark.parametrize("fault", ["missing", "duplicate", "reordered"])
def test_exact_matrix_does_not_accept_missing_or_duplicate_jobs(fault):
    jobs = [SimpleNamespace(job=j) for j in make_jobs(campaign())]
    verify_job_set(jobs, campaign())
    if fault == "missing":
        jobs.pop()
    elif fault == "duplicate":
        jobs.append(jobs[0])
    else:
        jobs.reverse()
    with pytest.raises(ContractError) as error:
        verify_job_set(jobs, campaign())
    assert (error.value.code, error.value.stage, error.value.field) == (
        "G2_PR6_MATRIX_INVALID",
        "pr6",
        "job_set",
    )


@pytest.mark.parametrize(
    "fault,field",
    [("pool", "same_pool"), ("semantic", "seed_or_order"), ("reference", "reference_case_set")],
)
def test_comparator_rejects_pool_drift_and_missing_reference(fault, field):
    async def check():
        executions, results = [], {}
        for mode in ("rule", "mock"):
            value = job("E04-positive", mode=mode)
            rows, _ = await run_job(value, campaign())
            entry = CaseExecution(
                job=value,
                returned=True,
                result_path="steps.jsonl",
                semantic_sha256=sha256_bytes(json_bytes(rows)),
                trace_path="trace.json",
                trace_sha256="0" * 64,
                pool_sha256=digest([r.pool_sha256 for r in rows]),
            )
            executions.append(entry)
            results[value.job_id] = rows
        refs = {"E04-positive": reference("E04-positive")}
        assert compare(executions, results, refs, (), ())["ok"]
        if fault == "pool":
            executions[0] = executions[0].model_copy(update={"pool_sha256": "f" * 64})
        elif fault == "semantic":
            copied = executions[0].model_copy(
                update={
                    "job": executions[0].job.model_copy(update={"seed": 719}),
                    "semantic_sha256": "f" * 64,
                }
            )
            executions.append(copied)
        else:
            refs = {}
        with pytest.raises(ContractError) as error:
            compare(executions, results, refs, (), ())
        assert error.value.field == field

    asyncio.run(check())


@pytest.fixture(scope="module")
def continuity_inputs():
    async def generate():
        values = {}
        for strategy in ("r0", "r1"):
            entries, results = [], {}
            for mode in ("rule", "mock"):
                value = job("DEV-01", strategy=strategy, mode=mode)
                rows, _ = await run_job(value, campaign())
                entries.append(
                    CaseExecution(
                        job=value,
                        returned=True,
                        result_path="steps.jsonl",
                        semantic_sha256=sha256_bytes(b"".join(json_bytes(r) for r in rows)),
                        trace_path="trace.json",
                        trace_sha256="0" * 64,
                        pool_sha256=digest([r.pool_sha256 for r in rows]),
                    )
                )
                results[value.job_id] = rows
            values[strategy] = (entries, results)
        return values

    values = asyncio.run(generate())
    # Load labels only after generating the prediction records, never into run_job.
    path = PACKAGE / "fixtures/pr6/v1/reference/manifest_v5.json"
    _, pairs, continuity = references(path, sha256_bytes(path.read_bytes()))
    target = next(c for c in continuity if c.case_id == "DEV-01-root-continuity")
    return values, pairs, target


def continuity_mutation(entries, results, target, fault):
    changed, updated = {}, []
    for entry in entries:
        rows = []
        for row in results[entry.job.job_id]:
            step = row.grouping.cursor.step_id
            if fault == "missing_from_step" and step == target.from_step_id:
                continue
            if fault == "missing_to_step" and step == target.to_step_id:
                continue
            member = (
                target.from_doc_version_id if fault == "missing_from_member"
                else target.to_doc_version_id
            )
            selected_step = (
                target.from_step_id if fault == "missing_from_member" else target.to_step_id
            )
            if step == selected_step:
                events = tuple(
                    event.model_copy(update={"event_key": "g2:review:drift"})
                    if fault == "key_drift" and member in event.member_doc_version_ids else event
                    for event in row.grouping.events
                    if not (fault in {"missing_from_member", "missing_to_member"}
                            and member in event.member_doc_version_ids)
                )
                row = row.model_copy(update={"grouping": row.grouping.model_copy(update={"events": events})})
            rows.append(row)
        changed[entry.job.job_id] = tuple(rows)
        updated.append(entry.model_copy(update={
            "semantic_sha256": sha256_bytes(b"".join(json_bytes(r) for r in rows))
        }))
    return updated, changed


@pytest.mark.parametrize("fault", [
    "key_drift", "missing_from_step", "missing_to_step", "missing_from_member", "missing_to_member"
])
def test_review_known_r1_continuity_mismatch_is_an_error(continuity_inputs, fault):
    values, pairs, target = continuity_inputs
    entries, results = continuity_mutation(*values["r1"], target, fault)
    report = compare(entries, results, {}, pairs, (target,))
    assert [(c["continuity"].numerator, c["continuity"].denominator)
            for c in report["cohorts"]] == [(0, 1), (0, 1)]
    assert report["ok"] is False
    assert len(report["errors"]) == 2
    for issue in report["errors"]:
        assert (issue["kind"], issue["stage"], issue["field"], issue["record_id"]) == (
            "continuity_mismatch", "identity_continuity", "event_key", target.case_id
        )
        assert issue["reason"] == ("identity_mismatch" if fault == "key_drift" else "endpoint_missing")
        assert issue["from_step_id"] == target.from_step_id and issue["to_step_id"] == target.to_step_id


def test_review_continuity_normal_and_zero_denominator_are_distinct(continuity_inputs):
    values, pairs, target = continuity_inputs
    entries, results = values["r1"]
    normal = compare(entries, results, {}, pairs, (target,))
    assert normal["ok"] and normal["errors"] == []
    assert all(c["continuity"].value == 1 for c in normal["cohorts"])
    unavailable = compare(entries, results, {}, pairs, ())
    assert unavailable["ok"] and unavailable["errors"] == []
    assert all((c["continuity"].value, c["continuity"].numerator,
                c["continuity"].denominator, c["continuity"].reason)
               == (None, 0, 0, "no_applicable_reference") for c in unavailable["cohorts"])


def test_review_r0_continuity_gap_remains_a_non_successful_baseline(continuity_inputs):
    values, pairs, target = continuity_inputs
    entries, results = continuity_mutation(*values["r0"], target, "key_drift")
    report = compare(entries, results, {}, pairs, (target,))
    assert report["ok"] and report["errors"] == []
    assert all(c["continuity"].value == 0 for c in report["cohorts"])
    assert len(report["baseline_quality"]) == 2
    assert all((r["kind"], r["is_success"], r["record_id"])
               == ("continuity_mismatch", False, target.case_id) for r in report["baseline_quality"])


@pytest.mark.parametrize("fault,matched", [("none", False), ("key_drift", True)])
def test_review_explicit_different_identity_reference(continuity_inputs, fault, matched):
    values, pairs, target = continuity_inputs
    target = target.model_copy(update={"expected": "different"})
    entries, results = continuity_mutation(*values["r1"], target, fault)
    report = compare(entries, results, {}, pairs, (target,))
    assert report["ok"] is matched
    assert all(c["continuity"].value == int(matched) for c in report["cohorts"])


@pytest.mark.parametrize("fault", ["none", "continuity", "false_merge", "error", "no_r1"])
def test_review_h02_checks_continuity_even_with_ok_flag(continuity_inputs, fault):
    values, pairs, target = continuity_inputs
    metrics = data(compare(*values["r1"], {}, pairs, (target,)))
    assert h02_ready(metrics)
    if fault == "continuity":
        # Defense in depth: an aggregate ok flag cannot override a measured 0/1.
        for cohort in metrics["cohorts"]:
            cohort["continuity"].update(numerator=0, value=0.0)
    elif fault == "false_merge":
        metrics["cohorts"][0]["grouping_counts"]["fp"] = 1
    elif fault == "error":
        metrics["errors"].append(dict(kind="continuity_mismatch"))
    elif fault == "no_r1":
        metrics["cohorts"] = []
    assert h02_ready(metrics) is (fault == "none")


def test_review_h02_preserves_unavailable_reference_and_r0_baseline(continuity_inputs):
    values, pairs, _ = continuity_inputs
    metrics = data(compare(*values["r1"], {}, pairs, ()))
    assert h02_ready(metrics)
    metrics["cohorts"].append(dict(strategy="r0", grouping_counts=dict(fp=10),
        continuity=dict(numerator=0, denominator=1)))
    assert h02_ready(metrics)


def test_r0_quality_gap_is_reported_without_relaxing_r1_conflict():
    async def check():
        executions, results = [], {}
        for strategy in ("r0", "r1"):
            for mode in ("rule", "mock"):
                value = job("E05-conflict", strategy=strategy, mode=mode)
                rows, _ = await run_job(value, campaign())
                assert bool(rows[-1].evidence.conflicts) == (strategy == "r1")
                entry = CaseExecution(
                    job=value,
                    returned=True,
                    result_path="steps.jsonl",
                    semantic_sha256=sha256_bytes(json_bytes(rows)),
                    trace_path="trace.json",
                    trace_sha256="0" * 64,
                    pool_sha256=digest([r.pool_sha256 for r in rows]),
                )
                executions.append(entry)
                results[value.job_id] = rows
        report = compare(executions, results, {"E05-conflict": reference("E05-conflict")}, (), ())
        assert report["ok"] and len(report["baseline_quality"]) == 2
        assert all(
            r["root_cause"] == "upstream_r0_separation" and r["is_success"] is False
            for r in report["baseline_quality"]
        )
        from evals.intelligence_g2.pr6.evaluate import check_case

        r0 = executions[0]
        pretended = r0.model_copy(update={"job": r0.job.model_copy(update={"strategy": "r1"})})
        assert "missing_reported_conflict" in check_case(
            pretended, results[r0.job.job_id], reference("E05-conflict")
        )

    asyncio.run(check())
