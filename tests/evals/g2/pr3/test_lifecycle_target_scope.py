"""Lifecycle targets must be grounded in the act, not in its scope metadata."""

import pytest

from evals.intelligence_g2.contracts import G2Error
from evals.intelligence_g2.pr3.contracts import PR3Config
from evals.intelligence_g2.pr3.validate_output import validate_output

from ..pr2.support import sequence
from .support import evidence_for, replay_values


def replay(body, *, replace=None):
    old = replay_values("T19")[0].visible_documents[0].candidate.paragraphs[0].text
    for source, target in (replace or {}).items():
        old = old.replace(source, target)
    scope = old[old.index("Task:"):]
    return evidence_for(sequence([(0, [{"id": "a", "body": old}]),
        (8, [{"id": "a", "version": 2, "body": body + " " + scope}])]))


@pytest.mark.parametrize("old_scope", [
    "Task: summarization", "Dataset: ToySet", "Baseline: Base v1.0", "Protocol: P1",
    "Hardware: CPU", "Conditions: batch=1",
])
def test_scope_metric_word_cannot_identify_accuracy_withdrawal_as_speed(old_scope):
    body = "Atlas Tool v1.0 withdraws its previous accuracy claim of 40%."
    field = old_scope.split(":")[0]
    _, rows = replay(body, replace={old_scope: field + ": speed gain evaluation"})
    old, new = rows
    assert new.validation.ok
    assert new.transitions == ()
    assert "unresolved_withdrawal" in {g.code for g in new.validation.coverage_gaps}
    claim = new.claims[0]
    assert claim.marker == "withdrawal" and claim.statement.startswith(body)
    metric = claim.proposition.metric
    assert metric is not None and metric.raw_value == "accuracy claim"
    assert metric.normalized_value == "accuracy"
    assert body[metric.start:metric.end] == metric.raw_value
    assert metric.end <= len(body)
    assert len(claim.proposition.quantities) == 1
    assert claim.proposition.quantities[0].value.end <= len(body)
    assert next(a.lifecycle for a in new.assessments if a.claim_key == old.claims[0].claim_key) == "historical"
    assert next(c for c in new.next_state.claims if c.claim_key == old.claims[0].claim_key) == old.claims[0]


def test_scope_metric_word_cannot_identify_accuracy_correction_as_speed():
    body = "Atlas Tool v1.0 correction: the previous accuracy claim of 40% is corrected to 4%."
    _, rows = replay(body, replace={"Task: summarization": "Task: speed gain evaluation"})
    new = rows[-1]
    assert new.transitions == () and new.claims[0].marker == "correction"
    assert "unresolved_correction" in {g.code for g in new.validation.coverage_gaps}
    assert new.claims[0].proposition.metric.raw_value == "accuracy claim"
    assert [q.value.normalized_value for q in new.claims[0].proposition.quantities] == ["40", "4"]


def test_missing_target_metric_is_not_filled_from_scope():
    _, rows = replay("Atlas Tool v1.0 withdraws its previous claim of 40%.",
        replace={"Task: summarization": "Task: speed gain evaluation"})
    assert rows[-1].claims[0].proposition.metric is None
    assert rows[-1].transitions == ()
    assert "unresolved_withdrawal" in {g.code for g in rows[-1].validation.coverage_gaps}


@pytest.mark.parametrize("source,target", [
    ("Task: summarization", "Task: speed gain evaluation"),
    ("Conditions: batch=1", "Conditions: batch=1, accuracy threshold 5%"),
    ("Conditions: batch=1", "Conditions: batch=1, up to 8 workers"),
])
def test_legal_speed_withdrawal_uses_only_clause_quantity_and_quantifier(source, target):
    body = "Atlas Tool v1.0 withdraws its previous speed gain of 40% claim."
    _, rows = replay(body, replace={source: target})
    old, new = rows
    assert len(new.transitions) == 1 and new.transitions[0].kind == "retracts"
    assert new.transitions[0].from_claim_keys == (old.claims[0].claim_key,)
    for claim in (old.claims[0], new.claims[0]):
        assert claim.proposition.quantifier == "reported"
        assert len(claim.proposition.quantities) == 1
        quantity = claim.proposition.quantities[0]
        assert (quantity.value.normalized_value, quantity.unit, quantity.quantifier) == ("40", "percent", "reported")
        assert quantity.value.end < claim.statement.index("Task:")
        assert claim.proposition.metric.end < claim.statement.index("Task:")
    assert next(a.lifecycle for a in new.assessments if a.claim_key == old.claims[0].claim_key) == "retracted"


def test_legal_correction_has_old_and_new_quantity_spans_without_scope_numbers():
    body = "Atlas Tool v1.0 correction: the previous speed gain of 40% is corrected to 4%."
    _, rows = replay(body, replace={"Conditions: batch=1": "Conditions: batch=1, accuracy threshold 99%"})
    new = rows[-1]
    assert len(new.transitions) == 1 and new.transitions[0].kind == "corrects"
    assert [q.value.normalized_value for q in new.claims[0].proposition.quantities] == ["40", "4"]
    assert all(q.value.end <= len(body) for q in new.claims[0].proposition.quantities)


def test_forged_scope_metric_provenance_is_rejected():
    values, rows = replay("Atlas Tool v1.0 withdraws its previous accuracy claim of 40%.",
        replace={"Task: summarization": "Task: speed gain evaluation"})
    claim = rows[-1].claims[0]
    start = claim.statement.index("speed gain", claim.statement.index("Task:"))
    metric = claim.proposition.metric.model_copy(update={"raw_value": "speed gain",
        "normalized_value": "speed_gain", "start": start, "end": start + len("speed gain")})
    forged = claim.model_copy(update={"proposition": claim.proposition.model_copy(update={"metric": metric})})
    with pytest.raises(G2Error) as error:
        validate_output(rows[-1].model_copy(update={"claims": (forged,)}), values[-1], PR3Config())
    assert (error.value.code, error.value.stage, error.value.field, error.value.record_id) == (
        "G2_PR3_FIELD_PROVENANCE_INVALID", "scope", "grounded_fields", claim.claim_key)
