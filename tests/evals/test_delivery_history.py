import pytest
from conftest import refresh
from pr4_support import put, rows
from test_loader import step

from evals.intelligence_v1.exceptions import ContractError
from evals.intelligence_v1.validate import validate_dataset


@pytest.mark.parametrize("defect,code", [("hash", "HISTORY_SNAPSHOT_MISMATCH"),
    ("identity", "HISTORY_SNAPSHOT_MISMATCH"), ("future_version", "FUTURE_OR_STALE_HISTORY_VERSION"),
    ("scope", "DELIVERY_SCOPE_INVALID"), ("prediction_id", "HISTORY_PREDICTION_ID_MISMATCH"),
    ("target", "HISTORY_TARGET_NOT_FOUND"), ("timeline", "DELIVERY_SCOPE_INVALID")])
def test_history_metadata_rejected_by_prediction_and_full_validator(bundle, defect, code):
    items = rows(bundle, "delivery_items.jsonl")
    member = items[0]["members"][0]
    if defect == "hash":
        member["content_sha256"] = "0"*64
    elif defect == "identity":
        member["document_id"] = "unrelated"
    elif defect == "future_version":
        member.update(doc_version_id="rv:x:2")
    elif defect == "scope":
        member.update(document_id="d01:a", doc_version_id="d01:a:1")
    elif defect == "prediction_id":
        items[0]["event_prediction_id"] = "predicted:wrong"
    elif defect == "target":
        exposures = rows(bundle, "exposures.jsonl")
        exposures[0]["event_prediction_id"] = "predicted:missing"
        put(bundle,"exposures.jsonl",exposures)
    elif defect == "timeline":
        steps = rows(bundle,"steps.jsonl")
        steps.append({**steps[-1], "timeline_id":"OTHER"})
        put(bundle,"steps.jsonl",steps)
    put(bundle,"delivery_items.jsonl",items)
    manifest = refresh(bundle)
    assert code in {e.code for e in validate_dataset(manifest,strict=False).errors}
    with pytest.raises(ContractError,match=f"^{code}$"):
        step(bundle,"D8","REVISIT-7D")


def test_future_unrelated_history_payload_is_not_interpreted(bundle):
    context, documents = step(bundle,"D8","REVISIT-7D")
    from evals.intelligence_v1.baselines import get_ranker
    from evals.intelligence_v1.contracts import BaselineConfig

    before = get_ranker("b4",BaselineConfig()).rank(context,documents)
    items = rows(bundle,"delivery_items.jsonl")
    items.append({"delivery_id":"rv:future", "event_prediction_id":"predicted:future",
                  "members":"FUTURE_PAYLOAD_MUST_NOT_BE_INTERPRETED"})
    put(bundle,"delivery_items.jsonl",items)
    refresh(bundle)
    context, documents = step(bundle,"D8","REVISIT-7D")
    assert get_ranker("b4",BaselineConfig()).rank(context,documents) == before


def test_old_reference_exposure_stays_unresolved_and_never_fills_knowledge():
    context, _ = step(name="D6",timeline="SYN-PR1")
    assert set(context.unresolved_exposure_ids) == {"exposure:included", "exposure:opened"}
    assert context.delivery_history == () and context.persona.knowledge_known == ()
