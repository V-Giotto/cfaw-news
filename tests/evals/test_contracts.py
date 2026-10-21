import json

import pytest
from conftest import BASE
from pydantic import ValidationError

from evals.intelligence_v1.contracts import (
    SCHEMA_MODELS,
    DocumentVersion,
    GoldLabel,
    PersonaVersion,
    check_schemas,
)


def test_derived_schemas_match_exactly():
    assert len(SCHEMA_MODELS) == 27
    assert check_schemas()


@pytest.mark.parametrize("change", [
    {"attention_budget_seconds": True}, {"attention_budget_seconds": "420"},
    {"attention_budget_seconds": 0}, {"persona_origin": "inferred"},
    {"locale": "  "}, {"unexpected": "field"},
])
def test_persona_rejects_bad_types_and_fields(bundle, change):
    rows = [json.loads(x) for x in (bundle / BASE / "personas.jsonl").read_bytes().splitlines()]
    with pytest.raises(ValidationError):
        PersonaVersion.model_validate_json(json.dumps({**rows[0], **change}))


def test_required_nullable_and_immutable_nested_collections(bundle):
    raw = json.loads((bundle / BASE / "documents.jsonl").read_bytes().splitlines()[0])
    row = DocumentVersion.model_validate_json(json.dumps(raw))
    assert isinstance(row.paragraphs, tuple)
    with pytest.raises(ValidationError):
        row.paragraphs[0].text = "changed"
    with pytest.raises(ValidationError):
        row.title = "changed"
    del raw["cleaner_revision"]
    with pytest.raises(ValidationError):
        DocumentVersion.model_validate_json(json.dumps(raw))


@pytest.mark.parametrize("change", [{"relevance": True}, {"relevance": 4},
                                   {"tier": "excellent"}, {"graded_relevance": -1}])
def test_gold_scores_and_enums_are_strict(bundle, change):
    raw = json.loads((bundle / BASE / "gold.jsonl").read_bytes().splitlines()[0])
    with pytest.raises(ValidationError):
        GoldLabel.model_validate_json(json.dumps({**raw, **change}))
