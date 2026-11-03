"""Version, source, policy, fact and stage-control boundaries."""

from copy import deepcopy

import pytest
from cfaw_news.intelligence.contracts import instant
from cfaw_news.intelligence.runtime import Control, run
from cfaw_news.intelligence.runtime_contracts import RuntimeConfig

from evals.intelligence_g2.contracts import data, digest, json_bytes
from evals.intelligence_g3.fact_signature import persona_content, policy_sha256
from evals.intelligence_g3.ranking_contracts import RankingConfig

from .runtime_support import NOW, envelope, source, version, wire


@pytest.mark.parametrize("field", ["ranking_policy_sha256", "native_engine_sha256",
                                   "fact_signature_policy_sha256"])
def test_old_or_wrong_config_pin_rejected(field):
    value = envelope()
    value["config"][field] = digest(RankingConfig())
    with pytest.raises(ValueError, match="PIN_MISMATCH"):
        wire(value)


def test_budget_profile_and_p1_experiment_are_explicit():
    for budget in ({}, None):
        value = envelope()
        if budget is None:
            value["config"].pop("budget")
        else:
            value["config"]["budget"] = budget
        with pytest.raises(ValueError):
            wire(value)
    value = envelope()
    value["config"]["algorithm"] = "p1"
    with pytest.raises(ValueError, match="EXPERIMENT_REQUIRED"):
        wire(value)
    value["config"]["experiment"] = "p1-explicit-development-v1"
    raw, pin = wire(value)
    result = run(raw, expected_sha256=pin)
    assert result.ranking.algorithm_id == "p1"
    assert RuntimeConfig.model_validate_json(json_bytes(envelope()["config"])).algorithm == "b4"


def test_multi_source_same_event_unknown_independence():
    value = envelope()
    second = source(source_id="other-official")
    value["sources"].append(second.model_dump(mode="json"))
    value["versions"].append(version(second, article="other").model_dump(mode="json"))
    raw, pin = wire(value)
    result = run(raw, expected_sha256=pin)
    assert len(result.stages[-1].grouping.events) == 1
    assert "independence_unknown" in result.stages[-1].evidence.bundles[0].uncertainties
    assert all(a.independent_support_count == 0 for a in result.stages[-1].evidence.assessments)


def test_full_linear_chain_and_missing_middle_rejected():
    value = envelope()
    policy = source()
    v1 = version(policy)
    v2 = version(policy, previous=v1, observed=instant("2026-01-02T01:00:00Z"),
                 body="Correction: Atlas Tool latency is <= 10 ms.")
    v3 = version(policy, previous=v2, observed=instant("2026-01-02T02:00:00Z"),
                 body="Correction: Atlas Tool latency is > 10 ms.")
    value["versions"] = [v.model_dump(mode="json") for v in (v1, v2, v3)]
    raw, pin = wire(value)
    result = run(raw, expected_sha256=pin)
    assert result.stages[-1].replay_input.visible_documents[0].candidate.doc_version_id == v3.doc_version_id
    assert len(result.context.replay.document_archive) == 3
    value["versions"].pop(1)
    with pytest.raises(ValueError, match="LINEAGE_INVALID"):
        wire(value)


@pytest.mark.parametrize("part", ["document", "persona", "coverage"])
def test_explicit_future_inputs_rejected(part):
    value = envelope()
    future = instant("2099-01-01T00:00:00Z")
    if part == "document":
        value["versions"] = [version(source(), observed=future).model_dump(mode="json")]
    elif part == "persona":
        value["persona"]["persona"]["available_at"] = future
    else:
        value["coverage"] = [dict(coverage_window_id="future", source_id="official", start_at=NOW,
            end_at=future, observed_at=future, status="unknown", reason_code="unobserved_between_polls")]
    with pytest.raises(ValueError, match="FUTURE_INPUT"):
        wire(value)


def test_future_cutoff_rejected_by_direct_envelope_json_import():
    from cfaw_news.intelligence.runtime_contracts import RuntimeEnvelope
    value = envelope()
    value["as_of"] = "2099-01-01T00:00:00Z"
    with pytest.raises(ValueError, match="FUTURE_INPUT"):
        RuntimeEnvelope.model_validate_json(json_bytes(value))


def test_fact_signature_symbols_numbers_units_bound():
    assert policy_sha256() == "70565148fe436fa823ef6a4063cbba7abb4c994cc34f19dc44bdc2451e367450"
    strings = ["Atlas latency <= 10 ms", "Atlas latency < 10 ms", "Atlas latency > 10 ms",
               "Atlas latency >= 10 ms", "Atlas latency <= 10 MS", "Atlas latency <= 11 ms"]
    assert len({persona_content(s) for s in strings}) == len(strings)


def test_budget_profile_changes_input_binding_but_not_event_namespace():
    a = envelope()
    b = deepcopy(a)
    b["config"]["budget"]["profile"] = "focus60-radar40-v1"
    raw, pin = wire(a)
    first = run(raw, expected_sha256=pin)
    raw, pin = wire(b)
    second = run(raw, expected_sha256=pin)
    assert first.input_sha256 != second.input_sha256
    assert first.stages[-1].grouping.next_state.namespace == second.stages[-1].grouping.next_state.namespace
    assert first.archive_snapshot_ids == second.archive_snapshot_ids


def test_cancel_and_deadline_no_returned_plan():
    raw, pin = wire(envelope())
    with pytest.raises(ValueError, match="CANCELLED"):
        run(raw, expected_sha256=pin, control=Control(cancelled=lambda: True))
    ticks = iter([0, 0, 2])
    with pytest.raises(ValueError, match="TIMEOUT"):
        run(raw, expected_sha256=pin, control=Control(timeout_seconds=1, clock=lambda: next(ticks)))
    control = Control()
    control.cancelled = lambda: "rule" in control.log
    with pytest.raises(ValueError, match="CANCELLED"):
        run(raw, expected_sha256=pin, control=control)


def test_long_input_rejected_before_execution():
    with pytest.raises(ValueError):
        wire(envelope(body="x" * 16001))


def test_source_windows_union_and_configured_empty_sources():
    value = envelope()
    value["versions"] = []
    value["coverage"] = [dict(coverage_window_id="point", source_id="official", start_at=NOW,
        end_at=NOW, observed_at=NOW, status="covered", reason_code="conditional_confirmed")]
    raw, pin = wire(value)
    result = run(raw, expected_sha256=pin)
    assert result.state == "evidence_not_ready" and result.coverage.has_gap
    assert result.plan.coverage.source_count == 1 and result.plan.coverage.has_gap
    assert result.coverage.sources[0].unobserved_intervals


def test_untrusted_history_and_old_rank_pin_cannot_enter_runtime():
    raw, pin = wire(envelope())
    result = run(raw, expected_sha256=pin)
    context = data(result.context)
    context["journal"]["entries"] = [dict(record_origin="synthetic")]
    from cfaw_news.intelligence.runtime_contracts import RuntimeHistoryInput, RuntimePlan
    with pytest.raises(ValueError):
        RuntimeHistoryInput.model_validate_json(json_bytes(context))
    plan = data(result.plan)
    plan["input"]["ranking"]["config_sha256"] = digest(RankingConfig())
    with pytest.raises(ValueError, match="RANKING_BINDING"):
        RuntimePlan.model_validate_json(json_bytes(plan))


def test_source_policy_revision_change_is_explicit_raw_downgrade():
    value = envelope()
    changed = source().model_dump(mode="json")
    changed["policy_revision"] = "authored-second-policy"
    value["sources"].append(changed)
    raw, pin = wire(value)
    result = run(raw, expected_sha256=pin)
    assert result.state == "raw_news_only" and result.plan is None and result.ranking is None
