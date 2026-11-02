"""Authored nonblind contract material, never a production source or claim of live news."""

from copy import deepcopy

from evals.intelligence_g2.contracts import json_bytes
from evals.intelligence_g4.contracts import RuntimeInput, parse
from evals.intelligence_v1.contracts import Paragraph
from evals.intelligence_v1.hashing import content_sha256, sha256_bytes

OLD = "2026-01-01T12:00:00Z"
NOW = "2026-01-02T12:00:00Z"
LATER = "2026-01-03T12:00:00Z"


def case(*, body="Atlas Tool v1.0 releases local agent tooling.", origin="synthetic"):
    """Real-origin cases are invented metadata-only HTTPS examples, never fetched news."""
    synthetic = origin == "synthetic"
    paragraphs = [dict(paragraph_id="p1", text=body)] if body else []
    title = "Atlas Tool v1.0 release"
    sha = content_sha256(title, None, tuple(Paragraph(**p) for p in paragraphs))
    rights = "synthetic" if synthetic else "unknown"
    provenance = "synthetic://g4-pr1/authoring" if synthetic else "https://example.com/"
    return dict(record_origin=origin, provenance_uri=provenance, timeline_id="g4-pr1-probe",
        config=dict(budget=dict(profile="focus70-radar30-v1")), sources=[dict(policy=dict(
            source_id="official", source_type="official", record_origin=origin,
            redistribution_rights=rights, allowed_use=["fulltext"] if synthetic else ["metadata"],
            max_excerpt_chars=1024), policy_provenance_uri=provenance)], steps=[dict(
            step_id="S0", as_of=NOW, time_window_start=OLD, time_window_end=NOW,
            persona=dict(persona=dict(persona_id="local", persona_version_id="local:v1",
                available_at=OLD, persona_origin="constructed" if synthetic else "consented_real",
                domain_interests=["agent tooling"], current_goals=[], hard_constraints=[],
                knowledge_known=[], attention_budget_seconds=420, exploration_preference="off",
                locale="en"), record_origin=origin, provenance_uri=provenance),
            documents=[dict(record_origin=origin, redistribution_rights=rights,
                provenance_uri="evals/intelligence_g4/tests/support.py" if synthetic else provenance,
                candidate=dict(doc_version_id="atlas:v1",
                    document_id="atlas", canonical_url="synthetic://atlas/v1" if synthetic else
                    "https://example.com/atlas", source_id="official", source_type="official",
                    content_kind="synthetic_text" if synthetic else "feed_summary", title=title,
                    language="en", text_excerpt=None, paragraphs=paragraphs, content_sha256=sha,
                    published_at=OLD, observed_at=NOW, available_at=NOW, upstream_document_id=None),
                visible_lineage=[dict(doc_version_id="atlas:v1", document_id="atlas",
                    available_at=NOW, supersedes_version_id=None, content_sha256=sha)])],
            source_coverage=[dict(coverage_window_id="official:S0", source_id="official",
                start_at=OLD, end_at=NOW, observed_at=NOW, status="unknown",
                reason="Authored test observation; no continuous or live coverage claimed.")])])


def wire(value):
    # Preparation owns these pins. The slice never derives a replacement trusted pin.
    raw = json_bytes(parse(RuntimeInput, value))
    return raw, sha256_bytes(raw)


def repeat(value):
    value = deepcopy(value)
    step = deepcopy(value["steps"][0])
    step.update(step_id="S1", as_of=LATER, time_window_end=LATER)
    step["source_coverage"][0].update(coverage_window_id="official:S1", end_at=LATER,
                                       observed_at=LATER)
    value["steps"].append(step)
    return value
