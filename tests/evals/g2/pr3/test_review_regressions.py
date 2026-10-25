"""PR3 review counterexamples; no development reference labels enter prediction."""

import pytest

from evals.intelligence_g2.contracts import G2Error, digest
from evals.intelligence_g2.pr3.contracts import ClaimTransition, PR3Config
from evals.intelligence_g2.pr3.validate_output import validate_output

from ..pr2.support import sequence
from .support import evidence_for, replay_values


def lifecycle_replay(body, *, title="Atlas Tool v1.0 release", original=None):
    original = original or replay_values("T19")[0].visible_documents[0].candidate.paragraphs[0].text
    scope = original[original.index("Task:"):]
    return evidence_for(sequence([(0, [{"id": "a", "body": original}]),
        (8, [{"id": "a", "version": 2, "title": title, "body": body + " " + scope}])]))


@pytest.mark.parametrize("body", [
    "Atlas Tool v1.0 reports it will not withdraw its previous speed gain of 40%.",
    "Atlas Tool v1.0 reports it will withdraw its previous speed gain of 40%.",
    "Atlas Tool v1.0 reports it may withdraw its previous speed gain of 40%.",
    "Atlas Tool v1.0 withdraws its previous speed gain of 40% claim if replication fails.",
    "Atlas Tool v1.0 correction: the previous speed gain of 40% is not corrected to 4%.",
    "Atlas Tool v1.0 correction: the previous speed gain of 40% will be corrected to 4%.",
])
def test_review_A_nonaffirmative_lifecycle_cannot_change_old_claim(body):
    _, rows = lifecycle_replay(body)
    old, new = rows
    key = old.claims[0].claim_key
    assert new.validation.ok
    assert new.claims[0].statement.startswith(body)
    assert new.claims[0].marker == "none"
    assert new.transitions == ()
    assessment = next(a for a in new.assessments if a.claim_key == key)
    assert (assessment.lifecycle, assessment.verification_state) == ("historical", "source_attributed")
    assert next(c for c in new.next_state.claims if c.claim_key == key) == old.claims[0]
    assert new.next_state.assessments[:len(old.next_state.assessments)] == old.next_state.assessments


@pytest.mark.parametrize("body", [
    "Atlas Tool v1.0 withdraws its previous accuracy claim of 40 percentage points.",
    "Atlas Tool v1.0 withdraws its previous speed gain of 40 percentage points claim.",
    "Atlas Tool v1.0 withdraws its previous speed gain of up to 40% claim.",
    "Atlas Tool v1.0 withdraws its previous claim of 40%.",
])
def test_review_B_same_number_is_not_a_complete_withdrawal_target(body):
    _, rows = lifecycle_replay(body)
    old, new = rows
    assert new.validation.ok and new.transitions == ()
    assert new.claims[0].marker == "withdrawal"
    assert "unresolved_withdrawal" in {g.code for g in new.validation.coverage_gaps}
    assessment = next(a for a in new.assessments if a.claim_key == old.claims[0].claim_key)
    assert (assessment.lifecycle, assessment.verification_state) == ("historical", "source_attributed")


def test_review_B_missing_scope_is_not_a_target_wildcard():
    _, rows = lifecycle_replay("Atlas Tool v1.0 withdraws our previous speed gain of 40% claim.")
    original = rows[0].claims[0].statement
    scoped = original[original.index("Task:"):]
    _, rows = evidence_for(sequence([(0, [{"id": "a", "body": original}]), (8, [{"id": "a", "version": 2,
        "body": "Atlas Tool v1.0 withdraws our previous speed gain of 40% claim. "
        + scoped.replace("Task: summarization; ", "")}])]))
    assert rows[-1].transitions == ()
    assert "unresolved_withdrawal" in {g.code for g in rows[-1].validation.coverage_gaps}


@pytest.mark.parametrize("body,kind,lifecycle", [
    ("Atlas Tool v1.0 withdraws our previous speed gain of 40% claim.", "retracts", "retracted"),
    ("Atlas Tool v1.0 correction: the previous speed gain of 40% is corrected to 4%.", "corrects", "superseded"),
])
def test_review_AB_complete_affirmative_target_still_changes_lifecycle(body, kind, lifecycle):
    _, rows = lifecycle_replay(body)
    old, new = rows
    assert len(new.transitions) == 1
    assert (new.transitions[0].kind, new.transitions[0].from_claim_keys) == (kind, (old.claims[0].claim_key,))
    assert next(a for a in new.assessments if a.claim_key == old.claims[0].claim_key).lifecycle == lifecycle


def test_review_C_repurposed_document_cannot_move_historical_claim_to_new_event():
    values, rows = lifecycle_replay("Atlas Tool v2.0 claims a speed gain of 60%.", title="Atlas Tool v2.0 release")
    old, new = rows
    old_hash = digest(old)
    old_claim = old.claims[0]
    old_key, new_key = old.bundles[0].event_key, new.bundles[0].event_key
    assert old_key != new_key
    assert not any(t.kind in {"merge", "split", "complex"} for t in values[-1].grouping_result.transitions)
    assert old_claim.claim_key not in new.bundles[0].historical_claim_keys
    assert all(m.claim_key != old_claim.claim_key for m in new.memberships)
    assert {m.event_key for m in new.next_state.memberships if m.claim_key == old_claim.claim_key} == {old_key}
    assert next(c for c in new.next_state.claims if c.claim_key == old_claim.claim_key) == old_claim
    assert new.next_state.assessments[:len(old.next_state.assessments)] == old.next_state.assessments
    assert digest(old) == old_hash


def test_review_C_compatible_version_update_keeps_old_history_in_same_event():
    _, rows = lifecycle_replay("Atlas Tool v1.0 claims a speed gain of 60%.")
    assert rows[0].bundles[0].event_key == rows[1].bundles[0].event_key
    assert rows[0].claims[0].claim_key in rows[1].bundles[0].historical_claim_keys


@pytest.mark.parametrize("qualifier", ["up to", "at least"])
def test_review_B_matching_explicit_quantifier_remains_a_positive_control(qualifier):
    original = replay_values("T19")[0].visible_documents[0].candidate.paragraphs[0].text
    original = original.replace("of 40%", "of " + qualifier + " 40%")
    _, rows = lifecycle_replay("Atlas Tool v1.0 withdraws our previous speed gain of "
        + qualifier + " 40% claim.", original=original)
    assert len(rows[-1].transitions) == 1 and rows[-1].transitions[0].kind == "retracts"


def test_review_C_explicit_merge_authorizes_historical_membership_with_lineage():
    original = replay_values("T19")[0].visible_documents[0].candidate.paragraphs[0].text
    a = {"id": "a", "title": "Atlas Tool release", "body": "Atlas Tool is released."}
    b = {"id": "b", "body": original}
    a2 = {"id": "a", "version": 2, "body": "Atlas Tool v1.0 is released."}
    b2 = {"id": "b", "version": 2, "body": original.replace("40%", "60%")}
    values, rows = evidence_for(sequence([(0, [a, b]), (1, [a2, b2])]))
    assert [len(r.bundles) for r in rows] == [2, 1]
    merge = next(t for t in values[-1].grouping_result.transitions if t.kind == "merge")
    retired_claims = {m.claim_key for m in rows[0].memberships if m.event_key != rows[1].bundles[0].event_key}
    assert retired_claims
    for key in retired_claims:
        assert key in rows[1].bundles[0].historical_claim_keys
        membership = next(m for m in rows[1].memberships if m.claim_key == key)
        assert membership.basis == "pr2_identity_lineage"
        assert membership.lineage_ids == (merge.transition_id,)
    assert rows[1].next_state.memberships[:len(rows[0].next_state.memberships)] == rows[0].next_state.memberships


def test_review_A_forged_nonaffirmative_transition_is_rejected():
    values, rows = lifecycle_replay("Atlas Tool v1.0 reports it will not withdraw its previous speed gain of 40%.")
    transition = ClaimTransition(transition_id="forged", kind="retracts",
        from_claim_keys=(rows[0].claims[0].claim_key,), to_claim_keys=(rows[1].claims[0].claim_key,),
        effective_at=values[1].grouping_input.cursor.as_of, trigger_ref_ids=rows[1].claims[0].evidence_ref_ids)
    with pytest.raises(G2Error) as error:
        validate_output(rows[1].model_copy(update={"transitions": (transition,)}), values[1], PR3Config())
    assert (error.value.code, error.value.stage, error.value.field, error.value.record_id) == (
        "G2_PR3_STATE_CHAIN_INVALID", "history", "transitions", "")


def test_review_C_forged_historical_reassignment_is_rejected():
    values, rows = lifecycle_replay("Atlas Tool v2.0 claims a speed gain of 60%.", title="Atlas Tool v2.0 release")
    prior = rows[0].memberships[0]
    forged = prior.model_copy(update={"event_key": rows[1].bundles[0].event_key,
        "effective_at": values[1].grouping_input.cursor.as_of})
    state = rows[1].next_state.model_copy(update={"memberships": rows[1].next_state.memberships + (forged,)})
    with pytest.raises(G2Error) as error:
        validate_output(rows[1].model_copy(update={"next_state": state}), values[1], PR3Config())
    assert (error.value.code, error.value.stage, error.value.field, error.value.record_id) == (
        "G2_PR3_STATE_CHAIN_INVALID", "history", "next_state", "")
