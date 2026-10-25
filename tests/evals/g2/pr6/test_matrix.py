"""Small full-chain smoke; formal campaign additionally requires both seeds/all budgets."""

import asyncio

from evals.intelligence_g2.pr6.contracts import CaseExecution, digest, json_bytes
from evals.intelligence_g2.pr6.evaluate import compare, references
from evals.intelligence_g2.pr6.manifest import PACKAGE, sha256_bytes
from evals.intelligence_g2.pr6.predict import run_job
from evals.intelligence_g2.pr6.reproduce import make_jobs
from evals.intelligence_v1.exceptions import ContractError

from .support import campaign


def test_complete_smoke_matrix(tmp_path):
    async def execute():
        executions, results = [], {}
        for job in make_jobs(campaign()):
            try:
                rows, _ = await run_job(job, campaign())
                execution = CaseExecution(
                    job=job,
                    returned=True,
                    result_path="steps.jsonl",
                    semantic_sha256=sha256_bytes(b"".join(json_bytes(r) for r in rows)),
                    trace_path="trace.json",
                    trace_sha256="0" * 64,
                    pool_sha256=digest([r.pool_sha256 for r in rows]),
                )
                results[job.job_id] = rows
            except ContractError as error:
                execution = CaseExecution(
                    job=job,
                    returned=False,
                    diagnostic=dict(
                        code=error.code, stage=getattr(error, "stage", "input"), field=error.field
                    ),
                )
            executions.append(execution)
        path = PACKAGE / "fixtures/pr6/v1/reference/manifest_v5.json"
        refs, pairs, continuity = references(path, sha256_bytes(path.read_bytes()))
        report = compare(executions, results, refs, pairs, continuity)
        (tmp_path / "preflight_matrix.json").write_bytes(json_bytes(report))
        assert report["ok"], report["errors"]
        assert report["determinism"] == dict(
            seed_order=True, prefix=True, immutable_rule=True, same_pool=True
        )
        g1 = [
            r
            for e in executions
            if e.job.cohort.startswith("g1_") and not e.job.prefix and e.job.mode == "rule"
            for r in results[e.job.job_id]
        ]
        assert len(g1) == 35
        assert all(p.base_item in r.rule.items for r in g1 for p in r.expression.presentations)

    asyncio.run(execute())
