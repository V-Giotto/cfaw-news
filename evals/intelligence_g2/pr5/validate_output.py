"""Locator, minimum numeric guard, closed rendering and semantic truth remain separate."""

import re

from pydantic import ValidationError

from evals.intelligence_g2.contracts import json_bytes
from evals.intelligence_g2.pr2.validate_output import instant
from evals.intelligence_g2.pr4.policy import radar_sentences, visible_text
from evals.intelligence_g2.pr4.sensitive import sensitive_content

from .assets import strict_json
from .contracts import DRAFT_ADAPTER, ClosedDraft, SafeDraft, fail
from .styles import refs_for, render

# Keep complete version/date/quantity surfaces, and explicitly distinguish tested units/qualifiers.
NUMBER = re.compile(r"\d+(?:[.\-/]\d+)*(?:\s*(?:%|percentage points?|percent(?:age)?|倍|百分点))?", re.I)
QUALIFIER = re.compile(r"\b(?:up to|at most|at least|average|approximately|not|no)\b|最高|平均|至少|未|不", re.I)


def numeric_surface(text):
    return tuple(NUMBER.findall(text)), tuple(QUALIFIER.findall(text))


def validate_draft(completion, request, base, assets):
    raw = strict_json(completion.content)
    # Reject secrets before retaining any candidate text, including JSON values not in the schema.
    if sensitive_content(raw):
        fail("SENSITIVE_OUTPUT", "expression", "draft")
    if isinstance(raw, dict):
        for ref in raw.get("refs", ()) if isinstance(raw.get("refs", ()), (list, tuple)) else ():
            if isinstance(ref, dict) and ref.get("available_at") and instant(ref["available_at"]) > request.as_of:
                fail("FUTURE_EVIDENCE", "temporal", "available_at")
    try:
        draft = DRAFT_ADAPTER.validate_json(json_bytes(raw))
    except ValidationError:
        fail("SCHEMA_INVALID", "expression", "draft")
    allowed = {r.ref_id: r for r in refs_for(request)}
    if len(draft.refs) != len({r.ref_id for r in draft.refs}):
        fail("CITATION_NOT_ALLOWED", "expression", "refs")
    for ref in draft.refs:
        expected = allowed.get(ref.ref_id)
        if expected is None or (ref.doc_version_id, ref.paragraph_id) != (expected.doc_version_id, expected.paragraph_id):
            fail("CITATION_NOT_ALLOWED", "expression", "refs")
        if ref != expected:
            fail("SPAN_MISMATCH", "expression", "refs")
    if set(allowed) != {r.ref_id for r in draft.refs}:
        fail("CITATION_NOT_ALLOWED", "expression", "refs")
    if not isinstance(draft, ClosedDraft):
        # Research/dev review can inspect a safe synthetic draft, but never publish it as fact.
        safe = None
        if base.record_origin == "synthetic":
            safe = SafeDraft(request_sha256=request.request_sha256, text=draft.text,
                             ref_ids=tuple(r.ref_id for r in draft.refs))
        return None, safe
    headline, body = render(request, draft.style_id, draft.claim_order, assets)
    combined = draft.headline + "\n" + draft.body
    expected = headline + "\n" + body
    if numeric_surface(combined) != numeric_surface(expected):
        fail("NUMERIC_SCOPE_MISMATCH", "expression", "numeric_scope")
    # These strings are forbidden only outside source quotes; exact reconstruction below is decisive.
    if combined != expected:
        if any(word in combined for word in ("独立实测证明", "independently_supported", "已独立证实")):
            fail("ATTRIBUTION_ESCALATION", "expression", "attribution")
        fail("EXPRESSION_NOT_CLOSED", "expression", "closed_render")
    candidate = base.model_copy(update={
        "headline": base.headline.model_copy(update={"text": headline}),
        "what_happened": base.what_happened.model_copy(update={"text": body})})
    if (len(visible_text(candidate)) > request.max_visible_chars
            or base.tier_candidate == "radar" and radar_sentences(candidate) > 2):
        fail("BUDGET_EXCEEDED", "expression", "visible_chars")
    return draft, None


def validate_output(result, value, config, assets, traces):
    from .contracts import ExpressionResult, data, digest, parse
    from .pipeline import identify, observe, rule_presentation
    from .project import checked_input, namespace, project_request

    value, config = checked_input(value, config, assets)
    if sensitive_content(result) or sensitive_content(traces):
        fail("SENSITIVE_OUTPUT", "output", "result")
    result = parse(ExpressionResult, result, stage="output")
    bases = {i.item_id: i for i in value.rule_result.items}
    views = {v.bundle.event_key: v for v in value.generation_input.events}
    parents = {s.event_key: s for s in value.rule_result.snapshots}
    if (len(result.presentations) != len(bases)
            or len({p.base_item.item_id for p in result.presentations}) != len(bases)
            or {p.base_item.item_id for p in result.presentations} != set(bases)
            or len(result.assessments) != len(bases) or len(traces) != len(bases)):
        fail("G2_PR5_OUTPUT_INVALID", "output", "partition")
    expected_snapshots = []
    prior = value.previous_state
    called, used, seen = 0, 0, set()
    for presentation, assessment, trace in zip(result.presentations, result.assessments, traces, strict=True):
        base = bases[presentation.base_item.item_id]
        request = project_request(value, base, views[base.event_key], config, assets)
        if (presentation.base_item != base or presentation.event_key != base.event_key
                or presentation.event_revision != base.event_revision or presentation.fact_revision != base.fact_revision
                or assessment.base_item_id != base.item_id or trace.base_item_id != base.item_id
                or (trace.status, trace.code) != (assessment.status, assessment.code)):
            fail("G2_PR5_OUTPUT_INVALID", "output", "immutable_base")
        if presentation.selection == "rule":
            if presentation != rule_presentation(base) or assessment.status == "accepted":
                fail("G2_PR5_OUTPUT_INVALID", "output", "rule_fallback")
        else:
            if request is None or value.mode != "mock" or assessment.status != "accepted" or assessment.code is not None:
                fail("G2_PR5_OUTPUT_INVALID", "output", "selection")
            if (assessment.locator_status, assessment.numeric_scope_status, assessment.closed_render_status) != ("passed",) * 3:
                fail("G2_PR5_OUTPUT_INVALID", "output", "assessment")
            headline, body = render(request, presentation.style_id, presentation.claim_order, assets)
            if presentation != identify(base, headline, body, presentation.style_id, presentation.claim_order, "mock_closed"):
                fail("G2_PR5_OUTPUT_INVALID", "output", "presentation")
            draft = dict(kind="closed", style_id=presentation.style_id, claim_order=presentation.claim_order,
                         refs=[data(r) for r in refs_for(request)], headline=headline, body=body)
            from .contracts import CompletionResult
            validate_draft(CompletionResult(content=json_bytes(draft).decode(),
                response_sha256=digest(draft), response_bytes=len(json_bytes(draft))), request, base, assets)
        if trace.mock_calls:
            from .assets import request_payload
            if (request is None or value.mode != "mock" or trace.request_sha256 != request.request_sha256
                    or trace.request_bytes != len(request_payload(request, assets))
                    or trace.request_bytes > config.max_request_bytes
                    or trace.response_bytes > config.max_response_bytes and trace.code != "OUTPUT_TOO_LARGE"
                    or assessment.status == "skipped"):
                fail("G2_PR5_OUTPUT_INVALID", "output", "trace")
            called += 1
            used += trace.request_bytes
        elif assessment.status != "skipped" or trace.request_bytes or trace.response_bytes:
            fail("G2_PR5_OUTPUT_INVALID", "output", "trace")
        if trace.mock_calls == 0 and assessment.status == "accepted":
            fail("G2_PR5_OUTPUT_INVALID", "output", "trace")
        seen.add(request.request_sha256 if request else None)
        expected_snapshots.append(observe(presentation, parents[base.event_key], prior.snapshots if prior else ()))
    if tuple(expected_snapshots) != result.snapshots or result.cursor != value.rule_result.cursor:
        fail("G2_PR5_STATE_CHAIN_INVALID", "history", "snapshots")
    state = result.next_state
    if (state.namespace != namespace(value, config) or state.mode != value.mode
            or state.config_sha256 != digest(config) or state.cursor != result.cursor
            or state.previous_state_sha256 != (digest(prior) if prior else None)
            or state.snapshots != (prior.snapshots if prior else ()) + result.snapshots
            or state.requests_reserved != (prior.requests_reserved if prior else 0) + called
            or state.request_bytes_reserved != (prior.request_bytes_reserved if prior else 0) + used
            or state.response_bytes_reserved != (prior.response_bytes_reserved if prior else 0) + called * config.max_response_bytes
            or called > config.max_requests_per_step or state.requests_reserved > config.max_requests_per_run
            or state.request_bytes_reserved > config.max_request_bytes_per_run
            or state.response_bytes_reserved > config.max_response_bytes_per_run):
        fail("G2_PR5_STATE_CHAIN_INVALID", "history", "state")
    if result.coverage_gaps != tuple(data(g) for g in value.generation_input.coverage_gaps):
        fail("G2_PR5_OUTPUT_INVALID", "output", "coverage_gaps")
    synthetic_requests = {}
    for base in bases.values():
        request = project_request(value, base, views[base.event_key], config, assets)
        if base.record_origin == "synthetic" and request is not None:
            synthetic_requests[request.request_sha256] = request
    if len({d.request_sha256 for d in result.drafts}) != len(result.drafts):
        fail("G2_PR5_OUTPUT_INVALID", "output", "drafts")
    for draft in result.drafts:
        if draft.request_sha256 not in seen or draft.request_sha256 not in synthetic_requests:
            fail("G2_PR5_OUTPUT_INVALID", "output", "drafts")
        request = synthetic_requests[draft.request_sha256]
        if (draft.ref_ids != tuple(r.ref_id for r in request.citations)
                or len(draft.text.encode("utf-8")) > config.max_response_bytes):
            fail("G2_PR5_OUTPUT_INVALID", "output", "drafts")
    return result
