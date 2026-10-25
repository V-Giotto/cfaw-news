import json

import pytest

from evals.intelligence_g2.pr3.contracts import PR3Config, parse
from evals.intelligence_g2.pr3.extract import extract_claims
from evals.intelligence_g2.pr3.scope import parse_fields

from .support import FIXTURE, inputs_for, make_input, replay_values, run, scenarios


def test_T19_full_quote_percent_attribution_and_no_independent_upgrade():
    value, results = run("T19")
    result = results[0]
    assert len(result.claims) == len(result.citations) == 1
    claim, ref = result.claims[0], result.citations[0]
    original = value[0].grouping_input.replay_input.visible_documents[0].candidate.paragraphs[0].text
    assert claim.statement == ref.quote == original
    assert ref.start == 0 and ref.end == len(original)
    assert claim.proposition.quantities[0].value.normalized_value == "40"
    assert claim.proposition.quantities[0].unit == "percent"
    assert result.assessments[0].verification_state == "source_attributed"
    assert result.assessments[0].independent_support_count == 0
    assert result.assessments[0].semantic_truth == "not_evaluated"


@pytest.mark.parametrize("case", [c["case_id"] for c in scenarios()])
def test_development_frozen_expected_paragraphs_types_and_conflicts(case):
    expected = json.loads((FIXTURE / "reference/expected.json").read_bytes())["cases"]
    _, results = run(case)
    rows = [r for r in expected if r["case_id"] == case]
    for result, row in zip(results, rows, strict=True):
        actual = {(c.doc_version_id, c.statement, c.claim_type) for c in result.claims}
        assert actual == {(c["doc_version_id"], c["statement"], c["claim_type"]) for c in row["claims"]}
        assessments = {a.claim_key: a for a in result.assessments}
        for claim in result.claims:
            ref = next(c for c in row["claims"] if c["doc_version_id"] == claim.doc_version_id)
            assert assessments[claim.claim_key].verification_state == ref["verification_state"]
        assert len(result.conflicts) == row["conflict_count"]
        assert all(a.independent_support_count == 0 for a in result.assessments)


def test_T21_scope_is_preserved_and_does_not_support_universal_capability():
    _, results = run("T21")
    claim = results[0].claims[0]
    assert claim.scope.task.normalized_value == "summarization"
    assert claim.scope.dataset.raw_value == "ToySet"
    assert any("only this task" in c.normalized_value for c in claim.scope.conditions)
    assert "independence_statement_not_verified" in claim.limitations
    assert {link.direction for link in results[0].links} == {"mentions"}
    assert results[0].assessments[0].verification_state == "source_attributed"


def test_T27_no_paragraph_no_fake_fact_and_table_gap():
    _, rows = run("T27")
    assert {c.doc_version_id for c in rows[0].claims} == {"table:1"}
    assert rows[0].claims[0].proposition.quantities == ()
    assert {g.code for g in rows[0].validation.coverage_gaps} >= {"no_citable_paragraph", "table_unavailable"}


@pytest.mark.parametrize("body,code", [
    ("Atlas Tool claims " + "x" * 1100 + " but only in this one case.", "whole_paragraph_quote_limit"),
    ("Atlas Tool release password=TEST_ONLY_PLACEHOLDER_NOT_A_SECRET", "sensitive_text_excluded"),
    ("Unrecognized plain description.", "unsupported_grammar"),
])
def test_excluded_full_paragraph_is_not_truncated_or_redacted_into_a_claim(body, code):
    replay = make_input([{"id": "a", "body": body}])
    _, group = inputs_for([replay])
    result = extract_claims(replay_input=replay, events=group[0].events, config=PR3Config())
    assert result.claims == result.citations == ()
    assert code in {g.code for g in result.coverage_gaps}


def test_T27_summary_is_secondary_and_cannot_supply_measurements():
    # Contract-only synthetic construction; this is not a real-source/live-data claim.
    replay = replay_values("T19")[0]
    wrapped = replay.visible_documents[0]
    candidate = wrapped.candidate.model_copy(update={"content_kind": "feed_summary"})
    replay = replay.model_copy(update={"visible_documents": (wrapped.model_copy(update={"candidate": candidate}),)})
    events = inputs_for(replay_values("T19"))[1][0].events
    result = extract_claims(replay_input=replay, events=events, config=PR3Config())
    assert result.claims[0].claim_type == "other"
    assert result.claims[0].proposition.quantities == ()
    assert result.claims[0].attribution.attribution_kind == "secondary_material"
    assert result.claims[0].attribution.asserted_by_source_id is None


def test_grounded_fields_point_to_actual_characters():
    _, rows = run("T19")
    ref = rows[0].citations[0]
    scope, prop, _ = parse_fields(ref)
    for grounded in (scope.task, scope.dataset, scope.baseline, scope.protocol, scope.hardware,
                     scope.target_version, prop.subject, prop.metric, prop.quantities[0].value):
        assert ref.quote[grounded.start:grounded.end] == grounded.raw_value


def test_strict_extra_fields_and_configuration_are_not_coerced():
    from evals.intelligence_g2.contracts import G2Error

    with pytest.raises(G2Error) as error:
        parse(PR3Config, {"max_quote_chars": "1024"})
    assert error.value.code == "SCHEMA_INVALID"
