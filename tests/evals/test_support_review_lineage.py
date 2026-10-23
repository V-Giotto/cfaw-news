"""Fabricated contract probes only; never substitute these for human submissions."""

from copy import deepcopy

import pytest
from conftest import refresh
from pr5_support import complete_contract_probe, save_rows

from evals.intelligence_v1.annotations import audit_annotations, submission_bytes
from evals.intelligence_v1.contracts import Annotation, ClaimReview, SupportReview
from evals.intelligence_v1.hashing import canonical_json, sha256_bytes


def claim_hash(row):
    claim = ClaimReview.model_validate_json(canonical_json(row))
    return sha256_bytes(canonical_json(claim.model_dump(mode="json")).encode("utf-8"))


def support_probe(bundle, variant="wording"):
    _, annotations, _, _, session = complete_contract_probe(bundle)
    selected = [a for a in annotations if a["timeline_id"] == "DEV-02" and a["step_id"] == "D2"
                and "d02:release:2" in a["initial_label"]["document_version_ids"]]
    assert len(selected) == 2
    original = dict(claim_text="The new release corrects the compatibility statement.",
        evidence_refs=[dict(doc_version_id="d02:release:2", paragraph_id="p1", direction="supports"),
                       dict(doc_version_id="d02:release:1", paragraph_id="p1", direction="mentions")],
        scope="This synthetic project and its currently visible version only.",
        semantic_support="supported", limitations=["Synthetic contract probe; not human evidence."])
    other = deepcopy(original)
    if variant in {"wording", "third-final"}:
        other["claim_text"] = "Compatibility was corrected in the current version."
    elif variant == "citation-subset":
        other["evidence_refs"] = other["evidence_refs"][:1]
    elif variant == "citation-order":
        other["evidence_refs"].reverse()
    elif variant == "scope":
        other["scope"] = "Only this visible project release; no extrapolation."
    for annotation, claim in zip(selected, [original, other], strict=True):
        annotation["initial_label"]["claim_reviews"] = [claim]
    review = dict(support_review_id="support-alignment-contract-probe", timeline_id="DEV-02", step_id="D2",
        persona_version_id=selected[0]["persona_version_id"], annotation_version=selected[0]["annotation_version"],
        prior_annotation_ids=[a["annotation_id"] for a in selected],
        **{key: original[key] for key in ["claim_text", "evidence_refs", "scope", "semantic_support"]},
        reason="Both original claims were reviewed; preserve this scoped final judgment. TEST ONLY.",
        reviewed_by="contract-probe-joint-review", reviewed_at="2026-10-22T03:30:00Z",
        source_claim_alignment=dict(
            sources=[dict(annotation_id=a["annotation_id"], claim_sha256=claim_hash(c))
                     for a, c in zip(selected, [original, other], strict=True)],
            reason="Explicit joint correspondence confirmed by the synthetic test double, not fuzzy matching.",
            aligned_by="contract-probe-joint-review", aligned_at="2026-10-22T03:00:00Z"))
    if variant == "third-final":
        review["claim_text"] = "The visible release explicitly replaces its old compatibility statement."
    return annotations, session, review, selected


def persist(bundle, annotations, session, review):
    for participant in session["participants"]:
        participant["submission_sha256"] = sha256_bytes(submission_bytes([
            Annotation.model_validate_json(canonical_json(a)) for a in annotations
            if a["annotator_id"] == participant["annotator_id"]]))
    save_rows(bundle, "labels/g1a_v1/annotations.jsonl", annotations)
    save_rows(bundle, "labels/g1a_v1/support_reviews.jsonl", [review])
    (bundle / "labels/review_session.json").write_bytes((canonical_json(session)+"\n").encode())
    return refresh(bundle)


@pytest.mark.parametrize("variant", ["wording", "citation-subset", "citation-order", "scope", "third-final"])
def test_T17_explicit_support_alignment_preserves_distinct_initial_claims(bundle, variant):
    from evals.intelligence_v1.validate import validate_dataset

    annotations, session, review, _ = support_probe(bundle, variant)
    path = persist(bundle, annotations, session, review)
    before = (bundle / "labels/g1a_v1/annotations.jsonl").read_bytes()
    audit = audit_annotations(path, manifest_sha256=sha256_bytes(path.read_bytes()))
    assert audit["errors"] == []
    assert audit["human_gate"] == "PASS"  # Complete fabricated attestation, never real people.
    assert audit["support_review_count"] == 1
    assert audit["semantic_support"]["value"] == 1
    assert audit["semantic_support"]["denominator"] == 1
    assert validate_dataset(path, strict=True).ok
    assert (bundle / "labels/g1a_v1/annotations.jsonl").read_bytes() == before


@pytest.mark.parametrize("defect", ["missing-alignment", "bad-hash", "missing-annotation", "one-side",
    "duplicate-source", "extra-annotation", "wrong-step", "before-freeze", "after-review",
    "duplicate-claim", "future-final", "other-family-final", "missing-paragraph",
    "changed-original-after-hash"])
def test_T17_explicit_support_alignment_rejects_broken_or_unsafe_lineage(bundle, defect):
    annotations, session, review, selected = support_probe(bundle)
    alignment = review["source_claim_alignment"]
    expected = "SUPPORT_REVIEW_LINEAGE_INVALID"
    if defect == "missing-alignment":
        review.pop("source_claim_alignment")
    elif defect == "bad-hash":
        alignment["sources"][1]["claim_sha256"] = "0" * 64
    elif defect == "missing-annotation":
        alignment["sources"][1]["annotation_id"] = "not-an-original"
    elif defect == "one-side":
        alignment["sources"] = [alignment["sources"][0], {**alignment["sources"][0]}]
    elif defect == "duplicate-source":
        alignment["sources"].append(deepcopy(alignment["sources"][0]))
    elif defect == "extra-annotation":
        alignment["sources"].append(dict(annotation_id=annotations[0]["annotation_id"],
                                         claim_sha256=alignment["sources"][0]["claim_sha256"]))
    elif defect == "wrong-step":
        other = next(a for a in annotations if a["step_id"] == "D0")
        other["initial_label"]["claim_reviews"] = deepcopy(selected[1]["initial_label"]["claim_reviews"])
        review["prior_annotation_ids"][1] = other["annotation_id"]
        alignment["sources"][1]["annotation_id"] = other["annotation_id"]
    elif defect == "before-freeze":
        alignment["aligned_at"] = "2026-10-22T01:30:00Z"
    elif defect == "after-review":
        alignment["aligned_at"] = "2026-10-22T03:31:00Z"
    elif defect == "duplicate-claim":
        selected[1]["initial_label"]["claim_reviews"] *= 2
    elif defect == "changed-original-after-hash":
        selected[1]["initial_label"]["claim_reviews"][0]["limitations"].append("Changed after mapping")
    else:
        doc = "d02:test:1" if defect == "future-final" else (
            "d01:a:1" if defect == "other-family-final" else "d02:release:2")
        review["evidence_refs"] = [dict(doc_version_id=doc,
            paragraph_id="missing" if defect == "missing-paragraph" else "p1", direction="supports")]
        expected = {"future-final": "FUTURE_VERSION", "other-family-final": "CROSS_FAMILY_SPLIT",
                    "missing-paragraph": "CITATION_NOT_FOUND"}[defect]
    path = persist(bundle, annotations, session, review)
    audit = audit_annotations(path, manifest_sha256=sha256_bytes(path.read_bytes()))
    assert audit["human_gate"] == "FAIL"
    assert expected in {e["code"] for e in audit["errors"]}
    assert audit["support_review_count"] == 0
    assert audit["semantic_support"]["value"] is None
    assert not audit["eligible_gold_keys"]


def test_source_claim_hashes_do_not_depend_on_list_position(bundle):
    annotations, session, review, selected = support_probe(bundle)
    for annotation in selected:
        extra = deepcopy(annotation["initial_label"]["claim_reviews"][0])
        extra["claim_text"] = "A separate unrelated claim kept in the original record."
        annotation["initial_label"]["claim_reviews"].insert(0, extra)
    path = persist(bundle, annotations, session, review)
    audit = audit_annotations(path, manifest_sha256=sha256_bytes(path.read_bytes()))
    assert not audit["errors"]
    assert audit["support_review_count"] == 1
    assert audit["human_gate"] == "PASS"


@pytest.mark.parametrize("defect", ["blank-reason", "blank-person", "naive-time", "missing-time",
                                  "invalid-hash", "one-source"])
def test_support_alignment_schema_requires_specific_sources_and_human_record(defect):
    from pydantic import ValidationError

    alignment = dict(sources=[dict(annotation_id="contract-A", claim_sha256="a"*64),
                              dict(annotation_id="contract-B", claim_sha256="b"*64)],
                     reason="Explicit test-only correspondence", aligned_by="contract-reviewer",
                     aligned_at="2026-10-22T03:00:00Z")
    if defect == "blank-reason":
        alignment["reason"] = " "
    elif defect == "blank-person":
        alignment["aligned_by"] = " "
    elif defect == "naive-time":
        alignment["aligned_at"] = "2026-10-22T03:00:00"
    elif defect == "missing-time":
        alignment.pop("aligned_at")
    elif defect == "invalid-hash":
        alignment["sources"][0]["claim_sha256"] = "not-a-sha"
    else:
        alignment["sources"] = alignment["sources"][:1]
    payload = dict(support_review_id="contract-schema-only", timeline_id="DEV-01", step_id="D0",
        persona_version_id="contract-persona", annotation_version="g1a-annotation-v1",
        prior_annotation_ids=["contract-A", "contract-B"], claim_text="Synthetic schema probe",
        evidence_refs=[dict(doc_version_id="d01:a:1", paragraph_id="p1", direction="mentions")],
        scope="Synthetic schema check only", semantic_support="uncertain", reason="Not human evidence",
        reviewed_by="contract-reviewer", reviewed_at="2026-10-22T03:30:00Z",
        source_claim_alignment=alignment)
    with pytest.raises(ValidationError):
        SupportReview.model_validate_json(canonical_json(payload))
