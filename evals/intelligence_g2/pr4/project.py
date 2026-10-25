"""Whitelisted evidence projection. Persona and candidate bodies stop here."""

from evals.intelligence_g2.pr3.contracts import PR3Config
from evals.intelligence_g2.pr3.validate_output import validate_output as validate_evidence

from .contracts import EventEvidenceView, GenerationInput, SourcePointer, digest, fail


def source_metadata(replay):
    policies = {p.source_id: p for p in replay.sources}
    return tuple(SourcePointer(doc_version_id=d.candidate.doc_version_id,
        document_id=d.candidate.document_id, source_id=d.candidate.source_id,
        canonical_url=d.candidate.canonical_url, available_at=d.candidate.available_at,
        content_sha256=d.candidate.content_sha256, content_kind=d.candidate.content_kind,
        record_origin=d.record_origin, redistribution_rights=d.redistribution_rights,
        provenance_uri=d.provenance_uri, policy=policies[d.candidate.source_id])
        for d in replay.visible_documents)


def project_step(evidence_input, evidence_result, *, previous_state, config, evidence_config=None):
    """Validate the parent, then retain only event-authorized evidence and metadata."""
    validate_evidence(evidence_result, evidence_input, evidence_config or PR3Config())
    replay = evidence_input.grouping_input.replay_input
    metadata = {p.doc_version_id: p for p in previous_state.source_metadata} if previous_state else {}
    for pointer in source_metadata(replay):
        if pointer.doc_version_id in metadata and metadata[pointer.doc_version_id] != pointer:
            fail("G2_PR4_PARENT_RUN_MISMATCH", "input", "immutable_source_metadata", pointer.doc_version_id)
        metadata[pointer.doc_version_id] = pointer
    claims = {c.claim_key: c for c in evidence_result.next_state.claims}
    refs = {r.ref_id: r for r in evidence_result.next_state.citations}
    events = {e.event_key: e for e in evidence_input.grouping_result.events}
    views = []
    for bundle in sorted(evidence_result.bundles, key=lambda b: b.event_key):
        keys = set(bundle.current_claim_keys + bundle.historical_claim_keys)
        chosen = tuple(claims[k] for k in sorted(keys))
        selected_refs = tuple(refs[k] for k in sorted({r for c in chosen for r in c.evidence_ref_ids}))
        ids = set(bundle.current_doc_version_ids) | {r.doc_version_id for r in selected_refs}
        if not ids <= set(metadata):
            fail("G2_PR4_PARENT_RUN_MISMATCH", "input", "historical_source_metadata", bundle.event_key)
        transitions = tuple(t for t in evidence_result.next_state.transitions
            if set(t.from_claim_keys + t.to_claim_keys) <= keys
            and (set(t.to_claim_keys) & set(bundle.current_claim_keys)))
        views.append(EventEvidenceView(bundle=bundle, claims=chosen, citations=selected_refs,
            transitions=transitions, source_pointers=tuple(metadata[k] for k in sorted(ids)),
            lineage_ids=events[bundle.event_key].lineage_ids,
            predecessor_event_keys=tuple(sorted({k for t in evidence_input.grouping_result.next_state.transitions
                if bundle.event_key in t.to_keys for k in t.from_keys if k != bundle.event_key}))))
    return GenerationInput(namespace=digest(dict(parent_namespace=evidence_result.next_state.namespace,
        generator_revision=config.generator_revision)), cursor=evidence_result.cursor, events=tuple(views),
        source_coverage=replay.context.source_coverage, coverage_gaps=evidence_result.validation.coverage_gaps,
        previous_state=previous_state, previous_state_sha256=digest(previous_state) if previous_state else None,
        config_sha256=digest(config))
