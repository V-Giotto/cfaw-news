"""PR2 sample contracts. Expected sets are authored independently of the selector."""

import json

import pytest
from conftest import SOURCE, refresh
from pydantic import ValidationError

from evals.intelligence_v1.contracts import (
    Claim,
    CoverageWindow,
    DocumentVersion,
    EvidenceRef,
    PersonaVersion,
    ReplayStep,
)
from evals.intelligence_v1.exceptions import ContractError
from evals.intelligence_v1.hashing import canonical_json, sha256_bytes
from evals.intelligence_v1.temporal import parse_instant, visible_versions
from evals.intelligence_v1.validate import validate_dataset

EXPECTED = {
    "D0": ["d01:a:1"],
    "D1": ["d01:a:1", "d01:b:1"],
    "D3": ["d01:a:1", "d01:b:1", "d01:c:1", "d01:d:1"],
    "D4": ["d01:a:1", "d01:b:1", "d01:c:1", "d01:d:1", "d01:e:1"],
    "D5": ["d01:a:2", "d01:b:1", "d01:c:1", "d01:d:1", "d01:e:1"],
    "D8": ["d01:a:2", "d01:b:1", "d01:c:1", "d01:d:1", "d01:e:1", "d01:f:1"],
}


def rows(relative, model=None, root=SOURCE):
    raw = (root / relative).read_bytes().splitlines()
    return [model.model_validate_json(x) if model else json.loads(x) for x in raw]


def write(root, relative, records):
    (root / relative).write_bytes("".join(canonical_json(x) + "\n" for x in records).encode())
    return refresh(root)


def test_DEV01_six_distinct_visible_sets_and_all_synthetic():
    docs = rows("versions/documents.jsonl", DocumentVersion)
    steps = rows("timelines/steps.jsonl", ReplayStep)
    assert len(docs) == 7 and len(steps) == 6
    assert all(d.record_origin == "synthetic" for d in docs)
    assert {s.timeline_id for s in steps} == {"DEV-01"}
    for step in steps:
        actual = [d.doc_version_id for d in visible_versions(docs, as_of=step.as_of)]
        assert actual == EXPECTED[step.step_id] == list(step.visible_doc_version_ids)
    assert len({tuple(x) for x in EXPECTED.values()}) == 6


def test_T04_repeat_observation_does_not_create_a_content_version():
    from evals.intelligence_v1.contracts import DocumentObservation

    docs = rows("versions/documents.jsonl", DocumentVersion)
    observations = rows("versions/observations.jsonl", DocumentObservation)
    repeated = [o for o in observations if o.doc_version_id == "d01:a:1"]
    assert len(repeated) == 2 and len({o.observed_at for o in repeated}) == 2
    assert len({o.content_sha256 for o in repeated}) == 1
    assert len([d for d in docs if d.document_id == "d01:a"]) == 2  # v1 and changed v2 only


def test_T05_T03_correction_is_append_only_and_old_paragraph_stays_exact():
    docs = rows("versions/documents.jsonl", DocumentVersion)
    old, new = [d for d in docs if d.document_id == "d01:a"]
    assert old.canonical_url == new.canonical_url
    assert new.supersedes_version_id == old.doc_version_id
    assert new.content_sha256 != old.content_sha256
    assert "Windows CPU" in old.paragraphs[1].text
    assert "not supported" in new.paragraphs[1].text
    before = old.model_dump_json()
    assert visible_versions(docs, as_of=parse_instant("2026-01-05T12:00:00Z"))[0] == old
    assert visible_versions(docs, as_of=new.available_at)[0] == new
    assert old.model_dump_json() == before


def test_T08_T09_claim_history_separates_attribution_and_scoped_measurement():
    from evals.intelligence_v1.pilot import visible_claim_states

    claims = rows("claims/claims.jsonl", Claim)
    early = visible_claim_states(claims, as_of=parse_instant("2026-01-04T12:00:00Z"))
    assert {c.verification_state for c in early} == {"source_attributed"}
    later = visible_claim_states(claims, as_of=parse_instant("2026-01-05T12:00:00Z"))
    measured = next(c for c in later if c.claim_type == "measured_result")
    assert measured.verification_state == "independently_supported"
    assert all(x in measured.scope for x in ("Linux", "GPU", "v1.0", "TinyBench-3"))
    assert {r.paragraph_id for r in measured.evidence_refs} >= {"p1", "p2"}
    assert measured.limitations and "Windows" in " ".join(measured.limitations)
    broad = next(c for c in later if c.claim_id == "d01:claim:performance")
    assert broad.verification_state == "source_attributed"
    corrected = visible_claim_states(claims, as_of=parse_instant("2026-01-06T12:00:00Z"))
    assert next(c for c in corrected if c.claim_id == "d01:claim:platform").verification_state == "disputed"
    assert next(c for c in early if c.claim_id == "d01:claim:platform").verification_state == "source_attributed"


def test_relations_distinguish_upstream_independent_and_distinct_events():
    from evals.intelligence_v1.contracts import EventRelation

    relations = rows("events/event_relations.jsonl", EventRelation)
    assert len([r for r in relations if r.relation == "syndicated"]) == 3
    assert {"same_event_different_evidence", "related_distinct_event"} <= {
        r.relation for r in relations
    }
    docs = {d.doc_version_id: d for d in rows("versions/documents.jsonl", DocumentVersion)}
    for r in relations:
        assert max(docs[r.left_doc_version_id].available_at,
                   docs[r.right_doc_version_id].available_at) <= r.evidence_at


@pytest.mark.parametrize("field,value,code", [
    ("observed_at", "2025-01-01T00:00:00Z", "FUTURE_EVIDENCE"),
    ("content_sha256", "0" * 64, "SHA_MISMATCH"),
    ("doc_version_id", "missing", "REFERENCE_NOT_FOUND"),
])
def test_observation_chain_is_checked(bundle, field, value, code):
    relative = "versions/observations.jsonl"
    records = rows(relative, root=bundle)
    records[0][field] = value
    report = validate_dataset(write(bundle, relative, records), strict=False)
    assert code in {x.code for x in report.errors}


@pytest.mark.parametrize("changes,code", [
    ({"evidence_at": "2026-01-01T00:00:00Z"}, "FUTURE_EVIDENCE"),
    ({"right_doc_version_id": "missing"}, "REFERENCE_NOT_FOUND"),
    ({"record_origin": "real", "provenance_uri": "https://example.org/a"}, "ORIGIN_MISMATCH"),
])
def test_relation_reference_time_and_origin_guards(bundle, changes, code):
    relative = "events/event_relations.jsonl"
    records = rows(relative, root=bundle)
    records[0].update(changes)
    report = validate_dataset(write(bundle, relative, records), strict=False)
    assert code in {x.code for x in report.errors}


def test_T16_missing_paragraph_is_rejected_and_T17_location_is_not_support():
    from evals.intelligence_v1.pilot import citation_status

    docs = rows("versions/documents.jsonl", DocumentVersion)
    cutoff = parse_instant("2026-01-01T12:00:00Z")
    good = EvidenceRef(doc_version_id="d01:a:1", paragraph_id="p1", direction="supports")
    report = citation_status(docs, good, as_of=cutoff)
    assert report == {"location": "valid", "semantic_support": "not_measured"}
    task = json.loads((SOURCE / "DEV-01/semantic_probe.json").read_bytes())
    assert task["statement"] == "Cedar Agent improves performance by one million times."
    assert task["expected_semantic_support"] == "unsupported"
    assert task["origin"] == "synthetic_test_expectation"
    # This authored negative expectation is not a submitted human semantic assessment.
    with pytest.raises(ContractError, match="CITATION_NOT_FOUND"):
        citation_status(docs, good.model_copy(update={"paragraph_id": "p999"}), as_of=cutoff)
    with pytest.raises(ContractError, match="FUTURE_VERSION"):
        citation_status(docs, good.model_copy(update={"doc_version_id": "d01:a:2"}), as_of=cutoff)


def test_T19_persona_changes_only_context_not_the_visible_technical_evidence():
    from evals.intelligence_v1.pilot import annotation_packet

    docs = rows("versions/documents.jsonl", DocumentVersion)
    personas = rows("personas/personas.jsonl", PersonaVersion)
    step = rows("timelines/steps.jsonl", ReplayStep)[3]
    coverage = rows("timelines/coverage_windows.jsonl", CoverageWindow)
    packet = json.loads(annotation_packet(docs, personas, coverage, step=step))
    alternate = personas[0].model_copy(update={"hard_constraints": ("Windows CPU only",)})
    other = json.loads(annotation_packet(docs, [alternate], coverage, step=step))
    assert packet["documents"] == other["documents"]
    assert packet["persona"]["hard_constraints"] != other["persona"]["hard_constraints"]
    assert all("tier" not in p for p in (packet, other))


def test_T21_gap_is_explicit_and_does_not_mean_no_world_change():
    from evals.intelligence_v1.pilot import annotation_packet

    docs = rows("versions/documents.jsonl", DocumentVersion)
    personas = rows("personas/personas.jsonl", PersonaVersion)
    coverage = rows("timelines/coverage_windows.jsonl", CoverageWindow)
    step = rows("timelines/steps.jsonl", ReplayStep)[2]
    packet = json.loads(annotation_packet(docs, personas, coverage, step=step))
    assert any(c["status"] == "service_offline" for c in packet["coverage"])
    assert packet["coverage_interpretation"] == "observed_sources_only; gaps_are_unknown"
    assert "no_updates" not in packet and "knowledge_known" not in packet


def test_packet_never_accesses_future_text_or_leaks_reference_fields():
    from evals.intelligence_v1.pilot import annotation_packet

    docs = rows("versions/documents.jsonl", DocumentVersion)
    step = rows("timelines/steps.jsonl", ReplayStep)[0]
    personas = rows("personas/personas.jsonl", PersonaVersion)

    class Guard:
        def __init__(self, row):
            self.row = row

        def __getattr__(self, key):
            if key in {"title", "text_excerpt", "paragraphs", "model_dump_json"}:
                pytest.fail("future text was accessed")
            return getattr(self.row, key)

    guarded = [d if d.available_at <= step.as_of else Guard(d) for d in docs]
    raw = annotation_packet(guarded, personas, [], step=step)
    assert raw == annotation_packet(docs[::-1], personas[::-1], [], step=step)
    packet = json.loads(raw)
    assert [d["doc_version_id"] for d in packet["documents"]] == EXPECTED["D0"]
    for forbidden in ("family_id", "family_scope_ids", "event_id", "verification_state",
                      "gold", "rationale", "CORRECTION", "TinyBench-3"):
        assert forbidden not in raw.decode()
    assert len(sha256_bytes(raw)) == 64


def test_DEV01_human_records_are_empty_and_not_counted_as_double_annotation():
    for name in ("annotations", "adjudications", "gold"):
        assert (SOURCE / f"labels/{name}.jsonl").read_bytes() == b""
    status = json.loads((SOURCE / "DEV-01/pilot_status.json").read_bytes())
    assert status["human_annotation_status"] == "not_started"
    assert status["confirmed_human_annotators"] == []
    assert status["semantic_support_measurement"] == "not_measured"
    assert not status["g1a_passed"]


def test_new_reference_contracts_are_strict_without_manufacturing_human_records():
    from evals.intelligence_v1.contracts import Annotation, DocumentObservation, EventRelation

    for model in (Annotation, DocumentObservation, EventRelation):
        with pytest.raises(ValidationError):
            model.model_validate_json('{"unknown":true}')


def test_scoped_claim_state_filter_does_not_read_future_claim_payload():
    from evals.intelligence_v1.pilot import visible_claim_states

    cutoff = parse_instant("2026-01-01T12:00:00Z")

    class Future:
        valid_as_of = parse_instant("2026-01-06T12:00:00Z")

        def __getattr__(self, key):
            pytest.fail("future claim payload was accessed")

    assert visible_claim_states([Future()], as_of=cutoff) == []


def test_T17_validator_keeps_semantics_pending_for_located_false_statement(bundle):
    relative = "claims/claims.jsonl"
    records = rows(relative, root=bundle)
    records[0]["claim_text"] = "Cedar Agent improves performance by one million times."
    report = validate_dataset(write(bundle, relative, records))
    assert report.ok and "claim_semantic_support" in report.pending
