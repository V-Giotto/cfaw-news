from datetime import timedelta

import pytest

from evals.intelligence_g2.contracts import G2Error, digest
from evals.intelligence_g2.pr3.contracts import PR3Config
from evals.intelligence_g2.pr3.pipeline import run_evidence_step

from ..pr2.support import merge_split_steps, sequence
from .support import evidence_for, make_input, replay_values, run


def test_T24_correction_keeps_old_claim_snapshot_and_event_identity():
    values, rows = run("T24")
    old, new = rows
    old_hash = digest(old)
    assert old.bundles[0].event_key == new.bundles[0].event_key
    assert old.bundles[0].event_revision != new.bundles[0].event_revision
    assert old.claims[0].statement.find("40%") >= 0 and "4%" in new.claims[0].statement
    assert len(new.transitions) == 1 and new.transitions[0].kind == "corrects"
    assert new.transitions[0].from_claim_keys == (old.claims[0].claim_key,)
    archived = next(c for c in new.next_state.claims if c.claim_key == old.claims[0].claim_key)
    assert archived == old.claims[0]
    assessment = next(a for a in new.assessments if a.claim_key == archived.claim_key)
    assert assessment.lifecycle == "superseded"
    assert assessment.verification_state != "retracted"
    assert new.next_state.assessments[:len(old.next_state.assessments)] == old.next_state.assessments
    assert digest(old) == old_hash
    assert run_evidence_step(evidence_input=values[1], config=PR3Config()) == new


def test_T24_explicit_withdrawal_and_unmarked_numeric_edit_are_distinct():
    _, withdrawal = run("RETRACT")
    assert withdrawal[-1].transitions[0].kind == "retracts"
    assert next(a for a in withdrawal[-1].assessments if a.lifecycle == "retracted").verification_state == "retracted"
    _, unmarked = run("UNMARKED")
    assert unmarked[-1].transitions == ()
    assert all(a.lifecycle != "retracted" for a in unmarked[-1].assessments)


def test_repeated_same_correction_does_not_append_duplicate_transition():
    values = replay_values("T24")
    specs = [{"id": "a", "version": 2, "body": values[1].visible_documents[0].candidate.paragraphs[0].text}]
    values.append(make_input(specs, timeline="T24", day=9, previous=values[-1]))
    _, rows = evidence_for(values)
    assert rows[-1].transitions == ()
    assert rows[-1].next_state.transitions == rows[-2].next_state.transitions
    assert rows[-1].claims == rows[-2].claims


def test_merge_split_preserve_birth_and_append_event_memberships():
    # Unchanged document b continues across a merge caused by revised document a.
    a = {"id": "a", "title": "Atlas Tool release", "body": "Atlas Tool is released."}
    b = {"id": "b", "body": "Atlas Tool v1.0 claims a speed gain of 40%."}
    a2 = {"id": "a", "version": 2, "body": "Atlas Tool v1.0 is released."}
    _, rows = evidence_for(sequence([(0, [a, b]), (1, [a2, b])]))
    old_b = next(c for c in rows[0].claims if c.doc_version_id == "b:1")
    new_b = next(c for c in rows[1].claims if c.doc_version_id == "b:1")
    assert old_b == new_b
    assert next(c for c in rows[1].next_state.claims if c.claim_key == old_b.claim_key) == old_b
    _, split = evidence_for(sequence(merge_split_steps()))
    assert [len(r.bundles) for r in split] == [2, 1, 2]
    assert split[-1].next_state.memberships[:len(split[-2].next_state.memberships)] == split[-2].next_state.memberships


def test_future_or_tampered_history_and_wrong_prefix_fail():
    values, rows = run("T24")
    old_state = rows[0].next_state
    ref = old_state.citations[0].model_copy(update={"available_at": values[1].grouping_input.cursor.as_of + timedelta(days=1)})
    changed = old_state.model_copy(update={"citations": (ref,)})
    with pytest.raises(G2Error) as error:
        run_evidence_step(evidence_input=values[1].model_copy(update={"previous_state": changed,
            "previous_state_sha256": digest(changed)}), config=PR3Config())
    assert (error.value.code, error.value.stage, error.value.field) == (
        "G2_PR3_HISTORY_FUTURE", "history", "citations.available_at")
    with pytest.raises(G2Error) as error:
        run_evidence_step(evidence_input=values[1].model_copy(update={"previous_state_sha256": "f" * 64}), config=PR3Config())
    assert (error.value.code, error.value.stage, error.value.field) == (
        "G2_PR3_STATE_CHAIN_INVALID", "history", "previous_state")
