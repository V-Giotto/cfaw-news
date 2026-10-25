import asyncio
import json

import pytest

from evals.intelligence_g2.contracts import PACKAGE
from evals.intelligence_g2.pr6.contracts import StepRecord, data, json_bytes
from evals.intelligence_g2.pr6.evaluate import check_case
from evals.intelligence_g2.pr6.manifest import prediction_catalog
from evals.intelligence_g2.pr6.predict import run_job
from evals.intelligence_v1.exceptions import ContractError

from .support import campaign, job, reference

CASES = [
    c["case_id"]
    for c in json.loads((PACKAGE / "fixtures/pr6/v1/prediction/cases_v4.json").read_bytes())[
        "cases"
    ]
]


@pytest.mark.parametrize("case", CASES)
def test_frozen_synthetic_controls(case):
    value = job(case)
    try:
        records, traces = asyncio.run(run_job(value, campaign()))
    except ContractError as e:
        assert case in {"E01-negative", "E09-secondary", "E11-json-negative"}
        expected = (
            ("FUTURE_VERSION", "bridge", "candidate.available_at")
            if case == "E01-negative"
            else ("ORIGIN_MISMATCH", "bridge", "redistribution_rights")
            if case == "E09-secondary"
            else ("G2_PR6_SENSITIVE_EXPORT", "pr6", "semantic_artifact")
        )
        assert (e.code, e.stage, e.field) == expected
        return
    assert len(records) == len(traces) > 0
    assert (
        check_case(
            type("Execution", (), {"job": value, "returned": True})(), records, reference(case)
        )
        == []
    )
    for row in records:
        assert StepRecord.model_validate_json(json_bytes(row)) == row
        assert all(
            i.event_key == p.event_key and i == p.base_item
            for i, p in zip(row.rule.items, row.expression.presentations, strict=True)
        )


def test_seed_order_and_exact_rule_control():
    async def check():
        a, _ = await run_job(job("E04-positive"), campaign())
        b, _ = await run_job(job("E04-positive", order="reverse"), campaign())
        c, _ = await run_job(job("E04-positive", mode="rule"), campaign())
        assert json_bytes(a) == json_bytes(b)
        assert [data(r.rule) for r in a] == [data(r.rule) for r in c]

    asyncio.run(check())


def test_all_three_budgets_are_existing_contract_values():
    async def check():
        for profile, seconds in [("low", 180), ("standard", 420), ("high", 900)]:
            rows, _ = await run_job(job("E04-positive", profile=profile), campaign())
            assert rows[0].reading_budget_seconds == seconds
            assert rows[0].expression.presentations[0].base_item == rows[0].rule.items[0]

    asyncio.run(check())


def test_prediction_catalog_never_needs_reference():
    root, rows = prediction_catalog(campaign())
    assert root.name == "prediction" and len(rows) == 29
    assert {c["error_mode"] for c in rows} == {f"E{i:02}" for i in range(1, 13)}
