"""All submissions here are temporary fabricated contract probes, never human evidence."""

import json

import pytest
from conftest import SOURCE, refresh

from evals.intelligence_v1.contracts import (
    CoverageWindow,
    DocumentVersion,
    PersonaVersion,
    ReplayStep,
)
from evals.intelligence_v1.hashing import canonical_json, sha256_bytes
from evals.intelligence_v1.pilot import annotation_packet
from evals.intelligence_v1.validate import validate_dataset


def records(root, path, model=None):
    return [model.model_validate_json(line) if model else json.loads(line)
            for line in (root / path).read_bytes().splitlines()]


def save(root, path, values):
    (root / path).write_bytes("".join(canonical_json(v) + "\n" for v in values).encode())


def probe(root, annotator="contract-probe-a", step_index=0):
    step = records(root, "timelines/steps.jsonl", ReplayStep)[step_index]
    packet = annotation_packet(records(root, "versions/documents.jsonl", DocumentVersion),
        records(root, "personas/personas.jsonl", PersonaVersion),
        records(root, "timelines/coverage_windows.jsonl", CoverageWindow), step=step)
    return dict(annotation_id=annotator, timeline_id=step.timeline_id, step_id=step.step_id,
        persona_version_id=step.persona_version_id, annotation_version="synthetic-fixture-v1",
        annotator_id=annotator, submitted_at="2026-10-20T00:00:00Z", guide_revision="dev01-guide-v1",
        packet_sha256=sha256_bytes(packet), initial_label=dict(local_event_id="local-probe",
        document_version_ids=["d01:a:1"], relevance=0, potential_value=0, novelty_to_persona=0,
        evidence_quality=0, graded_relevance=0, material_change="insufficient", tier="hold",
        rationale="Temporary schema probe, not a human judgment.", uncertainty=["Not human evidence"],
        document_relations=[], claim_reviews=[]))


def test_contract_probe_is_valid_but_never_confirms_human_independence(bundle):
    save(bundle, "labels/annotations.jsonl", [probe(bundle)])
    report = validate_dataset(refresh(bundle))
    assert report.counts["annotations"] == 1
    assert "independent_annotation" in report.pending and "claim_semantic_support" in report.pending
    assert (SOURCE / "labels/annotations.jsonl").read_bytes() == b""


@pytest.mark.parametrize("changes,code", [
    ({"packet_sha256": "0" * 64}, "SHA_MISMATCH"),
    ({"guide_revision": "missing-guide"}, "UNSUPPORTED_REVISION"),
    ({"persona_version_id": "dev01:developer:2"}, "REFERENCE_NOT_FOUND"),
    ({"submitted_at": "2025-01-01T00:00:00Z"}, "INVALID_INTERVAL"),
])
def test_annotation_context_is_pinned(bundle, changes, code):
    row = probe(bundle)
    row.update(changes)
    save(bundle, "labels/annotations.jsonl", [row])
    report = validate_dataset(refresh(bundle), strict=False)
    assert code in {e.code for e in report.errors}


@pytest.mark.parametrize("case,code", [
    ("future-document", "FUTURE_EVIDENCE"),
    ("missing-paragraph", "CITATION_NOT_FOUND"),
    ("future-relation", "FUTURE_EVIDENCE"),
    ("relation-origin", "ORIGIN_MISMATCH"),
])
def test_annotation_payload_is_time_and_reference_checked(bundle, case, code):
    row = probe(bundle)
    label = row["initial_label"]
    if case == "future-document":
        label["document_version_ids"] = ["d01:a:2"]
    elif case == "missing-paragraph":
        label["claim_reviews"] = [dict(claim_text="Schema probe", scope="Local probe",
            limitations=[], semantic_support="unsupported", evidence_refs=[dict(
                doc_version_id="d01:a:1", paragraph_id="p999", direction="unknown")])]
    else:
        row = probe(bundle, step_index=1)
        relation = records(bundle, "events/event_relations.jsonl")[0]
        if case == "future-relation":
            relation["evidence_at"] = "2026-02-01T00:00:00Z"
        else:
            relation.update(record_origin="real", provenance_uri="https://example.org/a")
        row["initial_label"]["document_relations"] = [relation]
    save(bundle, "labels/annotations.jsonl", [row])
    report = validate_dataset(refresh(bundle), strict=False)
    assert code in {e.code for e in report.errors}


def test_adjudication_cannot_invent_prior_submissions(bundle):
    step = records(bundle, "timelines/steps.jsonl")[0]
    label = dict(record_origin="synthetic", provenance_uri="DEV-01/README.md",
        timeline_id="DEV-01",step_id="D0",persona_version_id=step["persona_version_id"],
        event_id="d01:event:release",annotation_version="synthetic-fixture-v1",relevance=0,
        potential_value=0,novelty_to_persona=0,evidence_quality=0,graded_relevance=0,
        material_change="insufficient",tier="hold",supporting_doc_version_ids=["d01:a:1"],
        rationale="Temporary adversarial probe",uncertainty=[],adjudication_status="adjudicated")
    save(bundle, "labels/adjudications.jsonl", [dict(adjudication_id="probe",
        prior_annotation_ids=["missing-a", "missing-b"],final_label=label,reason="Probe",
        adjudicator_id="contract-probe",adjudicated_at="2026-10-20T00:00:00Z")])
    assert "REFERENCE_NOT_FOUND" in {e.code for e in validate_dataset(
        refresh(bundle), strict=False).errors}
