"""PR4 conservation, constraints, time boundaries, diagnostics and hostile wire inputs."""

import os
import subprocess
import sys
from copy import deepcopy

import pytest
from pydantic import ValidationError

from evals.intelligence_g2.contracts import data, digest, json_bytes
from evals.intelligence_g3.budget import PROFILES, display_units, estimates, plan_briefing
from evals.intelligence_g3.budget_cli import export_plan
from evals.intelligence_g3.budget_contracts import (
    BriefingPlan,
    BudgetConfig,
    BudgetInput,
    check_schemas,
)
from evals.intelligence_g3.contracts import PACKAGE, ROOT
from evals.intelligence_g3.history_contracts import HistoryInput, HistoryJournal
from evals.intelligence_g3.revisit import rank_revisit
from evals.intelligence_v1.exceptions import ContractError
from evals.intelligence_v1.hashing import sha256_bytes

from .budget_support import (
    coverage_case,
    long_case,
    long_update_case,
    pool_case,
    protected_case,
    source,
)
from .history_support import g3_tmp_path as g3_tmp_path
from .history_support import revisit_case, with_history
from .ranking_support import pool
from .support import Scenario


@pytest.mark.parametrize("budget", [180, 420, 900])
@pytest.mark.parametrize("profile", PROFILES)
def test_time_shares_conservation_full_ranking_and_archive_retention(budget, profile):
    value = pool_case(budget)
    ranking = rank_revisit(value)
    before = json_bytes(value), json_bytes(ranking)
    plan = plan_briefing(value, ranking, BudgetConfig(profile=profile))
    diag = plan.diagnostics
    assert diag.budget_seconds == budget
    assert diag.focus_target_seconds == budget * PROFILES[profile] // 100
    assert diag.radar_target_seconds + diag.focus_target_seconds == budget
    assert diag.focus_used_seconds <= diag.focus_target_seconds
    assert diag.radar_used_seconds <= diag.radar_target_seconds
    assert diag.used_seconds == sum(e.estimated_read_seconds for e in plan.events)
    assert diag.used_seconds + diag.unused_seconds == budget
    assert diag.utilization == diag.used_seconds / budget <= 1
    assert len(plan.events) == len(ranking.events) == len(value.replay.candidates) == 14
    assert [e.event_key for e in plan.events] == [e.event_key for e in ranking.events]
    assert plan.archive_snapshot_ids == tuple(e.snapshot_id for e in ranking.events)
    assert plan.input.history_input == value and plan.input.ranking == ranking
    assert before == (json_bytes(value), json_bytes(ranking))
    assert plan.ranking_sha256 == digest(ranking)
    if budget <= 420:
        assert any(e.tier == "focus" for e in plan.events)
        assert any(e.tier == "radar" for e in plan.events)
        assert any(e.status == "not_displayed" for e in plan.events)
    for event in plan.events:
        assert event.reasons
        if event.status == "not_displayed":
            assert event.tier is None and event.estimated_read_seconds == 0
            assert {r.code for r in event.reasons} >= {"focus_share_insufficient", "radar_share_insufficient"}


def test_ratio_configuration_changes_allocation_with_identical_stage_one_ranking():
    value = pool_case()
    ranking = rank_revisit(value)
    plans = [plan_briefing(value, ranking, BudgetConfig(profile=p)) for p in PROFILES]
    assert len({p.config_sha256 for p in plans}) == 3
    assert len({p.ranking_sha256 for p in plans}) == 1
    assert len({tuple((e.event_key, e.tier) for e in p.events) for p in plans}) > 1


def test_zero_candidates_zero_denominators_and_native_coverage_retained():
    value = HistoryInput(replay=Scenario("E10-negative").load(), journal=HistoryJournal())
    plan = plan_briefing(value, rank_revisit(value))
    assert plan.events == plan.display_order == plan.archive_snapshot_ids == ()
    assert plan.diagnostics.used_seconds == 0 and plan.diagnostics.unused_seconds == 420
    assert plan.diagnostics.event_breadth is None
    assert all(d.ratio is None for d in plan.diagnostics.domain_coverage)
    assert plan.coverage.windows == value.replay.source_coverage
    assert plan.coverage.interpretation == "coverage_observations_never_confirm_no_updates"


def test_single_overlong_native_eligible_candidate_is_explicitly_unshown_not_deleted():
    value = long_case()
    ranking = rank_revisit(value)
    assert ranking.events[0].eligible and value.replay.candidates[0].rule_item.tier_candidate == "focus"
    plan = plan_briefing(value, ranking)
    event = plan.events[0]
    assert event.estimates[-1].seconds == 199 > 180
    assert event.status == "not_displayed" and event.tier is None
    assert "minimum_exceeds_total_budget" in {r.code for r in event.reasons}
    assert plan.input.history_input.replay.candidates == value.replay.candidates
    assert len(plan.archive_snapshot_ids) == 1 and plan.diagnostics.used_seconds == 0


@pytest.mark.parametrize("length,seconds,shown", [(86, 125, True), (87, 126, True), (88, 127, False)])
def test_one_second_focus_boundary_and_safe_whole_block_truncation(length, seconds, shown):
    value = long_case(length)
    plan = plan_briefing(value, rank_revisit(value))
    event = plan.events[0]
    assert event.estimates[-1].seconds == seconds
    assert (event.tier == "focus") is shown
    if shown:
        assert event.status == "truncated" and event.estimated_read_seconds == seconds
        assert event.chosen_projection == "minimum"
        assert any(r.endswith("/what_happened") for r in event.omitted_refs)
        assert all(r.endswith(("/what_happened", "/why_it_matters")) for r in event.omitted_refs)
        assert any("/claim_summaries/" in r for r in event.content_refs)
        assert any("/risks/" in r for r in event.content_refs)
        assert plan.diagnostics.truncated_event_keys == (event.event_key,)
    else:
        assert event.status == "not_displayed" and event.estimated_read_seconds == 0
        assert plan.diagnostics.not_displayed_event_keys == (event.event_key,)


def test_budget_is_variable_text_cost_not_g2_legacy_fixed_item_seconds():
    short, long = long_case(20), long_case(100)
    a, b = (estimates(v.replay.candidates[0], 0) for v in (short, long))
    assert short.replay.candidates[0].rule_item.estimated_read_seconds == 90
    assert long.replay.candidates[0].rule_item.estimated_read_seconds == 90
    assert [e.seconds for e in a] == [85, 77, 59]
    assert [e.seconds for e in b] == [205, 197, 139]
    assert plan_briefing(short, rank_revisit(short)).diagnostics.presented_event_count == 1
    assert plan_briefing(long, rank_revisit(long)).diagnostics.presented_event_count == 0


@pytest.mark.parametrize("length,seconds,shown", [(140, 179, True), (141, 180, True), (142, 181, False)])
def test_total_budget_boundary_for_protected_mandatory_content(length, seconds, shown):
    value = long_update_case(length)
    ranking = rank_revisit(value)
    assert ranking.events[0].protected
    plan = plan_briefing(value, ranking)
    event = plan.events[0]
    assert event.estimates[-1].seconds == seconds
    assert (event.tier == "focus") is shown
    assert plan.diagnostics.used_seconds == (seconds if shown else 0)
    if shown:
        assert event.status == "truncated"
        assert plan.diagnostics.unused_seconds == 180 - seconds
        assert plan.diagnostics.unmet_protected_event_keys == ()
    else:
        assert event.status == "not_displayed"
        assert plan.diagnostics.unmet_protected_event_keys == (event.event_key,)


@pytest.mark.parametrize("text,units", [
    ("", 0), ("local execution", 2), ("中文 mixed words 42", 5),
    ("a-b; c.d", 4), ("cafe\u0301", 1), ("\U00020000汉A汉B", 5),
])
def test_registered_unicode_reading_units(text, units):
    assert display_units(text) == units


@pytest.mark.parametrize("algorithm", ["b0", "b1", "b2", "b3", "b4", "p1"])
def test_ties_and_all_algorithms_keep_original_complete_order(algorithm):
    value = pool_case()
    ranking = rank_revisit(value, algorithm)
    assert len({r.score for r in ranking.events}) == 1
    plan = plan_briefing(value, ranking)
    assert [e.event_key for e in plan.events] == [e.event_key for e in ranking.events]
    assert [r.event_key for r in ranking.events] == sorted(r.event_key for r in ranking.events)
    assert json_bytes(plan) == json_bytes(plan_briefing(value, ranking))


@pytest.mark.parametrize("algorithm", ["b0", "p1"])
def test_protected_correction_withdrawal_precede_newer_ordinary_and_borrow_share(algorithm):
    value = protected_case()
    ranking = rank_revisit(value, algorithm)
    if algorithm == "b0":
        assert not ranking.events[0].protected
    plan = plan_briefing(value, ranking)
    updates = [e for e in plan.events if e.protected]
    assert len(updates) == 2
    assert {r.history.promotion for r in ranking.events if r.protected} == {"correction", "withdrawal"}
    assert all(e.tier == "focus" for e in updates)
    assert set(plan.display_order[:2]) == {e.event_key for e in updates}
    assert plan.diagnostics.protected_borrowed_seconds > 0
    assert plan.diagnostics.used_seconds <= 180
    assert plan.diagnostics.unmet_protected_event_keys == ()
    assert plan.input.ranking == ranking


def test_impossible_protected_budget_is_diagnosed_without_overrun_or_false_display():
    value = protected_case(3)
    plan = plan_briefing(value, rank_revisit(value))
    assert plan.diagnostics.unmet_protected_event_keys
    for event in plan.events:
        if event.event_key in plan.diagnostics.unmet_protected_event_keys:
            assert event.status == "not_displayed" and event.tier is None
            assert "protected_budget_unmet" in {r.code for r in event.reasons}
    assert plan.diagnostics.used_seconds <= 180


@pytest.mark.parametrize("mode", ["correction", "withdrawal", "material"])
def test_pending_update_survives_opened_history_without_altering_ranker(mode):
    value = with_history(revisit_case(7, mode), ("rendered", "opened"))
    ranking = rank_revisit(value)
    plan = plan_briefing(value, ranking)
    assert plan.events[0].protected and plan.events[0].tier == "focus"
    assert ranking.events[0].features.duplicate.value == 0
    assert not ranking.events[0].history.declared_known


def test_hold_and_evidence_gates_survive_exploration_and_remain_archivable():
    value = source(pool())
    ranking = rank_revisit(value)
    plan = plan_briefing(value, ranking)
    blocked = [e for e in plan.events if e.status == "constraint_excluded"]
    assert len(blocked) == 1
    event = blocked[0]
    assert {r.code for r in event.reasons} >= {"g2_hold", "g2_evidence_insufficient", "no_cited_attributed_claim"}
    assert event.estimated_read_seconds == 0 and event.event_key not in plan.display_order
    assert event.snapshot_id in plan.archive_snapshot_ids
    assert plan.input.ranking.events[-1].features.exploration.value == 0
    assert plan.diagnostics.eligible_event_count == 2


@pytest.mark.parametrize("status", ["covered", "partial", "failed", "unknown", "service_offline"])
def test_source_coverage_statuses_remain_independent_diagnostics(status):
    value = coverage_case(status)
    plan = plan_briefing(value, rank_revisit(value))
    assert plan.coverage.status_counts[status] == plan.coverage.window_count == 1
    assert plan.coverage.windows == value.replay.source_coverage
    assert plan.coverage.effective_statuses == (status,)
    assert plan.coverage.has_gap is (status != "covered")
    assert plan.coverage.missing_source_ids == ()
    assert plan.coverage.interpretation == "coverage_observations_never_confirm_no_updates"
    assert len(plan.display_order) == len(plan.events) == 1


@pytest.mark.parametrize("budget", [0, 181, 419, 901])
def test_unregistered_attention_budget_is_rejected_before_planning(budget):
    with pytest.raises((ValidationError, ContractError)):
        source(pool(), budget)


def test_missing_coverage_is_unknown_without_inventing_an_observation():
    value = pool_case()
    plan = plan_briefing(value, rank_revisit(value))
    assert plan.coverage.windows == () and plan.coverage.window_count == 0
    assert plan.coverage.effective_statuses == ("unknown",) and plan.coverage.has_gap
    assert len(plan.coverage.missing_source_ids) == 14
    assert sum(plan.coverage.status_counts.values()) == 0


def test_domain_and_event_breadth_denominators_are_explicit():
    value = pool_case()
    plan = plan_briefing(value, rank_revisit(value))
    diag = plan.diagnostics
    assert diag.eligible_event_count == 14
    assert diag.event_breadth == len(plan.display_order) / 14
    domains = {d.domain: d for d in diag.domain_coverage}
    assert domains["local"].eligible_events == domains["evaluation"].eligible_events == 14
    assert domains["local"].presented_events == len(plan.display_order)
    assert domains["unmatched"].eligible_events == 0 and domains["unmatched"].ratio is None
    assert diag.declared_domain_count == 3 and diag.presented_domain_count == 2
    assert diag.declared_domain_coverage == 2 / 3
    assert diag.breadth_unit == "unique_g2_event_keys_not_independent_research_samples"


def test_every_projection_and_reason_pointer_resolves_to_complete_native_input():
    value = long_case(87)
    plan = plan_briefing(value, rank_revisit(value))
    raw = data(plan.input)
    for event in plan.events:
        pointers = [*event.content_refs, *event.omitted_refs]
        pointers += [p for e in event.estimates for p in (*e.content_refs, *e.omitted_refs)]
        pointers += [p for reason in event.reasons for p in reason.input_refs]
        for pointer in pointers:
            current = raw
            for token in pointer.split("/")[1:]:
                current = current[int(token)] if isinstance(current, list) else current[token]


@pytest.mark.parametrize("mutation", ["drop", "duplicate", "budget", "persona", "pool", "eligibility", "protection", "order"])
def test_direct_wire_and_planner_reject_unbound_or_incomplete_ranking(mutation):
    value = source(pool())
    ranking = rank_revisit(value)
    raw = dict(history_input=data(value), ranking=data(ranking), config=data(BudgetConfig()))
    if mutation == "drop":
        raw["ranking"]["events"].pop()
    elif mutation == "duplicate":
        raw["ranking"]["events"][0] = deepcopy(raw["ranking"]["events"][1])
    elif mutation == "budget":
        raw["ranking"]["attention_budget_seconds"] = 900
    elif mutation == "persona":
        raw["ranking"]["persona_version_id"] = "unbound"
    elif mutation == "pool":
        raw["ranking"]["candidate_pool_sha256"] = "0" * 64
    elif mutation == "eligibility":
        raw["ranking"]["events"][-1]["eligible"] = True
    elif mutation == "protection":
        raw["ranking"]["events"][0]["protected"] = True
    else:
        raw["ranking"]["events"].reverse()
        for i, row in enumerate(raw["ranking"]["events"], 1):
            row["rank"] = i
    with pytest.raises((ValidationError, ContractError)):
        BudgetInput.model_validate_json(json_bytes(raw))
    # The stage-one wire model alone cannot bind its rows to a separate input.
    # The public planner must perform that binding even for copied model objects.
    from evals.intelligence_g3.revisit import RevisitResult
    corrupted = RevisitResult.model_validate_json(json_bytes(raw["ranking"])).model_copy()
    with pytest.raises((ValidationError, ContractError)):
        plan_briefing(value, corrupted)


@pytest.mark.parametrize("mutation", ["events", "archive", "coverage", "utilization", "display", "content", "reason"])
def test_serialized_final_plan_rejects_removed_rows_and_false_diagnostics(mutation):
    value = pool_case()
    plan = plan_briefing(value, rank_revisit(value))
    assert BriefingPlan.model_validate_json(json_bytes(plan)) == plan
    raw = data(plan)
    if mutation == "events":
        raw["events"].pop()
    elif mutation == "archive":
        raw["archive_snapshot_ids"].pop()
    elif mutation == "coverage":
        raw["coverage"]["effective_statuses"] = ["covered"]
    elif mutation == "utilization":
        raw["diagnostics"]["used_seconds"] = 0
    elif mutation == "display":
        raw["display_order"] = []
    elif mutation == "content":
        raw["events"][0]["content_refs"] = []
    else:
        raw["events"][0]["reasons"] = []
    with pytest.raises((ValidationError, ContractError)):
        BriefingPlan.model_validate_json(json_bytes(raw))


@pytest.mark.parametrize("change", [
    {"profile": "arbitrary-99-1"}, {"config_revision": "g3-budget-v0"},
    {"reading_rule": {"units_per_second": 100}}, {"unused_share": "borrow-everything"},
])
def test_unregistered_budget_policy_and_estimator_rejected(change):
    value = pool_case()
    config = BudgetConfig.model_construct(**{**data(BudgetConfig()), **change})
    with pytest.raises((ValidationError, ContractError)):
        plan_briefing(value, rank_revisit(value), config)


def test_planner_never_invokes_ranker_or_reads_quality_labels(monkeypatch):
    value = pool_case()
    ranking = rank_revisit(value)
    def forbidden(*args, **kwargs):
        raise AssertionError("stage two must not rerank")
    monkeypatch.setattr("evals.intelligence_g3.revisit.rank_revisit", forbidden)
    monkeypatch.setattr("evals.intelligence_g3.rankers.rank", forbidden)
    plan = plan_briefing(value, ranking)
    assert plan.input.ranking == ranking


def test_pinned_cli_export_fresh_paths_and_schemas(g3_tmp_path):
    value = long_case(87)
    plan = plan_briefing(value, rank_revisit(value))
    input_path = g3_tmp_path / "input.json"
    input_path.write_bytes(json_bytes(plan.input))
    out = g3_tmp_path / "export"
    result = export_plan(input_path, input_sha256=sha256_bytes(input_path.read_bytes()), out=out)
    assert result == plan
    assert (out / "input.json").read_bytes() == input_path.read_bytes()
    assert (out / "briefing_plan.json").read_bytes() == json_bytes(plan)
    with pytest.raises(FileExistsError):
        export_plan(input_path, input_sha256=sha256_bytes(input_path.read_bytes()), out=out)
    with pytest.raises(ContractError, match="G3_SHA_MISMATCH"):
        export_plan(input_path, input_sha256="0" * 64, out=g3_tmp_path / "bad")
    assert not (g3_tmp_path / "bad").exists()
    with pytest.raises(ContractError, match="G3_PATH_INVALID"):
        export_plan(input_path, input_sha256=sha256_bytes(input_path.read_bytes()), out=ROOT / ".tmp/unsafe-budget")
    assert check_schemas()
    assert data(BudgetConfig()) in __import__("json").loads(
        (PACKAGE / "manifests/pr4_budget_configs.json").read_bytes())["configs"]


def test_hash_seed_determinism_across_processes(g3_tmp_path):
    value = long_case(87)
    plan = plan_briefing(value, rank_revisit(value))
    input_path = g3_tmp_path / "seed-input.json"
    input_path.write_bytes(json_bytes(plan.input))
    code = ("import sys;from evals.intelligence_g3.budget_cli import export_plan;"
            "from evals.intelligence_g2.contracts import digest;"
            "print(digest(export_plan(sys.argv[1],input_sha256=sys.argv[2],out=sys.argv[3])))")
    hashes = []
    for seed in ("1", "7"):
        run = subprocess.run([sys.executable, "-B", "-c", code, str(input_path),
            sha256_bytes(input_path.read_bytes()), str(g3_tmp_path / seed)], cwd=ROOT,
            env={**os.environ, "PYTHONHASHSEED": seed, "PYTHONPATH": str(ROOT / "backend")},
            capture_output=True, text=True, timeout=60)
        assert run.returncode == 0, run.stderr
        hashes.append(run.stdout.strip())
    assert hashes == [digest(plan)] * 2
