import copy
import json

import pytest

from evals.intelligence_g2.contracts import G2Config, G2Error, digest
from evals.intelligence_g2.pipeline import run_g2_offline
from evals.intelligence_g2.validate_output import checked_input, validate_output
from evals.intelligence_v1.contracts import Paragraph
from evals.intelligence_v1.hashing import content_sha256
from evals.intelligence_v1.loader import load_bundle

from .support import SOURCE, assert_error, input_at


def run(value):
    return run_g2_offline(replay_input=value, config=G2Config())


def no_body(value):
    doc = value.visible_documents[0]
    candidate = doc.candidate.model_copy(update={"paragraphs": (), "text_excerpt": None,
                                                "content_sha256": None})
    lineage = tuple(v.model_copy(update={"content_sha256": None})
                    if v.doc_version_id == candidate.doc_version_id else v
                    for v in doc.visible_lineage)
    return value.model_copy(update={"visible_documents": (doc.model_copy(update={
        "candidate": candidate, "visible_lineage": lineage}),)})


def test_G2_T04_pure_pipeline_has_no_io_and_input_is_immutable(monkeypatch):
    from pathlib import Path

    value = input_at()
    before = value.model_dump_json()

    def deny(*args, **kwargs):
        pytest.fail("pure function attempted file IO")

    with monkeypatch.context() as scoped:
        scoped.setattr(Path, "open", deny)
        scoped.setattr(Path, "stat", deny)
        scoped.setattr(Path, "lstat", deny)
        old = run(value)
        assert run(value) == old
    assert value.model_dump_json() == before


def test_G2_T04_added_document_or_order_does_not_rekey_existing_event():
    first, later = run(input_at()), run(input_at(step="D1"))
    old = first.events[0]
    current = next(e for e in later.events if e.member_doc_version_ids == old.member_doc_version_ids)
    assert old.event_key == current.event_key
    assert len(later.events) == 2  # No silent use of G1 reference-event grouping.
    value = input_at(step="D1")
    assert run(value.model_copy(update={"visible_documents": value.visible_documents[::-1],
        "sources": value.sources[::-1], "identity_seeds": value.identity_seeds[::-1]})) == later


@pytest.mark.parametrize("defect", ["missing", "duplicate", "foreign", "empty"])
def test_G2_T06_event_partition_is_exact(defect):
    value = input_at(step="D1")
    result = run(value)
    events = list(result.events)
    if defect == "missing":
        events.pop()
    elif defect == "duplicate":
        events[1] = events[1].model_copy(update={
            "member_doc_version_ids": events[0].member_doc_version_ids})
    elif defect == "foreign":
        events[0] = events[0].model_copy(update={"member_doc_version_ids": ("foreign",)})
    else:
        events = []
    with pytest.raises(G2Error) as caught:
        validate_output(result.model_copy(update={"events": tuple(events)}), value, G2Config())
    assert_error(caught, "GROUP_MEMBERS_INVALID", "identity", "member_doc_version_ids")


@pytest.mark.parametrize("defect,code,field", [
    ("paragraph", "CITATION_NOT_FOUND", "paragraph_id"),
    ("document", "CITATION_NOT_FOUND", "doc_version_id"),
    ("other_event", "G2_EVIDENCE_NOT_IN_EVENT", "doc_version_id"),
    ("quote", "G2_QUOTE_MISMATCH", "quote"),
    ("quote_sha", "G2_QUOTE_MISMATCH", "quote"),
    ("supports", "G2_PLACEHOLDER_STATUS_INVALID", "direction"),
])
def test_G2_T07_invalid_reference_is_rejected(defect, code, field):
    value = input_at(step="D1")
    result = run(value)
    bundle = result.bundles[0]
    ref = bundle.unverified_refs[0]
    changes = {
        "paragraph": {"paragraph_id": "p-missing"},
        "document": {"doc_version_id": "missing"},
        "other_event": {"doc_version_id": result.bundles[1].doc_version_ids[0]},
        "quote": {"quote": "fabricated performance 9999%"},
        "quote_sha": {"quote_sha256": "0" * 64},
        "supports": {"direction": "supports"},
    }[defect]
    changed = bundle.model_copy(update={"unverified_refs": (ref.model_copy(update=changes),)})
    with pytest.raises(G2Error) as caught:
        validate_output(result.model_copy(update={"bundles": (changed, *result.bundles[1:])}),
                        value, G2Config())
    assert_error(caught, code, "evidence", field)


def test_G2_T07_fake_facts_and_supported_focus_are_rejected():
    value = input_at()
    result = run(value)
    with pytest.raises(G2Error) as caught:
        validate_output(result.model_copy(update={"items": (
            result.items[0].model_copy(update={"what_happened": "已证实性能提升9999%"}),)}),
            value, G2Config())
    assert_error(caught, "G2_QUOTE_MISMATCH", "item", "what_happened")
    for changes in ({"tier_candidate": "focus"}, {"evidence_status": "supported"}):
        with pytest.raises(G2Error) as caught:
            validate_output(result.model_copy(update={"items": (
                result.items[0].model_copy(update=changes),)}), value, G2Config())
        assert caught.value.code == "G2_PLACEHOLDER_STATUS_INVALID"
    claim = result.bundles[0].claim_candidates[0].model_copy(
        update={"verification_state": "independently_supported"})
    with pytest.raises(G2Error) as caught:
        validate_output(result.model_copy(update={"bundles": (
            result.bundles[0].model_copy(update={"claim_candidates": (claim,)}),)}),
            value, G2Config())
    assert caught.value.code == "G2_PLACEHOLDER_STATUS_INVALID"


def test_G2_T08_empty_candidates_and_unknown_coverage_are_not_no_change():
    value = input_at()
    context = value.context.model_copy(update={"candidate_doc_version_ids": (), "source_coverage": ()})
    value = value.model_copy(update={"context": context, "visible_documents": (),
        "identity_seeds": (), "source_coverage_digest": digest([])})
    result = run(value)
    assert result.events == result.bundles == result.items == ()
    assert result.validation.ok and result.validation.counts["coverage_gaps"] == 1
    assert result.validation.semantic_support == "not_evaluated"
    assert "no_change" not in result.model_dump_json()
    fake = run(input_at()).items[0]
    with pytest.raises(G2Error) as caught:
        validate_output(result.model_copy(update={"items": (fake,)}), value, G2Config())
    assert_error(caught, "GROUP_MEMBERS_INVALID", "output", "event_bundle_item_coverage")


def test_G2_T08_no_paragraph_never_fabricates_excerpt_locator():
    value = no_body(input_at())
    result = run(value)
    item = result.items[0]
    assert item.tier_candidate == "hold" and item.evidence_status == "insufficient"
    assert item.what_happened is None and item.why_it_matters is None
    assert item.evidence_refs == item.claim_keys == ()
    assert result.bundles[0].claim_candidates == ()
    assert "no_citable_paragraph" in item.uncertainties
    # A summary is retained in input but does not become a fake paragraph.
    doc = value.visible_documents[0]
    candidate = doc.candidate.model_copy(update={"text_excerpt": "Summary without paragraphs"})
    sha = content_sha256(candidate.title, candidate.text_excerpt, ())
    candidate = candidate.model_copy(update={"content_sha256": sha})
    doc = doc.model_copy(update={"candidate": candidate, "visible_lineage": (
        doc.visible_lineage[0].model_copy(update={"content_sha256": sha}),)})
    assert run(value.model_copy(update={"visible_documents": (doc,)})).items[0].what_happened is None


@pytest.mark.parametrize("defect,code,field", [
    ("origin", "ORIGIN_MISMATCH", "record_origin"),
    ("rights", "ORIGIN_MISMATCH", "redistribution_rights"),
    ("source", "SOURCE_NOT_FOUND", "candidate.source_id"),
    ("source_type", "SOURCE_TYPE_MISMATCH", "candidate.source_type"),
])
def test_G2_T09_synthetic_origin_rights_and_source_are_checked(defect, code, field):
    value = input_at()
    doc = value.visible_documents[0]
    if defect == "origin":
        doc = doc.model_copy(update={"record_origin": "real"})
    elif defect == "rights":
        doc = doc.model_copy(update={"redistribution_rights": "permitted"})
    else:
        changes = {"source_id": "missing"} if defect == "source" else {"source_type": "other"}
        doc = doc.model_copy(update={"candidate": doc.candidate.model_copy(update=changes)})
    with pytest.raises(G2Error) as caught:
        checked_input(value.model_copy(update={"visible_documents": (doc,)}), G2Config())
    assert_error(caught, code, "bridge", field)


def real_metadata(value, *, rights="metadata_only"):
    """Synthetic *test scenario* describing a real-origin metadata record; no live provenance claim."""
    value = no_body(value)
    doc = value.visible_documents[0]
    candidate = doc.candidate.model_copy(update={"canonical_url": "https://github.blog/example",
        "content_kind": "feed_summary", "source_id": "github-blog", "source_type": "official"})
    doc = doc.model_copy(update={"candidate": candidate, "record_origin": "real",
        "redistribution_rights": rights, "provenance_uri": "https://github.blog/example"})
    sources = tuple(s.model_copy(update={"redistribution_rights": rights, "allowed_use": ("metadata",)})
                    if s.source_id == "github-blog" else s for s in value.sources)
    return value.model_copy(update={"visible_documents": (doc,), "sources": sources})


def test_G2_T09_metadata_only_and_excerpt_limit():
    value = real_metadata(input_at())
    assert run(value).items[0].evidence_status == "insufficient"
    assert run(value).items[0].record_origin == "real"
    for rights, expected in (("metadata_only", "RIGHTS_USE_NOT_ALLOWED"),
                             ("unknown", "RIGHTS_UNKNOWN_FULLTEXT"),
                             ("excerpt_only", "RIGHTS_USE_NOT_ALLOWED")):
        value = real_metadata(input_at(), rights=rights)
        doc = value.visible_documents[0]
        paragraphs = (Paragraph(paragraph_id="p1", text="A source-provided short excerpt."),)
        sha = content_sha256(doc.candidate.title, None, paragraphs)
        candidate = doc.candidate.model_copy(update={"paragraphs": paragraphs,
            "content_sha256": sha, "content_kind": "quoted_excerpt"})
        doc = doc.model_copy(update={"candidate": candidate, "visible_lineage": (
            doc.visible_lineage[0].model_copy(update={"content_sha256": sha}),)})
        sources = value.sources
        if rights == "excerpt_only":
            sources = tuple(s.model_copy(update={"allowed_use": ("metadata", "excerpt"),
                "max_excerpt_chars": len(paragraphs[0].text) - 1}) if s.source_id == "github-blog"
                else s for s in sources)
        with pytest.raises(G2Error) as caught:
            checked_input(value.model_copy(update={"visible_documents": (doc,), "sources": sources}),
                          G2Config())
        assert caught.value.code == expected


def test_G2_T07_long_quote_is_raw_bounded_and_marked_truncated():
    value = input_at()
    doc = value.visible_documents[0]
    paragraph = Paragraph(paragraph_id="p1", text="e\u0301 + 原样 Unicode " * 30)
    sha = content_sha256(doc.candidate.title, None, (paragraph,))
    candidate = doc.candidate.model_copy(update={"text_excerpt": None,
        "paragraphs": (paragraph,), "content_sha256": sha})
    doc = doc.model_copy(update={"candidate": candidate, "visible_lineage": (
        doc.visible_lineage[0].model_copy(update={"content_sha256": sha}),)})
    claim = run(value.model_copy(update={"visible_documents": (doc,)})).bundles[0].claim_candidates[0]
    assert claim.statement == paragraph.text[:160] and len(claim.statement) == 160
    assert "excerpt_truncated" in claim.limitations
    assert claim.verification_state == "unverified"


def test_G2_T01_T10_all_35_frozen_steps():
    from evals.intelligence_g2.bridge import project_step
    from evals.intelligence_g2.contracts import G1_PIN

    bundle = load_bundle(SOURCE / "manifests/dataset_manifest.json", manifest_sha256=G1_PIN)
    assert len(bundle.steps) == 35
    for step in bundle.steps:
        value = project_step(bundle, manifest_sha256=G1_PIN, timeline_id=step.timeline_id,
                              step_id=step.step_id, config=G2Config())
        result = run(value)
        assert result.validation.ok
        assert result.validation.counts["candidates"] == len(step.visible_doc_version_ids)
        assert all(item.tier_candidate == "hold" for item in result.items)
        assert all(ref.doc_version_id in step.visible_doc_version_ids
                   for item in result.items for ref in item.evidence_refs)


def test_G2_T08_frozen_synthetic_fixture_expectations():
    from evals.intelligence_g2.contracts import PACKAGE
    from evals.intelligence_v1.hashing import sha256_bytes

    directory = PACKAGE / "fixtures/pr1/v1"
    manifest = json.loads((directory / "manifest.json").read_bytes())
    assert manifest["record_origin"] == "synthetic"
    assert manifest["label_origin"] == "synthetic_fixture"
    assert manifest["review_origin"] == "ai_development"
    for name, sha in manifest["file_sha256"].items():
        assert sha256_bytes((directory / name).read_bytes()) == sha
    for case in json.loads((directory / "cases.json").read_bytes()):
        result = run(copy.deepcopy(case["input"]))
        assert len(result.events) == case["expected"]["event_count"], case["case_id"]
        assert result.validation.counts["claims"] == case["expected"]["claim_count"]
        assert [i.evidence_status for i in result.items] == case["expected"]["evidence_status"]
