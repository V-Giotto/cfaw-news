"""PR4 diagnostic repairs: time unions and canonical lexical query denominators."""

from datetime import datetime, timedelta
from functools import lru_cache
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from evals.intelligence_g2.contracts import data, digest, json_bytes
from evals.intelligence_g3.budget import _coverage, plan_briefing
from evals.intelligence_g3.budget_cli import export_plan
from evals.intelligence_g3.budget_contracts import BriefingPlan, BudgetConfig, BudgetInput
from evals.intelligence_g3.history_contracts import HistoryInput, parse_history
from evals.intelligence_g3.revisit import rank_revisit
from evals.intelligence_v1.contracts import CoverageWindow
from evals.intelligence_v1.exceptions import ContractError
from evals.intelligence_v1.hashing import sha256_bytes
from tests.evals.g2.pr2.support import sequence

from . import ranking_support
from .budget_support import coverage_case, pool_case, source
from .history_support import g3_tmp_path as g3_tmp_path


def probe(specs, *, point=False, candidates=True):
    """Pure interval unit tests with native windows and native source pointers."""
    replay = coverage_case("covered").replay
    start = replay.time_window_start
    source_id = replay.source_coverage[0].source_id
    windows = tuple(CoverageWindow(coverage_window_id=f"synthetic:window:{i}",
        source_id=source_id, start_at=start + timedelta(seconds=a),
        end_at=start + timedelta(seconds=b), observed_at=start + timedelta(seconds=300),
        status=status, reason=f"synthetic:{status}") for i, (a, b, status) in enumerate(specs))
    value = SimpleNamespace(source_coverage=windows,
        candidates=replay.candidates if candidates else (), time_window_start=start,
        time_window_end=start if point else start + timedelta(seconds=100))
    return value, _coverage(value)


def spans(raw, name, start):
    return [(int((datetime.fromisoformat(row["start_at"]) - start).total_seconds()),
             int((datetime.fromisoformat(row["end_at"]) - start).total_seconds())) for row in raw[name]]


@lru_cache
def native_interval_case(specs):
    """Run native G2 generation for a one-day query; no product outputs mocked."""
    documents = [dict(id="Atlas", body="Atlas Tool provides local execution.")]
    native = sequence([(1, documents)])[0]
    start, end = native.context.time_window_start, native.context.time_window_end
    windows = tuple(CoverageWindow(coverage_window_id=f"synthetic:interval:{i}",
        source_id=native.sources[0].source_id, start_at=start + timedelta(hours=a),
        end_at=start + timedelta(hours=b), observed_at=end, status=status,
        reason=f"synthetic:{status}") for i, (a, b, status) in enumerate(specs))
    raw_windows = [data(w) for w in windows]
    native = native.model_copy(update={"context": native.context.model_copy(
        update={"source_coverage": windows}), "source_coverage_digest": digest(raw_windows)})
    def bind(model, raw):
        raw["source_coverage"] = raw_windows
        raw["observations"][0].update(source_coverage=raw_windows,
                                    source_coverage_digest=digest(raw_windows))
        return parse_history(model, raw)
    with (patch.object(ranking_support, "sequence", return_value=(native,)),
          patch.object(ranking_support, "parse", side_effect=bind)):
        replay = ranking_support.native_replay([(1, documents)])
    return source(replay)


def test_reviewed_past_covered_window_does_not_cover_current_query():
    value = native_interval_case(((-48, -24, "covered"),))
    ranking = rank_revisit(value)
    plan = plan_briefing(value, ranking)
    assert plan.coverage.has_gap
    assert plan.coverage.effective_statuses == ("unknown",)
    assert plan.coverage.windows == value.replay.source_coverage
    assert plan.coverage.status_counts["covered"] == 1  # Raw history remains truthful.
    assert plan.input.history_input == value and plan.input.ranking == ranking


def test_reviewed_equivalent_interest_queries_have_one_denominator_unit():
    raw = data(pool_case())
    labels = ["local", "LOCAL", " local ", "unmatched"]
    raw["replay"]["persona"]["persona"]["domain_interests"] = labels
    value = parse_history(HistoryInput, raw)
    ranking = rank_revisit(value)
    before = json_bytes(value), json_bytes(ranking)
    plan = plan_briefing(value, ranking)
    assert plan.diagnostics.declared_domain_count == 2
    assert plan.diagnostics.presented_domain_count == 1
    assert plan.diagnostics.declared_domain_coverage == 0.5
    assert before == (json_bytes(value), json_bytes(ranking))
    assert list(plan.input.history_input.replay.persona.persona.domain_interests) == labels


@pytest.mark.parametrize("specs,status,confirmed,gaps,unobserved", [
    ((), "unknown", [], [(0, 100)], [(0, 100)]),
    (((-200, -100, "covered"),), "unknown", [], [(0, 100)], [(0, 100)]),
    (((-100, 0, "covered"), (100, 200, "covered")), "unknown", [], [(0, 100)], [(0, 100)]),
    (((50, 50, "covered"),), "unknown", [], [(0, 100)], [(0, 100)]),
    (((0, 40, "covered"),), "partial", [(0, 40)], [(40, 100)], [(40, 100)]),
    (((40, 100, "covered"),), "partial", [(40, 100)], [(0, 40)], [(0, 40)]),
    (((0, 40, "covered"), (60, 100, "covered")), "partial", [(0, 40), (60, 100)], [(40, 60)], [(40, 60)]),
    (((0, 40, "covered"), (40, 100, "covered")), "covered", [(0, 100)], [], []),
    (((0, 70, "covered"), (50, 100, "covered")), "covered", [(0, 100)], [], []),
    (((-50, 150, "covered"),), "covered", [(0, 100)], [], []),
    (((0, 100, "covered"), (20, 30, "covered")), "covered", [(0, 100)], [], []),
    (((0, 100, "covered"), (40, 60, "failed")), "partial", [(0, 40), (60, 100)], [(40, 60)], []),
    (((-100, 0, "failed"), (0, 100, "covered")), "covered", [(0, 100)], [], []),
    (((-100, 0, "covered"), (0, 100, "failed")), "failed", [], [(0, 100)], []),
])
def test_interval_union_clipping_holes_and_conservative_overlaps(specs, status, confirmed, gaps, unobserved):
    value, result = probe(specs)
    assert result["effective_statuses"] == [status]
    assert result["has_gap"] is (status != "covered")
    assert result["windows"] == [data(w) for w in value.source_coverage]
    assert result["window_count"] == len(specs) and result["source_count"] == 1
    actual = result["sources"][0]
    assert actual["status"] == status
    assert spans(actual, "confirmed_intervals", value.time_window_start) == confirmed
    assert spans(actual, "unconfirmed_intervals", value.time_window_start) == gaps
    assert spans(actual, "unobserved_intervals", value.time_window_start) == unobserved


@pytest.mark.parametrize("status", ["covered", "partial", "failed", "unknown", "service_offline"])
def test_explicit_window_status_is_not_overridden_by_time_union(status):
    value, result = probe(((0, 100, status),))
    assert result["effective_statuses"] == [status]
    assert result["sources"][0]["observed_statuses"] == [status]
    assert result["sources"][0]["segments"][0]["observed_statuses"] == [status]
    assert result["status_counts"][status] == 1
    assert spans(result["sources"][0], "unobserved_intervals", value.time_window_start) == []


@pytest.mark.parametrize("status", ["partial", "failed", "unknown", "service_offline"])
def test_overlapping_covered_window_cannot_erase_noncovered_observation(status):
    _, result = probe(((0, 100, "covered"), (0, 100, status)))
    assert result["effective_statuses"] == [status]
    assert result["sources"][0]["confirmed_intervals"] == []
    assert set(result["sources"][0]["observed_statuses"]) == {"covered", status}
    assert result["status_counts"]["covered"] == result["status_counts"][status] == 1


@pytest.mark.parametrize("specs,status", [
    (((0, 0, "covered"),), "covered"),
    (((-100, 0, "covered"),), "covered"),
    (((1, 100, "covered"),), "unknown"),
    (((0, 0, "failed"),), "failed"),
])
def test_zero_length_query_is_an_explicit_point_observation(specs, status):
    _, result = probe(specs, point=True)
    assert result["effective_statuses"] == [status]
    assert result["interval_policy"] == "half-open-duration-closed-point-v1"


def test_empty_pool_still_diagnoses_known_sources_and_unknown_source_universe():
    _, observed = probe(((-100, 0, "covered"),), candidates=False)
    assert observed["source_count"] == 1 and observed["effective_statuses"] == ["unknown"]
    _, absent = probe((), candidates=False)
    assert absent["sources"] == [] and absent["effective_statuses"] == ["unknown"]
    assert absent["has_gap"]


def test_source_ids_have_separate_effective_status_and_raw_counts():
    value, _ = probe(((0, 100, "covered"),))
    other = value.source_coverage[0].model_copy(update={"coverage_window_id": "other", "source_id": "other", "status": "failed"})
    value.source_coverage += (other,)
    result = _coverage(value)
    assert result["source_count"] == 2 and result["window_count"] == 2
    assert result["effective_statuses"] == ["covered", "failed"]
    assert {s["source_id"]: s["status"] for s in result["sources"]} == {
        value.source_coverage[0].source_id: "covered", "other": "failed"}


@pytest.mark.parametrize("labels,tokens", [
    (["local", "LOCAL"], ("local",)),
    (["local", " local ", "local"], ("local",)),
    (["local evaluation", "evaluation-local", "LOCAL evaluation"], ("evaluation", "local")),
    (["!!!", "---"], ()),
])
def test_canonical_domain_key_and_raw_label_provenance(labels, tokens):
    raw = data(pool_case())
    raw["replay"]["persona"]["persona"]["domain_interests"] = labels
    value = parse_history(HistoryInput, raw)
    plan = plan_briefing(value, rank_revisit(value))
    assert plan.diagnostics.declared_domain_count == 1
    domain = plan.diagnostics.domain_coverage[0]
    assert domain.query_tokens == tokens and domain.labels == tuple(labels)
    assert domain.domain_key == "g3:domain-query:" + digest(list(tokens))
    assert domain.input_refs == tuple(f"/history_input/replay/persona/persona/domain_interests/{i}" for i in range(len(labels)))
    if not tokens:
        assert domain.eligible_events == domain.presented_events == 0 and domain.ratio is None
        assert "empty_interest_query_unmatchable" in domain.reason_codes


def test_domain_identity_ignores_alias_order_without_modifying_ranking():
    keys = []
    for labels in (["local", "LOCAL", " local "], [" local ", "local", "LOCAL"]):
        raw = data(pool_case())
        raw["replay"]["persona"]["persona"]["domain_interests"] = labels
        value = parse_history(HistoryInput, raw)
        ranking = rank_revisit(value)
        plan = plan_briefing(value, ranking)
        keys.append(plan.diagnostics.domain_coverage[0].domain_key)
        assert plan.input.ranking == ranking
        assert plan.diagnostics.declared_domain_coverage == 1
    assert keys[0] == keys[1]


def test_no_declared_domains_has_an_explicit_empty_denominator():
    raw = data(pool_case())
    raw["replay"]["persona"]["persona"]["domain_interests"] = []
    value = parse_history(HistoryInput, raw)
    plan = plan_briefing(value, rank_revisit(value))
    assert plan.diagnostics.domain_coverage == ()
    assert plan.diagnostics.declared_domain_count == plan.diagnostics.presented_domain_count == 0
    assert plan.diagnostics.declared_domain_coverage is None


@pytest.mark.parametrize("field", ["domain_key", "labels", "query_tokens", "declared_domain_count"])
def test_wire_rejects_forged_canonical_domains_or_denominators(field):
    value = pool_case()
    raw = data(plan_briefing(value, rank_revisit(value)))
    if field == "declared_domain_count":
        raw["diagnostics"][field] = 99
    else:
        raw["diagnostics"]["domain_coverage"][0][field] = "forged" if field == "domain_key" else ["forged"]
    with pytest.raises((ValidationError, ContractError)):
        BriefingPlan.model_validate_json(json_bytes(raw))


@pytest.mark.parametrize("specs,status", [
    (((-48, -24, "covered"),), "unknown"),
    (((0, 12, "covered"),), "partial"),
    (((0, 8, "covered"), (16, 24, "covered")), "partial"),
    (((0, 12, "covered"), (12, 24, "covered")), "covered"),
])
def test_native_wire_and_pinned_cli_preserve_input_and_compute_interval_status(specs, status, g3_tmp_path):
    value = native_interval_case(specs)
    ranking = rank_revisit(value)
    before = json_bytes(value), json_bytes(ranking)
    plan = plan_briefing(value, ranking)
    assert plan.coverage.effective_statuses == (status,)
    assert BriefingPlan.model_validate_json(json_bytes(plan)) == plan
    path = g3_tmp_path / "input.json"
    path.write_bytes(json_bytes(plan.input))
    output = export_plan(path, input_sha256=sha256_bytes(path.read_bytes()), out=g3_tmp_path / "plan")
    assert output == plan
    assert before == (json_bytes(value), json_bytes(ranking))
    for row in plan.coverage.sources:
        for segment in row.segments:
            for pointer in segment.window_refs:
                index = int(pointer.rsplit("/", 1)[1])
                assert value.replay.source_coverage[index].source_id == row.source_id
    forged = data(plan)
    forged["coverage"]["sources"][0]["status"] = "failed" if status == "covered" else "covered"
    with pytest.raises((ValidationError, ContractError)):
        BriefingPlan.model_validate_json(json_bytes(forged))


def test_diagnostic_revision_is_registered_and_legacy_wire_is_not_silently_reinterpreted():
    value = pool_case()
    plan = plan_briefing(value, rank_revisit(value))
    assert plan.schema_revision == "g3-pr4-plan-v2"
    assert plan.input.schema_revision == "g3-pr4-input-v2"
    assert plan.input.config.config_revision == "g3-budget-v2"
    assert plan.input.config.reading_rule.revision == "unicode-display-units-v1"
    for cls, raw, revision in ((BudgetInput, data(plan.input), "g3-pr4-input-v1"),
                               (BriefingPlan, data(plan), "g3-pr4-plan-v1")):
        raw["schema_revision"] = revision
        with pytest.raises((ValidationError, ContractError)):
            cls.model_validate_json(json_bytes(raw))
    config = BudgetConfig().model_copy(update={"domains": "unregistered-canonicalization"})
    with pytest.raises((ValidationError, ContractError)):
        plan_briefing(value, rank_revisit(value), config)
