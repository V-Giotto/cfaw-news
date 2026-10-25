import asyncio
from types import SimpleNamespace

import pytest

from evals.intelligence_g2.pr6.contracts import CaseExecution, digest, json_bytes
from evals.intelligence_g2.pr6.evaluate import compare, verify_job_set
from evals.intelligence_g2.pr6.manifest import sha256_bytes
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
