"""Temporal preflight and independent structural/field checks, then deterministic contract checks."""

from evals.intelligence_g2.pr2.validate_output import (
    checked_grouping_input,
    get,
    instant,
)
from evals.intelligence_g2.pr2.validate_output import (
    validate_output as validate_grouping_output,
)
from evals.intelligence_g2.validate_output import preflight_time
from evals.intelligence_v1.hashing import sha256_bytes

from .contracts import EvidenceInput, EvidenceResult, PR3Config, digest, fail, parse
from .extract import citation_key
from .history import namespace
from .scope import parse_fields


def unique(rows, field, stage="output"):
    output = {}
    for row in rows:
        key = getattr(row, field)
        if key in output:
            fail("DUPLICATE_ID", stage, field, key)
        output[key] = row
    return output


def preflight(value):
    grouping = get(value, "grouping_input")
    replay = get(grouping, "replay_input")
    preflight_time(replay)
    cutoff = get(get(replay, "context"), "as_of")
    if cutoff is None:
        return
    cutoff = instant(cutoff)
    prior = get(value, "previous_state")
    for state in (prior,):
        if state is None:
            continue
        bound = get(get(state, "cursor"), "as_of")
        if bound is not None and instant(bound) >= cutoff:
            fail("G2_PR3_HISTORY_FUTURE", "history", "previous_state.cursor")
        bound = instant(bound) if bound is not None else cutoff
        for collection, field in (("claims", "first_extracted_as_of"), ("citations", "available_at"),
                ("transitions", "effective_at"), ("memberships", "effective_at"), ("assessments", "as_of")):
            for row in get(state, collection, ()):
                time = get(row, field)
                if time is not None and instant(time) > bound:
                    fail("G2_PR3_HISTORY_FUTURE", "history", collection + "." + field)


def checked_input(evidence_input, config):
    preflight(evidence_input)
    value = parse(EvidenceInput, evidence_input)
    config = parse(PR3Config, config)
    grouping, _ = checked_grouping_input(value.grouping_input, value.grouping_config)
    if value.config_sha256 != digest(config):
        fail("CONFIG_NOT_PINNED", "input", "config_sha256")
    replay = grouping.replay_input
    docs = replay.visible_documents
    for count, limit, field in ((len(docs), config.max_documents, "documents"),
            (sum(len(d.candidate.paragraphs) for d in docs), config.max_paragraphs, "paragraphs"),
            (sum(len(p.text) for d in docs for p in d.candidate.paragraphs), config.max_visible_chars, "visible_chars")):
        if count > limit:
            fail("G2_PR3_BUDGET_EXCEEDED", "input", field)
    validate_grouping_output(value.grouping_result, grouping, value.grouping_config)
    prior = value.previous_state
    cursor = grouping.cursor
    if prior is None:
        if cursor.ordinal != 0 or value.previous_state_sha256 is not None:
            fail("G2_PR3_STATE_CHAIN_INVALID", "history", "previous_state")
    else:
        if (value.previous_state_sha256 != digest(prior) or prior.config_sha256 != digest(config)
                or prior.namespace != namespace(value, config)
                or cursor.ordinal != prior.cursor.ordinal + 1
                or cursor.previous_step_id != prior.cursor.step_id
                or prior.grouping_state_sha256 != digest(grouping.previous_state)):
            fail("G2_PR3_STATE_CHAIN_INVALID", "history", "previous_state")
        claims = unique(prior.claims, "claim_key", "history")
        refs = unique(prior.citations, "ref_id", "history")
        for ref in refs.values():
            check_ref_bytes(ref)
        for claim in claims.values():
            check_claim_fields(claim, refs)
        for row in prior.memberships:
            if row.claim_key not in claims:
                fail("G2_PR3_STATE_CHAIN_INVALID", "history", "memberships.claim_key", row.claim_key)
        for row in prior.transitions:
            if not set(row.from_claim_keys + row.to_claim_keys) <= set(claims):
                fail("G2_PR3_STATE_CHAIN_INVALID", "history", "transitions.claim_keys")
    return value.model_copy(update={"grouping_input": grouping}), config


def check_ref_bytes(ref):
    if (ref.start != 0 or ref.end != len(ref.quote) or ref.quote_sha256 != sha256_bytes(ref.quote.encode())
            or ref.ref_id != citation_key(ref)):
        fail("G2_PR3_SPAN_MISMATCH", "evidence", "quote", ref.ref_id)


def check_citation(ref, replay, event):
    documents = {d.candidate.doc_version_id: d.candidate for d in replay.visible_documents}
    if ref.doc_version_id not in documents:
        fail("CITATION_NOT_FOUND", "evidence", "doc_version_id", ref.doc_version_id)
    if ref.doc_version_id not in event.member_doc_version_ids:
        fail("G2_PR3_EVIDENCE_NOT_IN_EVENT", "evidence", "doc_version_id", ref.doc_version_id)
    doc = documents[ref.doc_version_id]
    paragraphs = {p.paragraph_id: p.text for p in doc.paragraphs}
    if ref.paragraph_id not in paragraphs:
        fail("CITATION_NOT_FOUND", "evidence", "paragraph_id", ref.doc_version_id)
    check_ref_bytes(ref)
    if (paragraphs[ref.paragraph_id][ref.start:ref.end] != ref.quote
            or ref.end != len(paragraphs[ref.paragraph_id]) or ref.source_id != doc.source_id
            or ref.document_id != doc.document_id or ref.available_at != doc.available_at
            or ref.content_sha256 != doc.content_sha256):
        fail("G2_PR3_SPAN_MISMATCH", "evidence", "quote", ref.ref_id)


def check_claim_fields(claim, refs):
    if len(claim.evidence_ref_ids) != 1 or claim.evidence_ref_ids[0] not in refs:
        fail("CITATION_NOT_FOUND", "evidence", "evidence_ref_ids", claim.claim_key)
    ref = refs[claim.evidence_ref_ids[0]]
    if claim.statement != ref.quote or claim.doc_version_id != ref.doc_version_id:
        fail("G2_PR3_SPAN_MISMATCH", "evidence", "statement", claim.claim_key)
    scope, prop, marker = parse_fields(ref)
    if claim.attribution.attribution_kind == "secondary_material":
        prop = prop.model_copy(update={"quantities": (), "polarity": "unknown", "ambiguous": True})
        marker = "none"
    if claim.scope != scope or claim.proposition != prop or claim.marker != marker:
        fail("G2_PR3_FIELD_PROVENANCE_INVALID", "scope", "grounded_fields", claim.claim_key)


def validate_output(result, evidence_input, config):
    value, config = checked_input(evidence_input, config)
    result = parse(EvidenceResult, result, stage="output")
    replay = value.grouping_input.replay_input
    events = {e.event_key: e for e in value.grouping_result.events}
    refs = unique(result.citations, "ref_id")
    claims = unique(result.claims, "claim_key")
    owners = {k: b.event_key for b in result.bundles for k in b.current_claim_keys}
    for assessment in result.assessments:
        if assessment.verification_state == "independently_supported":
            fail("G2_PR3_STATUS_INVALID", "output", "verification_state", assessment.claim_key)
    for claim in claims.values():
        check_claim_fields(claim, refs)
        event = events.get(owners.get(claim.claim_key))
        if event is None:
            fail("G2_PR3_EVIDENCE_NOT_IN_EVENT", "evidence", "claim_key", claim.claim_key)
        check_citation(refs[claim.evidence_ref_ids[0]], replay, event)
    for link in result.links:
        if link.target_claim_key not in claims or link.evidence_claim_key not in claims:
            fail("G2_PR3_HISTORICAL_REF_AS_CURRENT", "evidence", "link.claim_key", link.link_key)
        if (owners[link.target_claim_key] != owners[link.evidence_claim_key]
                or link.ref_id not in claims[link.evidence_claim_key].evidence_ref_ids):
            fail("G2_PR3_EVIDENCE_NOT_IN_EVENT", "evidence", "link.ref_id", link.link_key)
    from .pipeline import assemble
    expected = assemble(value, config)
    for field, code, stage in (("links", "G2_PR3_UNSUPPORTED_DIRECTION", "relations"),
            ("lineage", "G2_PR3_LINEAGE_INVALID", "lineage"),
            ("claims", "G2_PR3_FIELD_PROVENANCE_INVALID", "extract"),
            ("assessments", "G2_PR3_STATUS_INVALID", "output"),
            ("transitions", "G2_PR3_STATE_CHAIN_INVALID", "history"),
            ("next_state", "G2_PR3_STATE_CHAIN_INVALID", "history")):
        if getattr(result, field) != getattr(expected, field):
            fail(code, stage, field)
    if result != expected:
        fail("G2_PR3_STATUS_INVALID", "output", "result")
    return result
