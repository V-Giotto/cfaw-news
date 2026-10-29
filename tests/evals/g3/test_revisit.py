"""Synthetic 1/3/7-day adversarial revisit cases; no quality or user-effect claims."""

from contextlib import ExitStack
from datetime import timedelta
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from evals.intelligence_g2.contracts import data, digest, json_bytes
from evals.intelligence_g3.contracts import G3ReplayInput
from evals.intelligence_g3.history import append_event, select_history
from evals.intelligence_g3.history_contracts import HistoryInput, HistoryJournal, HistoryMapping
from evals.intelligence_g3.history_contracts import parse_history as parse
from evals.intelligence_g3.rankers import rank
from evals.intelligence_g3.revisit import compare_revisit, rank_revisit
from evals.intelligence_v1.exceptions import ContractError

from .history_support import (
    add_current_delivery,
    all_old_deliveries,
    event_for,
    identity_case,
    mappings_for,
    revisit_case,
    with_history,
)
from .history_support import g3_tmp_path as g3_tmp_path
from .ranking_support import SPECS, delivered, native_replay, pool
from .support import Scenario


def target_row(result, value):
    key = value.replay.deliveries[0].items[0].event_key
    return next(e for e in result.events if e.event_key == key)


@pytest.mark.parametrize("days", [1, 3, 7])
@pytest.mark.parametrize("kind,penalty,known", [
    ("included", .1, False), ("rendered", .2, False), ("opened", .1, False),
    ("acknowledged", .35, True), ("dismissed", .3, False)])
def test_revisit_distinguishes_exposure_from_explicit_knowledge(days, kind, penalty, known):
    value = with_history(revisit_case(days), (kind,))
    row = target_row(rank_revisit(value), value)
    assert row.history.declared_known is known
    assert row.features.novelty.value == (0 if known else 1)
    assert row.features.duplicate.value == pytest.approx(penalty)
    assert set(row.features.exposure_signals) == {"included", kind}
    assert not row.protected and row.history.promotion == "none"
    assert any(p.startswith("/journal/entries/") for p in row.history.input_refs)


@pytest.mark.parametrize("feedback,known,penalty", [
    ("known", True, .35), ("not_known", False, .1),
    ("helpful", False, .1), ("irrelevant", False, .3)])
def test_only_known_feedback_declares_knowledge(feedback, known, penalty):
    value = with_history(revisit_case(), ())
    journal = append_event(value.journal, event_for(value.replay, "feedback", feedback=feedback))
    value = HistoryInput(replay=value.replay, journal=journal)
    row = target_row(rank_revisit(value), value)
    assert row.history.declared_known is known
    assert row.features.duplicate.value == pytest.approx(penalty)


def test_retraction_and_replacement_append_without_rewriting_the_old_acknowledgment():
    value = with_history(revisit_case(), ("acknowledged",))
    original = json_bytes(value.journal.entries[0])
    assert target_row(rank_revisit(value), value).history.declared_known
    event = event_for(value.replay, "retract", interaction_id="retraction",
                      retracts_id="interaction:0", available_at=value.replay.as_of)
    journal = append_event(value.journal, event)
    value = HistoryInput(replay=value.replay, journal=journal)
    row = target_row(rank_revisit(value), value)
    assert not row.history.declared_known
    assert row.features.duplicate.value == .1
    assert json_bytes(journal.entries[0]) == original
    assert "/journal/entries/1" in row.history.input_refs
    replacement = event_for(value.replay, "feedback", feedback="known", interaction_id="replacement",
                            available_at=value.replay.as_of)
    journal = append_event(journal, replacement)
    assert target_row(rank_revisit(HistoryInput(replay=value.replay, journal=journal)), value).history.declared_known


@pytest.mark.parametrize("retracts", ["missing", "interaction:0"])
def test_retraction_cannot_remove_passive_exposure(retracts):
    value = with_history(revisit_case(), ("rendered",))
    with pytest.raises(ContractError, match="G3_HISTORY_INVALID"):
        append_event(value.journal, event_for(value.replay, "retract", interaction_id="r", retracts_id=retracts))


@pytest.mark.parametrize("days", [1, 3, 7])
@pytest.mark.parametrize("mode", ["material", "correction", "withdrawal"])
def test_supported_changes_override_acknowledged_and_dismissed_repeat_penalties(days, mode):
    value = with_history(revisit_case(days, mode), ("rendered", "acknowledged", "dismissed"))
    rows = rank_revisit(value).events
    assert len(rows) == 1
    row = rows[0]
    assert row.eligible and row.protected
    assert row.features.duplicate.value == 0 and row.features.material_change.value == 1
    assert row.features.novelty.value == 1 and not row.history.declared_known
    assert row.history.promotion == {"material": "material_change"}.get(mode, mode)
    assert row.history.reason_codes
    assert any("/observations/0/" in p for p in row.history.input_refs)


@pytest.mark.parametrize("days", [1, 3, 7])
def test_revision_update_and_reprints_keep_identity_and_no_material_change(days):
    value = with_history(revisit_case(days, "reprint"), ("acknowledged",))
    current, old = value.replay.candidates[0], value.replay.observations[0].candidates[0]
    assert current.event.event_key == old.event.event_key
    assert current.event.event_revision != old.event.event_revision
    row = rank_revisit(value).events[0]
    assert not row.protected and row.features.material_change.value == 0
    assert row.history.declared_known and row.features.duplicate.value == pytest.approx(.35)
    assert row.history.delivery_count == 1
    assert any(s.endswith(":exact_event_revision") for s in row.history.mapping_statuses)
    assert all(s.independence == "unknown" for s in current.bundle.lineage)


@pytest.mark.parametrize("mode", ["correction", "withdrawal", "material"])
def test_pending_change_stays_protected_after_included_rendered_opened_until_acknowledged(mode):
    value = with_history(revisit_case(3, mode), ("acknowledged",))
    raw = data(value.replay)
    current = data(delivered(value.replay, (), observation=1).deliveries[0])
    current["delivery"]["delivery_id"] = "current:delivery"
    raw["deliveries"].append(current)
    replay = parse(G3ReplayInput, raw)
    journal = value.journal
    for index, kind in enumerate(("included", "rendered", "opened")):
        journal = append_event(journal, event_for(replay, kind, interaction_id=f"current:{index}",
                                                  delivery_index=1))
    row = rank_revisit(HistoryInput(replay=replay, journal=journal)).events[0]
    assert row.protected and row.features.duplicate.value == 0
    journal = append_event(journal, event_for(replay, "acknowledged", interaction_id="ack:new", delivery_index=1))
    row = rank_revisit(HistoryInput(replay=replay, journal=journal)).events[0]
    assert row.history.declared_known and not row.protected
    assert row.features.duplicate.value > 0


@pytest.mark.parametrize("stage", ["merge", "split"])
@pytest.mark.parametrize("certainty", ["missing", "uncertain", "confirmed"])
def test_native_merge_split_history_requires_explicit_auditable_mapping(stage, certainty):
    replay = all_old_deliveries(identity_case(stage))
    journal = HistoryJournal()
    for i in range(len(replay.deliveries)):
        journal = append_event(journal, event_for(replay, "acknowledged", interaction_id=f"ack:{i}", delivery_index=i))
    mappings = () if certainty == "missing" else mappings_for(replay, certainty)
    assert mappings or certainty == "missing"
    value = HistoryInput(replay=replay, journal=journal, mappings=mappings)
    result = rank_revisit(value)
    if certainty != "confirmed":
        for row in result.events:
            assert not row.history.declared_known and row.features.duplicate.value == 0
            assert "uncertain_history_no_inherited_knowledge_or_penalty" in row.history.reason_codes
            assert any(s.endswith(":missing_explicit_mapping") or s.endswith(":uncertain_mapping")
                       for s in row.history.mapping_statuses)
    else:
        assert all(row.history.resolved_snapshot_ids for row in result.events)
        assert all(any(p.startswith("/mappings/") for p in row.history.input_refs) for row in result.events)
        assert all(any(s.endswith(":explicit_g2_lineage") for s in row.history.mapping_statuses) for row in result.events)
        # Parent acknowledgment cannot declare additional merged/split statements known.
        assert all(not row.history.declared_known for row in result.events)


@pytest.mark.parametrize("mutation", ["id", "revision", "path", "future", "certainty", "duplicate"])
def test_mapping_wire_model_rejects_forged_or_ambiguous_native_bindings(mutation):
    replay = all_old_deliveries(identity_case())
    raw = data(HistoryInput(replay=replay, journal=HistoryJournal(), mappings=mappings_for(replay)))
    mapping = raw["mappings"][0]
    if mutation == "id":
        mapping["transition_ids"] = ["not:a:transition"]
    elif mutation == "revision":
        mapping["from_target"]["event_revision"] = "0" * 64
    elif mutation == "path":
        mapping["transition_ids"] = [replay.identity_state.transitions[0].transition_id]
    elif mutation == "future":
        mapping["available_at"] = (replay.as_of + timedelta(seconds=1)).isoformat()
    elif mutation == "certainty":
        mapping["certainty"] = "inferred_from_title"
    else:
        raw["mappings"].append({**mapping, "mapping_id": "duplicate:pair"})
    with pytest.raises(ValidationError):
        HistoryInput.model_validate_json(json_bytes(raw))


def test_unrelated_old_event_is_not_silently_merged_into_current_event():
    value = with_history(native_replay([(0, SPECS[:2]), (3, [SPECS[1]])]), ("acknowledged",))
    row = rank_revisit(value).events[0]
    assert not row.history.declared_known and not row.history.resolved_snapshot_ids
    assert row.features.duplicate.value == 0
    assert "unmapped_history_preserved_without_identity_inference" in row.history.reason_codes


def test_repeated_deliveries_increase_capped_penalty_but_repeated_log_signals_do_not():
    value = with_history(revisit_case(), ("rendered", "rendered", "rendered"))
    row = rank_revisit(value).events[0]
    assert row.features.duplicate.value == .2
    raw = data(value.replay)
    for i in range(20):
        copy = data(value.replay.deliveries[0])
        copy["delivery"]["delivery_id"] = f"extra:{i}"
        raw["deliveries"].append(copy)
    replay = parse(G3ReplayInput, raw)
    row = rank_revisit(HistoryInput(replay=replay, journal=value.journal)).events[0]
    assert row.history.delivery_count == 21 and row.features.duplicate.value == .75


@pytest.mark.parametrize("algorithm", ["b0", "b1", "b2", "b3", "b4", "p1"])
def test_hard_constraints_and_same_pool_immutability_determinism(algorithm):
    value = with_history(pool(), ("acknowledged",))
    original = json_bytes(value)
    result = rank_revisit(value, algorithm)
    assert result == rank_revisit(value, algorithm)
    assert json_bytes(value) == original
    assert {r.event_key for r in result.events} == {c.event.event_key for c in value.replay.candidates}
    assert not result.events[-1].eligible and not result.events[-1].protected
    assert result.algorithm_version == f"g3-{algorithm}-revisit-v1"
    assert result.input_sha256 == digest(value)
    if algorithm in {"b0", "b1", "b2", "b3"}:
        assert [(r.event_key, r.score) for r in result.events] == [
            (r.event_key, r.score) for r in rank(value.replay, algorithm).events]


def test_all_algorithms_bind_same_context_budget_history_and_config():
    value = with_history(revisit_case(), ("rendered",))
    results = compare_revisit(value)
    assert len({r.comparison_sha256 for r in results}) == 1
    for budget in (180, 420, 900):
        raw = data(value)
        raw["replay"]["attention_budget_seconds"] = budget
        changed = compare_revisit(parse(HistoryInput, raw))
        assert len({r.comparison_sha256 for r in changed}) == 1
        if budget != value.replay.attention_budget_seconds:
            assert changed[0].comparison_sha256 != results[0].comparison_sha256


def test_feature_and_constraint_pointers_resolve_and_scores_reconstruct():
    value = with_history(revisit_case(7, "correction"), ("rendered", "acknowledged"))
    raw = data(value)
    for result in compare_revisit(value):
        for row in result.events:
            assert row.score == pytest.approx(sum(c.contribution for c in row.components), abs=1e-5)
            refs = [*row.history.input_refs, *row.constraint_input_refs]
            for feature in (row.features.bm25, row.features.relevance, row.features.novelty,
                            row.features.material_change, row.features.recency, row.features.duplicate,
                            row.features.exploration):
                refs.extend(feature.input_refs)
            for pointer in refs:
                current = raw
                for token in pointer.split("/")[1:]:
                    current = current[int(token)] if isinstance(current, list) else current[token]


def test_unknown_coverage_does_not_claim_no_updates_and_empty_pool_retains_diagnostics():
    value = with_history(revisit_case())
    row = rank_revisit(value).events[0]
    assert row.history.coverage_statuses == ("unknown",)
    assert "coverage_gap_no_claim_of_no_updates" in row.history.reason_codes
    empty = HistoryInput(replay=Scenario("E10-negative").load(), journal=HistoryJournal())
    result = rank_revisit(empty)
    assert result.events == () and "coverage_gaps_do_not_mean_no_world_change" in result.diagnostics


def test_future_journal_poison_has_identical_selected_input_and_predictions():
    value = with_history(revisit_case(), ("opened",))
    future = event_for(value.replay, "acknowledged", interaction_id="future",
                       available_at=value.replay.as_of + timedelta(days=1))
    poisoned = append_event(value.journal, future)
    selected = select_history(value.replay, poisoned)
    assert selected == value
    assert rank_revisit(selected) == rank_revisit(value)
    forged = value.model_copy(update={"journal": poisoned})
    with pytest.raises(ContractError, match="G3_FUTURE_HISTORY"):
        rank_revisit(forged)


def test_prediction_performs_no_file_network_subprocess_or_label_reads():
    value = with_history(revisit_case(3, "withdrawal"), ("acknowledged",))
    rank_revisit(value)  # Warm Python's standard-library lazy imports before the IO guard.

    def denied(*args, **kwargs):
        raise AssertionError("prediction attempted IO")

    with ExitStack() as stack:
        for name in ("builtins.open", "io.open", "os.open", "pathlib.Path.read_bytes",
                     "pathlib.Path.read_text", "socket.socket", "socket.create_connection", "subprocess.Popen"):
            stack.enter_context(patch(name, denied))
        assert rank_revisit(value).events[0].protected


def test_mapping_schema_does_not_allow_implicit_confidence_or_unknown_fields():
    mapping = mappings_for(all_old_deliveries(identity_case()))[0]
    with pytest.raises(ContractError):
        parse(HistoryMapping, {**data(mapping), "implicit_persona": "learned"})


@pytest.mark.parametrize("algorithm", ["b4", "p1"])
def test_protected_correction_precedes_higher_scored_ordinary_event(algorithm, monkeypatch):
    from evals.intelligence_g2.contracts import read_json
    from evals.intelligence_g3.contracts import PACKAGE

    specs = read_json((PACKAGE / "fixtures/pr3/v1/scenarios.json").read_bytes())
    replay = all_old_deliveries(native_replay([(0, [*specs["initial"], SPECS[1]]),
        (3, [*specs["updates"]["correction"], SPECS[1]])]))
    correction = next(c.event.event_key for c in replay.candidates if "official:2" in c.event.member_doc_version_ids)
    journal = HistoryJournal()
    for i in range(len(replay.deliveries)):
        if replay.deliveries[i].items[0].event_key == correction:
            journal = append_event(journal, event_for(replay, "acknowledged", interaction_id=f"ack:{i}", delivery_index=i))
    monkeypatch.setattr("evals.intelligence_g3.rankers.candidate_scores", lambda *args:
        {c.event.event_key: 0 if c.event.event_key == correction else 1e9 for c in replay.candidates})
    result = rank_revisit(HistoryInput(replay=replay, journal=journal), algorithm)
    assert result.events[0].protected and result.events[0].event_key == correction
    assert result.events[0].score < result.events[1].score


def test_metadata_revision_without_statement_delta_does_not_reset_knowledge():
    from evals.intelligence_g2.contracts import read_json
    from evals.intelligence_g3.contracts import PACKAGE

    start = read_json((PACKAGE / "fixtures/pr3/v1/scenarios.json").read_bytes())["initial"]
    value = with_history(native_replay([(0, start), (3, [{**start[0], "version": 2,
        "title": "Atlas Tool v1.0 release metadata updated"}])]), ("acknowledged",))
    assert value.replay.candidates[0].event.event_revision != value.replay.observations[0].candidates[0].event.event_revision
    row = rank_revisit(value).events[0]
    assert row.history.declared_known and not row.protected
    assert row.features.duplicate.value == pytest.approx(.35)


def test_pinned_export_roundtrip_and_no_overwrite_or_bad_pin_output(g3_tmp_path):
    from evals.intelligence_g3.revisit_cli import export_revisit
    from evals.intelligence_v1.hashing import sha256_bytes

    value = with_history(revisit_case(7, "withdrawal"), ("acknowledged",))
    source = g3_tmp_path / "history-input.json"
    source.write_bytes(json_bytes(value))
    pin = sha256_bytes(source.read_bytes())
    output = g3_tmp_path / "out"
    first = export_revisit(source, input_sha256=pin, out=output)
    assert first == rank_revisit(value)
    assert (output / "input.json").read_bytes() == source.read_bytes()
    assert (output / "ranking.json").read_bytes() == json_bytes(first)
    with pytest.raises(FileExistsError):
        export_revisit(source, input_sha256=pin, out=output)
    with pytest.raises(ContractError, match="G3_SHA_MISMATCH"):
        export_revisit(source, input_sha256="0" * 64, out=g3_tmp_path / "invalid")
    assert not (g3_tmp_path / "invalid").exists()


@pytest.mark.parametrize("negative_first", [True, False])
def test_unretracted_not_known_vetoes_conflicting_known_in_any_arrival_order(negative_first):
    value = with_history(revisit_case(7), ())
    replay, journal = value.replay, value.journal
    for i, feedback in enumerate(("not_known", "known") if negative_first else ("known", "not_known")):
        event = event_for(replay, "feedback", interaction_id=feedback, feedback=feedback,
                          available_at=replay.deliveries[0].available_at + timedelta(days=i + 1))
        # Acknowledgment can arrive late: occurrence and availability need not coincide.
        if feedback == "known":
            event = event.model_copy(update={"occurred_at": replay.deliveries[0].available_at})
        journal = append_event(journal, event)
    row = rank_revisit(HistoryInput(replay=replay, journal=journal)).events[0]
    assert not row.history.declared_known
    assert row.features.novelty.value == 1
    assert row.features.duplicate.value == .1  # Ineffective known signals add no penalty.
    retraction = event_for(replay, "retract", interaction_id="retract:not_known", retracts_id="not_known",
                           available_at=replay.as_of)
    journal = append_event(journal, retraction)
    row = rank_revisit(HistoryInput(replay=replay, journal=journal)).events[0]
    assert row.history.declared_known


@pytest.mark.parametrize("mode", ["correction", "withdrawal", "material"])
@pytest.mark.parametrize("positive", ["known", "acknowledged"])
@pytest.mark.parametrize("negative_first", [True, False])
def test_current_update_conflict_preserves_protection_in_both_orders(mode, positive, negative_first):
    value = with_history(revisit_case(7, mode), ())
    replay = add_current_delivery(value.replay)
    journal = HistoryJournal()
    order = ("not_known", positive) if negative_first else (positive, "not_known")
    for signal in order:
        journal = append_event(journal, event_for(replay,
            "acknowledged" if signal == "acknowledged" else "feedback",
            feedback=None if signal == "acknowledged" else signal, interaction_id=signal,
            delivery_index=1))
    selected = HistoryInput(replay=replay, journal=journal)
    for algorithm in ("b4", "p1"):
        row = rank_revisit(selected, algorithm).events[0]
        assert not row.history.declared_known
        assert row.history.promotion == {"material": "material_change"}.get(mode, mode)
        assert row.protected and row.features.duplicate.value == 0
        assert row.features.novelty.value == 1
        assert all(signal in row.features.exposure_signals or f"feedback:{signal}" in
                   row.features.exposure_signals for signal in order)
    # Retracting the negative resolves the conflict; the actual current declaration remains.
    resolved = append_event(journal, event_for(replay, "retract", interaction_id="resolve",
        retracts_id="not_known", delivery_index=1))
    row = rank_revisit(HistoryInput(replay=replay, journal=resolved)).events[0]
    assert row.history.declared_known and not row.protected
    assert row.features.duplicate.value == pytest.approx(.4)  # Two bound deliveries.
    # Retracting only the positive declaration cannot resolve the negative.
    rejected = append_event(journal, event_for(replay, "retract", interaction_id="reject",
        retracts_id=positive, delivery_index=1))
    row = rank_revisit(HistoryInput(replay=replay, journal=rejected)).events[0]
    assert not row.history.declared_known and row.protected and row.features.duplicate.value == 0


@pytest.mark.parametrize("stage", ["merge", "split"])
@pytest.mark.parametrize("certainty", ["missing", "uncertain", "confirmed"])
@pytest.mark.parametrize("signal", ["acknowledged", "known", "opened"])
def test_current_exact_feedback_survives_uncertain_ancestral_mapping(stage, certainty, signal):
    replay = all_old_deliveries(identity_case(stage))
    mappings = () if certainty == "missing" else mappings_for(replay, certainty)
    ci = next(i for i, c in enumerate(replay.candidates) if c.rule_item.tier_candidate != "hold")
    replay = add_current_delivery(replay, ci)
    index = len(replay.deliveries) - 1
    journal = append_event(HistoryJournal(), event_for(replay,
        "feedback" if signal == "known" else signal, feedback="known" if signal == "known" else None,
        interaction_id="current:signal", delivery_index=index))
    value = HistoryInput(replay=replay, journal=journal, mappings=mappings)
    key = replay.candidates[ci].event.event_key
    row = next(r for r in rank_revisit(value).events if r.event_key == key)
    assert replay.candidates[ci].snapshot.snapshot_id in row.history.resolved_snapshot_ids
    assert row.history.delivery_count == (3 if certainty == "confirmed" else 1)
    assert row.history.declared_known is (signal != "opened")
    assert row.features.novelty.value == (1 if signal == "opened" else 0)
    assert "/journal/entries/0/event" in row.history.input_refs
    if certainty != "confirmed":
        assert "uncertain_history_no_inherited_knowledge_or_penalty" in row.history.reason_codes
        assert all(r.snapshot_id not in row.history.resolved_snapshot_ids for d in replay.deliveries[:-1]
                   for r in d.items)
        if signal != "opened":
            assert not row.protected and row.features.duplicate.value == pytest.approx(.35)
