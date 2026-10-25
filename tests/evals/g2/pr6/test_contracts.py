import pytest
from pydantic import ValidationError

from evals.intelligence_g2.contracts import data, json_bytes
from evals.intelligence_g2.pr6.acceptance import decide, verify_review
from evals.intelligence_g2.pr6.contracts import CampaignSpec, G2AcceptanceResult, Gate, MetricValue
from evals.intelligence_g2.pr6.metrics import not_evaluated, ratio
from evals.intelligence_g2.pr6.reproduce import make_jobs
from evals.intelligence_v1.exceptions import ContractError

from ..support import output_path
from .support import campaign


@pytest.mark.parametrize("n,d,value", [(0, 0, None), (0, 1, 0.0), (1, 2, 0.5)])
def test_denominators(n, d, value):
    result = ratio(n, d)
    assert result.value == value and result.denominator == d and result.numerator == n
    if not d:
        assert result.reason == "zero_denominator"
    assert not_evaluated("independence_unknown").value is None


@pytest.mark.parametrize("change", [{"value": 1.0}, {"reason": None}, {"status": "measured"}])
def test_unavailable_metrics_cannot_be_filled_as_pass(change):
    with pytest.raises(ValidationError):
        MetricValue.model_validate_json(json_bytes({**data(ratio(0, 0)), **change}))


@pytest.mark.parametrize("name", [f"H{i:02}" for i in range(1, 11)])
def test_each_gate_is_required_and_humans_never_block(name):
    gates = {
        f"H{i:02}": Gate(status="PASS", evidence=("actual_hash",), reason="verified")
        for i in range(1, 11)
    }
    result = decide(gates, "a" * 40)
    assert result.overall_status == "PASS" and result.user_research == "not_evaluated"
    assert result.administrator_acceptance == "pending" and result.g3_planning_authorized is False
    gates[name] = Gate(status="BLOCKED", evidence=(), reason="missing")
    result = decide(gates, "a" * 40)
    assert result.overall_status == "NOT_MET" and not result.g3_offline_eligible
    with pytest.raises(ValidationError):
        G2AcceptanceResult.model_validate_json(
            json_bytes({**data(result), "overall_status": "PASS"})
        )


def test_full_matrix_has_all_axes_and_prefix_jobs():
    value = CampaignSpec.model_validate_json(
        json_bytes(
            {
                **data(campaign()),
                "scope": "full",
                "strategies": ["r0", "r1"],
                "profiles": ["low", "standard", "high"],
                "seeds": [1, 719],
                "orders": ["canonical", "reverse"],
                "supplemental_r2": True,
            }
        )
    )
    jobs = make_jobs(value)
    assert len({j.job_id for j in jobs}) == len(jobs)
    assert {j.case_id for j in jobs if j.cohort == "g1_primary"} == {
        f"DEV-{i:02}" for i in range(1, 6)
    }
    assert {j.profile for j in jobs if j.strategy == "r2"} == {"standard"}
    assert any(j.prefix for j in jobs)
    with pytest.raises(ValidationError):
        CampaignSpec.model_validate_json(json_bytes({**data(value), "seeds": [1]}))


def test_programmatic_checks_are_not_an_ai_review():
    path = output_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(json_bytes(dict(case_id="x", executor_type="programmatic_check")))
    from evals.intelligence_v1.hashing import sha256_bytes

    with pytest.raises(ContractError) as e:
        verify_review(
            path,
            sha256_bytes(path.read_bytes()),
            prediction_pin="p",
            evaluation_pin="e",
            commit="c",
            cases=["x"],
        )
    assert e.value.code == "G2_PR6_REVIEW_INVALID" and e.value.field == "review_binding"
