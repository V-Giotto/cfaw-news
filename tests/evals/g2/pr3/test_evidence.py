from datetime import timedelta

import pytest

from evals.intelligence_g2.contracts import G2Error, digest
from evals.intelligence_g2.pr3.contracts import PR3Config
from evals.intelligence_g2.pr3.pipeline import run_evidence_step
from evals.intelligence_g2.pr3.relations import make_link
from evals.intelligence_g2.pr3.validate_output import check_citation, validate_output

from .support import run


def assert_issue(error, code, stage, field, record_id=None):
    assert (error.value.code, error.value.stage, error.value.field) == (code, stage, field)
    if record_id is not None:
        assert error.value.record_id == record_id


def test_T20_reprints_are_dependent_but_citation_is_not_independence():
    _, rows = run("T20")
    result = rows[0]
    assert len(result.claims) == len(result.citations) == len(result.lineage) == 4
    assert len({s.dependency_group_key for s in result.lineage}) == 1
    assert {s.independence for s in result.lineage} == {"dependent"}
    assert {a.independent_support_count for a in result.assessments} == {0}
    assert {a.verification_state for a in result.assessments} == {"source_attributed"}


@pytest.mark.parametrize("case", ["T22", "NUMERIC_DIFFERENCE", "UP_TO"])
def test_T22_different_scope_or_nonexclusive_numbers_do_not_create_conflict(case):
    _, rows = run(case)
    assert rows[0].conflicts == ()
    assert all(a.verification_state != "disputed" for a in rows[0].assessments)
    assert {link.direction for link in rows[0].links} <= {"mentions", "unknown"}
    if case == "T22":
        assert "scope_difference" in {link.scope_relation for link in rows[0].links}


def test_T23_same_scope_has_two_sided_refutation_without_truth_claim():
    _, rows = run("T23")
    row = rows[0]
    assert len(row.conflicts) == 1
    assert len(row.conflicts[0].ref_ids) == 2
    assert sum(link.direction == "refutes" for link in row.links) == 2
    assert {a.verification_state for a in row.assessments} == {"disputed"}
    assert {a.semantic_truth for a in row.assessments} == {"not_evaluated"}


def test_same_scope_positive_support_is_nonempty_but_not_independent_proof():
    _, rows = run("SUPPORT")
    assert sum(link.direction == "supports" for link in rows[0].links) == 2
    assert {a.verification_state for a in rows[0].assessments} == {"source_attributed"}
    assert {a.independent_support_count for a in rows[0].assessments} == {0}


@pytest.mark.parametrize("kind", ["statement", "quantity", "status", "quote"])
def test_T19_forged_number_grounding_status_or_quote_fails_with_specific_issue(kind):
    values, rows = run("T19")
    result = rows[0]
    claim, ref = result.claims[0], result.citations[0]
    if kind == "statement":
        result = result.model_copy(update={"claims": (claim.model_copy(update={"statement": claim.statement.replace("40%", "400%")}),)})
        expected = ("G2_PR3_SPAN_MISMATCH", "evidence", "statement", claim.claim_key)
    elif kind == "quantity":
        quantity = claim.proposition.quantities[0]
        quantity = quantity.model_copy(update={"value": quantity.value.model_copy(update={"normalized_value": "400"})})
        result = result.model_copy(update={"claims": (claim.model_copy(update={"proposition": claim.proposition.model_copy(update={"quantities": (quantity,)})}),)})
        expected = ("G2_PR3_FIELD_PROVENANCE_INVALID", "scope", "grounded_fields", claim.claim_key)
    elif kind == "status":
        result = result.model_copy(update={"assessments": (result.assessments[0].model_copy(update={"verification_state": "independently_supported"}),)})
        expected = ("G2_PR3_STATUS_INVALID", "output", "verification_state", claim.claim_key)
    else:
        result = result.model_copy(update={"citations": (ref.model_copy(update={"quote_sha256": "0" * 64}),)})
        expected = ("G2_PR3_SPAN_MISMATCH", "evidence", "quote", ref.ref_id)
    with pytest.raises(G2Error) as error:
        validate_output(result, values[0], PR3Config())
    assert_issue(error, *expected)


def test_T25_legal_location_cannot_be_upgraded_to_support_of_another_proposition():
    values, rows = run("T25")
    row = rows[0]
    target = next(c for c in row.claims if c.doc_version_id == "a:1")
    other = next(c for c in row.claims if c.doc_version_id == "b:1")
    ref = next(r for r in row.citations if r.ref_id == other.evidence_ref_ids[0])
    event = values[0].grouping_result.events[0]
    check_citation(ref, values[0].grouping_input.replay_input, event)  # Structural PASS.
    original = next(link for link in row.links if link.target_claim_key == target.claim_key and link.evidence_claim_key == other.claim_key)
    assert original.direction == "unknown"
    assert original.support_check_status == "not_evaluated"
    forged = make_link(target, other, "supports", "same_declared_scope", "same_reported_value_and_scope")
    bad = row.model_copy(update={"links": tuple(forged if link.link_key == original.link_key else link for link in row.links)})
    with pytest.raises(G2Error) as error:
        validate_output(bad, values[0], PR3Config())
    assert_issue(error, "G2_PR3_UNSUPPORTED_DIRECTION", "relations", "links")


def test_T26_cross_event_reference_and_future_poison_fail_before_extraction(monkeypatch):
    values, rows = run("T26")
    row, value = rows[0], values[0]
    ref = next(r for r in row.citations if r.doc_version_id == "foreign:1")
    event = next(e for e in value.grouping_result.events if "a:1" in e.member_doc_version_ids)
    with pytest.raises(G2Error) as error:
        check_citation(ref, value.grouping_input.replay_input, event)
    assert_issue(error, "G2_PR3_EVIDENCE_NOT_IN_EVENT", "evidence", "doc_version_id", "foreign:1")
    replay = value.grouping_input.replay_input
    wrapped = replay.visible_documents[0]

    class Poison:
        def __iter__(self):
            raise AssertionError("future body accessed")

    future = wrapped.candidate.model_copy(update={"available_at": replay.context.as_of + timedelta(days=1), "paragraphs": Poison()})
    replay = replay.model_copy(update={"visible_documents": (wrapped.model_copy(update={"candidate": future}),)})
    changed = value.model_copy(update={"grouping_input": value.grouping_input.model_copy(update={"replay_input": replay})})
    calls = []
    monkeypatch.setattr("evals.intelligence_g2.pr3.pipeline.extract_claims", lambda **kw: calls.append(kw))
    with pytest.raises(G2Error) as error:
        run_evidence_step(evidence_input=changed, config=PR3Config())
    assert_issue(error, "FUTURE_VERSION", "bridge", "candidate.available_at", future.doc_version_id)
    assert calls == []


def test_T26_legal_old_reference_cannot_be_used_as_current_evidence():
    values, rows = run("T24")
    old, current = rows
    claim = old.claims[0]
    new = current.claims[0]
    forged = make_link(new, claim, "refutes", "same_declared_scope", "opposite_polarity_same_scope")
    with pytest.raises(G2Error) as error:
        validate_output(current.model_copy(update={"links": current.links + (forged,)}), values[1], PR3Config())
    assert_issue(error, "G2_PR3_HISTORICAL_REF_AS_CURRENT", "evidence", "link.claim_key", forged.link_key)


def test_output_and_inputs_are_immutable_and_pure(monkeypatch):
    from pathlib import Path

    values, rows = run("T19")
    before = digest(values[0])

    def denied(*args, **kwargs):
        raise AssertionError("pure function attempted IO")

    with monkeypatch.context() as scoped:
        scoped.setattr(Path, "open", denied)
        assert run_evidence_step(evidence_input=values[0], config=PR3Config()) == rows[0]
    assert digest(values[0]) == before
