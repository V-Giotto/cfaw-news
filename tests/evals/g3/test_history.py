"""PR3 adversarial history contracts, journal integrity and temporal boundaries."""

from datetime import timedelta

import pytest
from pydantic import ValidationError

from evals.intelligence_g2.contracts import data, digest, json_bytes
from evals.intelligence_g3.contracts import G3ReplayInput
from evals.intelligence_g3.history import (
    append_event,
    select_deliveries,
    select_history,
    select_persona,
)
from evals.intelligence_g3.history_contracts import HistoryEvent, HistoryInput, HistoryJournal
from evals.intelligence_g3.history_contracts import parse_history as parse
from evals.intelligence_g3.history_store import append_interaction, load_journal
from evals.intelligence_v1.exceptions import ContractError
from evals.intelligence_v1.hashing import sha256_bytes

from .history_support import event_for, revisit_case, with_history
from .history_support import g3_tmp_path as g3_tmp_path


@pytest.mark.parametrize("kind", ["included", "rendered", "opened", "acknowledged", "dismissed"])
def test_actions_are_independent_facts_without_inferred_transitions(kind):
    value = with_history(revisit_case(), (kind,))
    assert [e.event.kind for e in value.journal.entries] == [kind]
    assert parse(HistoryInput, data(value)) == value


@pytest.mark.parametrize("feedback", ["helpful", "irrelevant", "known", "not_known"])
def test_explicit_feedback_enum_and_roundtrip(feedback):
    value = with_history(revisit_case(), ())
    event = event_for(value.replay, "feedback", feedback=feedback)
    assert parse(HistoryEvent, data(event)) == event
    journal = append_event(value.journal, event)
    assert parse(HistoryInput, dict(replay=data(value.replay), journal=data(journal)))


@pytest.mark.parametrize("mutation", [dict(kind="seen"), dict(feedback="implicit_known"),
    dict(feedback="known"), dict(kind="feedback"), dict(retracts_id="old"),
    dict(source="server"), dict(record_origin="real"), dict(extra="gold")])
def test_illegal_feedback_source_origin_or_extra_fields_fail(mutation):
    event = event_for(with_history(revisit_case(), ()).replay)
    with pytest.raises((ValidationError, ContractError)):
        parse(HistoryEvent, {**data(event), **mutation})


@pytest.mark.parametrize("field", ["occurred_at", "available_at"])
def test_explicit_future_interaction_rejected_in_wire_model_and_projection_filters_it(field):
    value = with_history(revisit_case(), ())
    raw = data(event_for(value.replay))
    future = value.replay.as_of + timedelta(seconds=1)
    raw["available_at"] = future.isoformat()
    if field == "occurred_at":
        raw[field] = future.isoformat()
    journal = append_event(HistoryJournal(), parse(HistoryEvent, raw))
    payload = dict(replay=data(value.replay), journal=data(journal))
    with pytest.raises(ValidationError, match="G3_FUTURE_HISTORY"):
        HistoryInput.model_validate_json(json_bytes(payload))
    selected = select_history(value.replay, journal)
    assert selected.journal.entries == ()
    assert data(selected) == data(value)


def test_delayed_record_not_visible_at_occurrence_time_and_boundary_is_inclusive():
    value = with_history(revisit_case(), ())
    event = event_for(value.replay, available_at=value.replay.as_of)
    journal = append_event(HistoryJournal(), event)
    assert select_history(value.replay, journal).journal == journal
    old = data(event)
    old["available_at"] = (value.replay.as_of + timedelta(seconds=1)).isoformat()
    future = append_event(HistoryJournal(), parse(HistoryEvent, old))
    assert select_history(value.replay, future).journal.entries == ()


@pytest.mark.parametrize("field", ["available_at", "generated_at", "as_of"])
def test_future_delivery_is_excluded_by_selector_and_rejected_by_explicit_replay(field):
    value = with_history(revisit_case(), ())
    raw = data(value.replay)
    stamp = (value.replay.as_of + timedelta(seconds=1)).isoformat()
    d = raw["deliveries"][0]
    d["available_at"] = stamp
    if field != "available_at":
        d["delivery"][field] = stamp
    if field == "as_of":
        d["delivery"]["generated_at"] = stamp
    from evals.intelligence_g3.contracts import DeliverySnapshot

    future = parse(DeliverySnapshot, d)
    assert select_deliveries((future,), value.replay.as_of) == ()
    with pytest.raises(ValidationError):
        G3ReplayInput.model_validate_json(json_bytes(raw))


def test_future_persona_selection_and_strict_rejection():
    value = with_history(revisit_case(), ())
    old = value.replay.persona
    future = data(old)
    future["persona"]["available_at"] = (value.replay.as_of + timedelta(seconds=1)).isoformat()
    future["persona"]["persona_version_id"] = "future:persona"
    from evals.intelligence_g3.contracts import PersonaSnapshot

    future = parse(PersonaSnapshot, future)
    assert select_persona((old, future), value.replay.as_of) == old
    with pytest.raises(ContractError, match="G3_FUTURE_PERSONA"):
        select_persona((future,), value.replay.as_of)
    raw = data(value.replay)
    raw["persona"] = data(future)
    with pytest.raises(ValidationError, match="G3_FUTURE_PERSONA"):
        G3ReplayInput.model_validate_json(json_bytes(raw))


@pytest.mark.parametrize("mutation", ["target", "delivery", "persona", "legacy"])
def test_unbound_interaction_and_legacy_history_cannot_silently_enter_pr3(mutation):
    value = with_history(revisit_case())
    raw = data(value)
    event = raw["journal"]["entries"][0]["event"]
    if mutation == "target":
        event["target"]["event_revision"] = "0" * 64
    elif mutation == "delivery":
        event["delivery_id"] = "unknown"
    elif mutation == "persona":
        event["persona_id"] = "unknown"
    else:
        from .ranking_support import delivered

        raw["replay"] = data(delivered(revisit_case()))
    if mutation != "legacy":
        raw["journal"] = data(append_event(HistoryJournal(), parse(HistoryEvent, event)))
    with pytest.raises(ValidationError):
        HistoryInput.model_validate_json(json_bytes(raw))


def test_append_only_writer_retains_bytes_and_rejects_overwrite_and_stale_head(g3_tmp_path):
    path = g3_tmp_path / "history.jsonl"
    value = with_history(revisit_case(), ())
    first = event_for(value.replay, "acknowledged", interaction_id="old")
    j1 = append_interaction(path, first, expected_head=None)
    original = path.read_bytes()
    replacement = event_for(value.replay, "feedback", feedback="not_known", interaction_id="new")
    j2 = append_interaction(path, replacement, expected_head=j1.head)
    assert path.read_bytes().startswith(original) and len(j2.entries) == 2
    raw = path.read_bytes()
    assert load_journal(path, expected_sha256=sha256_bytes(raw)) == j2
    for event, head, code in [(first, j2.head, "G3_HISTORY_CHAIN_INVALID"),
                               (replacement, j1.head, "G3_HISTORY_HEAD_MISMATCH")]:
        with pytest.raises(ContractError, match=code):
            append_interaction(path, event, expected_head=head)
        assert path.read_bytes() == raw


@pytest.mark.parametrize("mutation", ["edit", "delete", "reorder", "truncate", "rehash"])
def test_journal_tampering_fails_chain_or_external_pin(g3_tmp_path, mutation):
    value = with_history(revisit_case(), ("opened", "acknowledged"))
    path = g3_tmp_path / "history.jsonl"
    raw = b"".join(json_bytes(e) for e in value.journal.entries)
    trusted = sha256_bytes(raw)
    if mutation == "edit":
        bad = raw.replace(b'"opened"', b'"dismissed"')
    elif mutation == "delete":
        bad = json_bytes(value.journal.entries[0])
    elif mutation == "reorder":
        bad = b"".join(json_bytes(e) for e in reversed(value.journal.entries))
    elif mutation == "truncate":
        bad = raw[:-1]
    else:
        replacement = append_event(HistoryJournal(), event_for(value.replay, "dismissed"))
        bad = json_bytes(replacement.entries[0])
    path.write_bytes(bad)  # An attacker, deliberately outside the append API.
    with pytest.raises(ContractError, match="G3_SHA_MISMATCH"):
        load_journal(path, expected_sha256=trusted)
    if mutation in {"edit", "reorder", "truncate"}:
        with pytest.raises(ContractError):
            load_journal(path, expected_sha256=sha256_bytes(bad))


def test_busy_writer_fails_without_removing_foreign_lock(g3_tmp_path):
    path = g3_tmp_path / "history.jsonl"
    lock = g3_tmp_path / "history.jsonl.lock"
    lock.write_text("existing writer", encoding="utf-8")
    event = event_for(with_history(revisit_case(), ()).replay)
    with pytest.raises(ContractError, match="G3_HISTORY_CONCURRENT_WRITE"):
        append_interaction(path, event, expected_head=None)
    assert lock.read_text(encoding="utf-8") == "existing writer" and not path.exists()


def test_backdated_availability_duplicate_id_and_bad_sequence_are_rejected():
    replay = with_history(revisit_case(), ()).replay
    later = event_for(replay, available_at=replay.as_of)
    journal = append_event(HistoryJournal(), later)
    with pytest.raises(ContractError, match="G3_HISTORY_CHAIN_INVALID"):
        append_event(journal, event_for(replay, interaction_id="backdated"))
    body = dict(sequence=3, previous_sha256=journal.head,
                event=data(event_for(replay, interaction_id="next", available_at=replay.as_of)))
    with pytest.raises(ContractError, match="G3_HISTORY_CHAIN_INVALID"):
        parse(HistoryJournal, dict(entries=[*data(journal)["entries"], {**body, "sha256": digest(body)}]))


@pytest.mark.parametrize("operation", ["append", "load", "export_input", "export_output"])
def test_storage_and_export_still_reject_paths_outside_g3(g3_tmp_path, operation):
    from evals.intelligence_g3.contracts import ROOT
    from evals.intelligence_g3.revisit_cli import export_revisit

    # Guaranteed outside the allowed areas, even when pytest itself uses a G3 basetemp.
    outside = ROOT / ".tmp/g3-path-denied" / g3_tmp_path.name / "outside.jsonl"
    value = with_history(revisit_case(), ())
    source = g3_tmp_path / "input.json"
    source.write_bytes(json_bytes(value))
    with pytest.raises(ContractError, match="G3_PATH_INVALID"):
        if operation == "append":
            append_interaction(outside, event_for(value.replay), expected_head=None)
        elif operation == "load":
            load_journal(outside, expected_sha256="0" * 64)
        elif operation == "export_input":
            export_revisit(outside, input_sha256="0" * 64, out=g3_tmp_path / "out")
        else:
            export_revisit(source, input_sha256=sha256_bytes(source.read_bytes()), out=outside)
    assert not outside.exists() and not (g3_tmp_path / "out").exists()
