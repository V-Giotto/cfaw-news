import json
from datetime import timedelta

import pytest

from evals.intelligence_g2.contracts import (
    G2Config,
    G2Error,
    PredictedRelation,
    check_schemas,
    data,
    digest,
    parse,
)
from evals.intelligence_g2.validate_output import validate_relation

from .support import assert_error, input_at


def test_G2_T04_schemas_are_derived_and_frozen():
    assert check_schemas()
    assert G2Config.model_config == {"extra": "forbid", "strict": True, "frozen": True}


@pytest.mark.parametrize("relation", ["exact_duplicate", "syndicated",
    "same_event_different_evidence", "related_distinct_event", "unrelated", "uncertain"])
def test_G2_T06_relation_contract_has_prediction_semantics(relation):
    value = input_at(step="D1")
    left, right = sorted(value.context.candidate_doc_version_ids)
    row = PredictedRelation(left_doc_version_id=left, right_doc_version_id=right,
        predicted_relation=relation, method="schema_test_only", evidence_reasons=("unmeasured",),
        as_of=value.context.as_of)
    assert validate_relation(row, value) == row
    assert row.confidence is None
    with pytest.raises(G2Error) as caught:
        parse(PredictedRelation, {**data(row), "reference_event_id": "forbidden"})
    assert_error(caught, "SCHEMA_INVALID", "input", "reference_event_id")
    with pytest.raises(G2Error) as caught:
        validate_relation(row.model_copy(update={"right_doc_version_id": "zz:missing"}), value)
    assert_error(caught, "GROUP_MEMBERS_INVALID", "identity", "relation.doc_version_ids")
    with pytest.raises(G2Error) as caught:
        validate_relation(row.model_copy(update={"as_of": row.as_of + timedelta(days=1)}), value)
    assert_error(caught, "G2_CONTEXT_MISMATCH", "identity", "relation.as_of")
    with pytest.raises(G2Error) as caught:
        parse(PredictedRelation, row.model_copy(update={"right_doc_version_id": left}))
    assert_error(caught, "GROUP_MEMBERS_INVALID", "input", "right_doc_version_id")
    for confidence in (1.01, -0.01, float("inf")):
        with pytest.raises(G2Error) as caught:
            parse(PredictedRelation, row.model_copy(update={"confidence": confidence}))
        assert caught.value.code == "SCHEMA_INVALID"


@pytest.mark.parametrize("revision_field", ["config_revision", "pipeline_revision",
                                           "identity_revision", "generator_revision"])
def test_G2_T04_unsupported_revisions_are_not_silent(revision_field):
    with pytest.raises(G2Error) as caught:
        parse(G2Config, {**data(G2Config()), revision_field: "unknown"})
    assert_error(caught, "UNSUPPORTED_REVISION", "input", revision_field)


def test_G2_T04_config_digest_and_strict_json():
    from evals.intelligence_g2.contracts import read_json

    assert digest(G2Config()) == digest(data(G2Config()))
    for raw in (b'{"x":1,"x":2}', b'{"x":NaN}', b'\xef\xbb\xbf{}', b'not json'):
        with pytest.raises(G2Error) as caught:
            read_json(raw)
        assert_error(caught, "INVALID_JSON")
    with pytest.raises(G2Error) as caught:
        parse(G2Config, {**data(G2Config()), "max_quote_chars": "160"})
    assert_error(caught, "SCHEMA_INVALID", "input", "max_quote_chars")
    assert "160" in json.dumps(G2Config.model_json_schema())


@pytest.mark.parametrize("path", ["../escape", "/absolute", "C:/escape", ".env",
                                 ".local/private", "dir\\escape"])
def test_G2_T10_manifest_and_diagnostic_paths_are_relative(path):
    from evals.intelligence_g2.contracts import ArtifactDigest, ValidationIssue

    for model, values in ((ArtifactDigest, {"path": path, "sha256": "0" * 64,
                                             "byte_count": 0, "record_count": None}),
                           (ValidationIssue, {"code": "SCHEMA_INVALID", "stage": "input",
                                              "path": path})):
        with pytest.raises(G2Error) as caught:
            parse(model, values)
        assert_error(caught, "OUTPUT_PATH_INVALID", "input", "path")
