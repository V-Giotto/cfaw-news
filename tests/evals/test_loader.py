"""PR3 historical selection expectations, independent of the loader."""

import json

import pytest
from conftest import SOURCE, refresh

from evals.intelligence_v1.exceptions import ContractError
from evals.intelligence_v1.hashing import canonical_json, sha256_bytes


def loaded(root=SOURCE):
    from evals.intelligence_v1.loader import load_bundle

    path = root / "manifests/dataset_manifest.json"
    return load_bundle(path, manifest_sha256=sha256_bytes(path.read_bytes()))


def step(root=SOURCE, name="D8", timeline="DEV-01"):
    from evals.intelligence_v1.loader import load_step

    bundle = loaded(root)
    return load_step(bundle, timeline_id=timeline, step_id=name, config=bundle.config)


def test_DEV01_replay_exact_sets_and_latest_persona():
    expected = {
        "D0": ["a:1"], "D1": ["a:1", "b:1"],
        "D3": ["a:1", "b:1", "c:1", "d:1"],
        "D4": ["a:1", "b:1", "c:1", "d:1", "e:1"],
        "D5": ["a:2", "b:1", "c:1", "d:1", "e:1"],
        "D8": ["a:2", "b:1", "c:1", "d:1", "e:1", "f:1"],
    }
    for name, ids in expected.items():
        context, candidates = step(name=name)
        assert [d.doc_version_id for d in candidates] == ["d01:" + i for i in ids]
        assert context.persona.persona_version_id.endswith(":2" if name in {"D5", "D8"}
                                                          else ":1")
        assert context.exposure_history == ()
        assert context.candidate_doc_version_ids == tuple(d.doc_version_id for d in candidates)
    context, candidates = step(name="D8")
    assert any(d.available_at < context.time_window_start for d in candidates)
    assert any(c.status == "service_offline" for c in context.source_coverage)


def test_history_is_scoped_filtered_and_has_no_fixture_gold_target():
    context, _ = step(name="D6", timeline="SYN-PR1")
    assert [e.kind for e in context.exposure_history] == ["included", "opened"]
    assert all(e.event_prediction_id is None for e in context.exposure_history)
    assert "reference_event_id" not in context.model_dump_json()
    assert "knowledge_known\":[]" in context.persona.model_dump_json()


def test_snapshot_mismatch_fails_without_repair(bundle):
    path = bundle / "timelines/steps.jsonl"
    records = [json.loads(x) for x in path.read_bytes().splitlines()]
    records[0]["visible_doc_version_ids"] = []
    path.write_bytes("".join(canonical_json(r) + "\n" for r in records).encode())
    refresh(bundle)
    with pytest.raises(ContractError, match="VISIBLE_SET_MISMATCH"):
        step(bundle, "D0")
    assert json.loads(path.read_bytes().splitlines()[0])["visible_doc_version_ids"] == []


def test_future_body_is_not_validated_or_scored_in_earlier_step(bundle):
    path = bundle / "versions/documents.jsonl"
    records = [json.loads(x) for x in path.read_bytes().splitlines()]
    # A trusted all-dataset validator rejects this; a past prediction never inspects it.
    records[1]["paragraphs"] = "FUTURE_POISON_NOT_A_PARAGRAPH_LIST"
    path.write_bytes("".join(canonical_json(r) + "\n" for r in records).encode())
    refresh(bundle)
    assert [d.doc_version_id for d in step(bundle, "D0")[1]] == ["d01:a:1"]
    with pytest.raises(ContractError, match="SCHEMA_INVALID"):
        step(bundle, "D5")


def test_prediction_projection_rejects_reference_fields():
    from pydantic import ValidationError

    from evals.intelligence_v1.contracts import CandidateDocumentVersion, ReplayContext

    context, candidates = step(name="D0")
    for field in ("family_id", "event_id", "future_status"):
        with pytest.raises(ValidationError):
            CandidateDocumentVersion.model_validate_json(canonical_json({
                **candidates[0].model_dump(mode="json"), field: "poison"}))
        with pytest.raises(ValidationError):
            ReplayContext.model_validate_json(canonical_json({
                **context.model_dump(mode="json"), field: "poison"}))


def test_pin_and_candidate_tamper_are_rejected(bundle):
    from evals.intelligence_v1.loader import load_bundle

    path = bundle / "manifests/dataset_manifest.json"
    pin = sha256_bytes(path.read_bytes())
    with pytest.raises(ContractError, match="MANIFEST_SHA_MISMATCH"):
        load_bundle(path, manifest_sha256="0" * 64)
    documents = bundle / "versions/documents.jsonl"
    documents.write_bytes(documents.read_bytes() + b" ")
    with pytest.raises(ContractError, match="SHA_MISMATCH"):
        load_bundle(path, manifest_sha256=pin)


def test_future_exposure_payload_is_not_interpreted_in_the_past(bundle):
    path = bundle / "fixtures/valid/minimal_three_step/exposures.jsonl"
    records = [json.loads(x) for x in path.read_bytes().splitlines()]
    records[-1]["kind"] = "FUTURE_INVALID_PAYLOAD"
    path.write_bytes("".join(canonical_json(r) + "\n" for r in records).encode())
    refresh(bundle)
    context, _ = step(bundle, name="D6", timeline="SYN-PR1")
    assert [e.kind for e in context.exposure_history] == ["included", "opened"]


def test_future_coverage_is_rejected_before_reason_payload(bundle):
    path = bundle / "timelines/coverage_windows.jsonl"
    records = [json.loads(x) for x in path.read_bytes().splitlines()]
    records[0].update(observed_at="2030-01-01T00:00:00Z", reason={"future": "poison"})
    path.write_bytes("".join(canonical_json(r) + "\n" for r in records).encode())
    refresh(bundle)
    with pytest.raises(ContractError, match="FUTURE_COVERAGE"):
        step(bundle, "D1")
