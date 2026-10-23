"""PR2 pure sample helpers, not a loader, replay engine, ranker or semantic judge.

Use only provenance-validated records. Full-dataset integrity validation is trusted
preparation; annotation packets must never receive reference events/claims/gold.
"""

from .exceptions import ContractError
from .hashing import canonical_json
from .temporal import (
    format_instant,
    project_candidate,
    require_visible_version,
    utc_instant,
    visible_persona,
    visible_versions,
)


def visible_claim_states(records, *, as_of):
    """Evaluation/annotation-admin only. Never pass these reference states to prediction."""
    cutoff = utc_instant(as_of)
    selected = {}
    seen = set()
    for row in records:
        if row.valid_as_of > cutoff:
            continue  # Do not inspect a future claim's text, state, references or ID.
        key = (row.claim_id, row.valid_as_of)
        if key in seen:
            raise ContractError("DUPLICATE_ID", record_id=row.claim_id)
        seen.add(key)
        if row.claim_id not in selected or selected[row.claim_id].valid_as_of < row.valid_as_of:
            selected[row.claim_id] = row
    return [selected[key] for key in sorted(selected)]


def citation_status(documents, reference, *, as_of):
    """Locate the cited historical paragraph; semantic support is deliberately unmeasured."""
    found = [d for d in documents if d.doc_version_id == reference.doc_version_id]
    if len(found) != 1:
        raise ContractError("CITATION_NOT_FOUND", record_id=reference.doc_version_id)
    version = require_visible_version(found[0], as_of=as_of)
    if reference.paragraph_id is not None and reference.paragraph_id not in {
        p.paragraph_id for p in version.paragraphs
    }:
        raise ContractError("CITATION_NOT_FOUND", record_id=reference.doc_version_id)
    return {"location": "valid", "semantic_support": "not_measured"}


def annotation_packet(documents, personas, coverage, *, step):
    """Return deterministic UTF-8/LF bytes for ONE step, without reference answers.

Metadata selection happens before reading document payload. This helper does not
open files, export future packets, authorize distribution or certify human review.
"""
    cutoff = utc_instant(step.as_of)
    scoped = [d for d in documents if d.family_id in step.family_scope_ids]
    visible = visible_versions(scoped, as_of=cutoff)
    if tuple(d.doc_version_id for d in visible) != step.visible_doc_version_ids:
        raise ContractError("VISIBLE_SET_MISMATCH")
    selected = [p for p in personas if p.persona_version_id == step.persona_version_id]
    if len(selected) != 1:
        raise ContractError("REFERENCE_NOT_FOUND", field="persona_version_id")
    persona = visible_persona(personas, persona_id=selected[0].persona_id, as_of=cutoff)
    if persona.persona_version_id != step.persona_version_id:
        raise ContractError("VERSION_CONFLICT", field="persona_version_id")
    windows = {c.coverage_window_id: c for c in coverage}
    included = []
    for key in step.coverage_window_ids:
        if key not in windows:
            raise ContractError("REFERENCE_NOT_FOUND", field="coverage_window_ids")
        window = windows[key]
        if window.observed_at > cutoff or window.end_at > cutoff:
            raise ContractError("FUTURE_COVERAGE", record_id=key)
        included.append(window.model_dump(mode="json"))
    payload = {
        "packet_revision": "dev01-packet-v1",
        "timeline_id": step.timeline_id,
        "step_id": step.step_id,
        "as_of": format_instant(cutoff),
        "persona": persona.model_dump(mode="json"),
        "attention_budget_seconds": step.attention_budget_seconds,
        "documents": [project_candidate(d, as_of=cutoff).model_dump(mode="json") for d in visible],
        "coverage": sorted(included, key=lambda c: c["coverage_window_id"]),
        "coverage_interpretation": "observed_sources_only; gaps_are_unknown",
    }
    return (canonical_json(payload) + "\n").encode("utf-8")


def annotation_packet_v2(context, candidates):
    """A single projected historical context, without any reference labels or events."""
    if tuple(d.doc_version_id for d in candidates) != context.candidate_doc_version_ids:
        raise ContractError("VISIBLE_SET_MISMATCH")
    for document in candidates:
        require_visible_version(document, as_of=context.as_of)
    payload = {"packet_revision": "g1a-packet-v2", "context": context.model_dump(mode="json"),
               "documents": [d.model_dump(mode="json") for d in candidates],
               "coverage_interpretation": "observed_sources_only; gaps_are_unknown",
               "history_interpretation": "inclusion_or_opening_does_not_establish_comprehension"}
    return (canonical_json(payload) + "\n").encode("utf-8")
