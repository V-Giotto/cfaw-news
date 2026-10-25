import pytest

from evals.intelligence_g2.pr3.contracts import PR3Config
from evals.intelligence_g2.pr3.extract import extract_claims

from .support import evidence_for as run_values
from .support import inputs_for, make_input


@pytest.mark.parametrize("phrase,number,unit,quantifier", [
    ("speed gain of 40%", "40", "percent", "reported"),
    ("speed gain of up to 40%", "40", "percent", "at_most"),
    ("speed gain of at least 4.50 percentage points", "4.5", "percent_point", "at_least"),
    ("speed gain of approximately 2 times", "2", "ratio", "approx"),
    ("速度提升40%", "40", "percent", "reported"),
])
def test_numbers_units_and_quantifiers_are_not_interchanged(phrase, number, unit, quantifier):
    value = make_input([{"id": "a", "body": "Atlas Tool v1.0 reports " + phrase + "."}])
    result = inputs_for([value])[1][0]
    claim = extract_claims(replay_input=value, events=result.events, config=PR3Config()).claims[0]
    q = claim.proposition.quantities[0]
    assert (q.value.normalized_value, q.unit, q.quantifier) == (number, unit, quantifier)


@pytest.mark.parametrize("body", [
    "Atlas Tool v1.0 correction: no correction was issued for our previous speed gain of 40%.",
    "Atlas Tool v1.0 withdraws nothing; this is no withdrawal of our previous speed gain of 40%.",
])
def test_negative_correction_and_withdrawal_markers_cannot_retract(body):
    value = make_input([{"id": "a", "body": body}])
    result = inputs_for([value])[1][0]
    claim = extract_claims(replay_input=value, events=result.events, config=PR3Config()).claims[0]
    assert claim.marker == "none"


@pytest.mark.parametrize("phrase", ["not a speed gain of 40%", "a speed gain of 0%", "a speed gain of 1 times"])
def test_unsupported_negation_zero_and_ratio_do_not_become_opposite_positive_evidence(phrase):
    from .support import replay_values

    values = replay_values("T23")
    specs = [{"id": "a", "body": values[0].visible_documents[0].candidate.paragraphs[0].text},
        {"id": "b", "body": "Atlas Tool v1.0 reports " + phrase + ". Task: summarization; Dataset: ToySet; Baseline: Base v1.0; Protocol: P1; Hardware: CPU; Conditions: batch=1;"}]
    result = run_values([make_input(specs)])[1][0]
    assert result.conflicts == ()
    assert not any(link.direction in {"supports", "refutes"} for link in result.links)


def test_positive_result_and_other_baseline_negation_in_one_paragraph_abstains():
    from .support import replay_values

    original = replay_values("T19")[0].visible_documents[0].candidate.paragraphs[0].text
    mixed = original + " No speed gain was reported for a different baseline."
    result = run_values([make_input([{"id": "a", "body": original}, {"id": "b", "body": mixed}])])[1][0]
    mixed_claim = next(c for c in result.claims if c.doc_version_id == "b:1")
    assert mixed_claim.statement == mixed
    assert mixed_claim.proposition.ambiguous
    assert result.conflicts == ()
    assert not any(link.direction in {"supports", "refutes"} for link in result.links)


def test_unparsed_conditional_cannot_be_hidden_by_equal_structured_scope_markers():
    from .support import replay_values

    original = replay_values("T19")[0].visible_documents[0].candidate.paragraphs[0].text
    conditional = original.replace("claims a speed gain", "claims if an unreported setup is used, a speed gain")
    result = run_values([make_input([{"id": "a", "body": original}, {"id": "b", "body": conditional}])])[1][0]
    assert next(c for c in result.claims if c.doc_version_id == "b:1").proposition.ambiguous
    assert not any(link.direction in {"supports", "refutes"} for link in result.links)
