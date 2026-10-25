from datetime import timedelta, timezone

import pytest

from evals.intelligence_g2.contracts import G2Config, G2Error, data, digest
from evals.intelligence_g2.pipeline import run_g2_offline
from evals.intelligence_g2.validate_output import checked_input
from evals.intelligence_v1.exceptions import ContractError
from evals.intelligence_v1.loader import load_bundle

from .support import (
    SOURCE,
    assert_error,
    copied_bundle,
    input_at,
    project,
    refresh_copy,
    rows,
    save_rows,
)


def test_G2_T01_inclusive_boundary_offset_and_late_observation():
    value = input_at()
    doc = value.visible_documents[0].candidate
    cutoff = doc.available_at
    context = value.context.model_copy(update={"as_of": cutoff,
        "time_window_start": cutoff, "time_window_end": cutoff, "source_coverage": ()})
    exact = value.model_copy(update={"context": context, "source_coverage_digest": digest([])})
    result = run_g2_offline(replay_input=exact, config=G2Config())
    assert result.validation.ok
    raw = data(exact)
    instant = cutoff.astimezone(timezone(timedelta(hours=8)))
    raw["context"]["as_of"] = instant.isoformat()
    assert run_g2_offline(replay_input=raw, config=G2Config()) == result
    future = doc.model_copy(update={"available_at": cutoff + timedelta(microseconds=1)})
    injected = exact.model_copy(update={"visible_documents": (
        value.visible_documents[0].model_copy(update={"candidate": future}),)})
    with pytest.raises(G2Error) as caught:
        run_g2_offline(replay_input=injected, config=G2Config())
    assert_error(caught, "FUTURE_VERSION", "bridge", "candidate.available_at")
    assert caught.value.record_id == doc.doc_version_id
    raw["context"]["as_of"] = cutoff.replace(tzinfo=None).isoformat()
    with pytest.raises(G2Error) as caught:
        checked_input(raw, G2Config())
    assert caught.value.code == "NAIVE_DATETIME"


def test_G2_T02_latest_version_and_stable_identity():
    before = run_g2_offline(replay_input=input_at(step="D4"), config=G2Config())
    after = run_g2_offline(replay_input=input_at(step="D5"), config=G2Config())
    a = next(e for e in before.events if "d01:a:1" in e.member_doc_version_ids)
    b = next(e for e in after.events if "d01:a:2" in e.member_doc_version_ids)
    assert a.event_key == b.event_key
    assert a.event_revision != b.event_revision
    assert a.anchor_doc_version_id == b.anchor_doc_version_id == "d01:a:1"
    assert a.first_visible_at == b.first_visible_at
    assert all(r.doc_version_id != "d01:a:2" for i in before.items for r in i.evidence_refs)
    assert all(r.doc_version_id != "d01:a:1" for i in after.items for r in i.evidence_refs)


def test_G2_T02_future_body_poison_is_not_projected(tmp_path):
    root = copied_bundle(tmp_path)
    docs = rows(root, "versions/documents.jsonl")
    next(d for d in docs if d["doc_version_id"] == "d01:a:2")["paragraphs"] = (
        "FUTURE_PAYLOAD_MUST_NOT_BE_INTERPRETED")
    save_rows(root, "versions/documents.jsonl", docs)
    refresh_copy(root)
    early = input_at(root=root)
    assert "FUTURE_PAYLOAD" not in early.model_dump_json()
    assert run_g2_offline(replay_input=early, config=G2Config()).validation.ok
    with pytest.raises(ContractError) as caught:
        input_at(root=root, step="D5")
    assert caught.value.code == "SCHEMA_INVALID"


def test_G2_T01_future_object_is_rejected_before_body_serialization():
    value = input_at()
    original = value.visible_documents[0]

    class FutureMetadataOnly:
        doc_version_id = "future:body-guard"
        available_at = value.context.as_of + timedelta(days=1)

        def __getattr__(self, name):
            if name in {"title", "text_excerpt", "paragraphs", "model_dump", "model_dump_json"}:
                pytest.fail("future body serialization attempted")
            raise AttributeError(name)

    injected = value.model_copy(update={"visible_documents": (
        original.model_copy(update={"candidate": FutureMetadataOnly()}),)})
    with pytest.raises(G2Error) as caught:
        run_g2_offline(replay_input=injected, config=G2Config())
    assert_error(caught, "FUTURE_VERSION", "bridge", "candidate.available_at")


@pytest.mark.parametrize("kind,code", [("persona", "FUTURE_PERSONA"),
    ("exposure", "FUTURE_EXPOSURE"), ("coverage", "FUTURE_COVERAGE"),
    ("delivery", "FUTURE_DELIVERY")])
def test_G2_T03_injected_nested_future_context_is_revalidated(kind, code):
    value = input_at("REVISIT-7D", "D8")
    context = value.context
    future = context.as_of + timedelta(days=1)
    if kind == "persona":
        context = context.model_copy(update={"persona": context.persona.model_copy(
            update={"available_at": future})})
    elif kind == "exposure":
        assert context.exposure_history
        row = context.exposure_history[0].model_copy(update={"occurred_at": future})
        context = context.model_copy(update={"exposure_history": (row,)})
    elif kind == "coverage":
        assert context.source_coverage
        row = context.source_coverage[0].model_copy(update={"observed_at": future})
        context = context.model_copy(update={"source_coverage": (row,)})
    else:
        assert context.delivery_history
        row = context.delivery_history[0].model_copy(update={"delivery_generated_at": future})
        context = context.model_copy(update={"delivery_history": (row,)})
    with pytest.raises(G2Error) as caught:
        checked_input(value.model_copy(update={"context": context}), G2Config())
    assert caught.value.code == code
    assert caught.value.stage == "bridge"


def test_G2_T03_loader_filters_future_exposure_and_persona_does_not_change_facts():
    value = input_at("SYN-PR1", "D6")
    assert all(e.occurred_at <= value.context.as_of for e in value.context.exposure_history)
    assert [e.kind for e in value.context.exposure_history] == ["included", "opened"]
    value = input_at()
    old = run_g2_offline(replay_input=value, config=G2Config())
    persona = value.context.persona.model_copy(update={"current_goals": ("another synthetic goal",)})
    changed = value.model_copy(update={"context": value.context.model_copy(update={"persona": persona})})
    new = run_g2_offline(replay_input=changed, config=G2Config())
    assert old.events == new.events and old.bundles == new.bundles and old.items == new.items


def test_G2_T04_bridge_canonical_order_and_exact_projection():
    value = input_at(step="D1")
    candidates = tuple(d.candidate for d in value.visible_documents)
    assert project(step="D1", candidates=candidates[::-1]) == value
    changed = candidates[0].model_copy(update={"title": "changed projection"})
    with pytest.raises(G2Error) as caught:
        project(step="D1", candidates=(changed, candidates[1]))
    assert_error(caught, "G2_CONTEXT_MISMATCH", "bridge", "candidate")
    with pytest.raises(G2Error) as caught:
        project(step="D1", candidates=(candidates[0],))
    assert_error(caught, "VISIBLE_SET_MISMATCH", "bridge", "candidate_doc_version_ids")


def test_G2_T06_duplicates_and_invalid_identity_seed():
    value = input_at()
    with pytest.raises(G2Error) as caught:
        checked_input(value.model_copy(update={"visible_documents": value.visible_documents * 2}),
                      G2Config())
    assert_error(caught, "DUPLICATE_ID", "bridge", "visible_documents")
    for changes in ({"anchor_doc_version_id": "missing"},
                    {"first_visible_at": value.context.as_of + timedelta(days=1)},
                    {"document_id": "missing"}):
        seed = value.identity_seeds[0].model_copy(update=changes)
        with pytest.raises(G2Error) as caught:
            checked_input(value.model_copy(update={"identity_seeds": (seed,)}), G2Config())
        assert_error(caught, "G2_IDENTITY_SEED_INVALID", "identity", "identity_seeds")


def test_G2_T05_unfrozen_bundle_is_not_accepted(tmp_path):
    from evals.intelligence_g2.contracts import json_bytes
    from evals.intelligence_v1.hashing import sha256_bytes

    root = copied_bundle(tmp_path)
    path = root / "manifests/dataset_manifest.json"
    import json

    manifest = json.loads(path.read_bytes())
    manifest["status"] = "draft"
    path.write_bytes(json_bytes(manifest))
    with pytest.raises(G2Error) as caught:
        project(root)
    assert_error(caught, "G2_INPUT_NOT_FROZEN", "bridge", "manifest.status")
    bundle = load_bundle(SOURCE / "manifests/dataset_manifest.json",
                         manifest_sha256=sha256_bytes((SOURCE / "manifests/dataset_manifest.json").read_bytes()))
    assert bundle.manifest.status == "frozen"
