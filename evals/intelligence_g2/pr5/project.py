"""Revalidate PR4, then expose approved claims only, never Persona or body archives."""

from evals.intelligence_g2.pr2.validate_output import get, instant
from evals.intelligence_g2.pr4.policy import choose, quote_allowance
from evals.intelligence_g2.pr4.sensitive import sensitive_content
from evals.intelligence_g2.pr4.validate_output import preflight
from evals.intelligence_g2.pr4.validate_output import validate_output as validate_rule

from .assets import checked_assets, strict_json
from .contracts import ExpressionInput, ExpressionRequest, PR5Config, data, digest, fail, parse


def namespace(value, config):
    return digest(dict(parent_namespace=value.generation_input.namespace,
                       config_sha256=digest(config), mode=value.mode))


def checked_input(value, config, assets):
    raw = get(value, "generation_input", {})
    preflight(raw)  # Before deserializing any nested text, including model_copy bypasses.
    cutoff = instant(get(get(raw, "cursor", {}), "as_of"))
    from .load_run import preflight_rule
    raw_rule = get(value, "rule_result", {})
    preflight_rule(data(raw_rule), cutoff)
    rule_state = get(raw_rule, "next_state", {})
    for pointer in get(rule_state, "source_metadata", ()):
        if get(pointer, "available_at") and instant(get(pointer, "available_at")) > cutoff:
            fail("FUTURE_VERSION", "temporal", "available_at")
    prior = get(value, "previous_state")
    if prior:
        previous = get(prior, "cursor", {})
        time = instant(get(previous, "as_of"))
        if time >= cutoff or any(instant(get(s, "as_of")) > time for s in get(prior, "snapshots", ())):
            fail("FUTURE_EVIDENCE", "temporal", "previous_state")
    value, config = parse(ExpressionInput, value), parse(PR5Config, config)
    checked_assets(assets, config)
    if value.config_sha256 != digest(config):
        fail("CONFIG_NOT_PINNED", "input", "config_sha256")
    validate_rule(value.rule_result, value.generation_input, value.rule_config)
    if sensitive_content(value.generation_input.source_coverage):
        fail("SENSITIVE_OUTPUT", "input", "source_coverage")
    if sensitive_content(value.rule_result):
        fail("SENSITIVE_OUTPUT", "input", "rule_result")
    cursor = value.generation_input.cursor
    if value.rule_result.cursor != cursor:
        fail("G2_PR5_PARENT_RUN_MISMATCH", "input", "cursor")
    state = value.previous_state
    if state is None:
        if value.previous_state_sha256 is not None or cursor.ordinal != 0 or cursor.previous_step_id is not None:
            fail("G2_PR5_STATE_CHAIN_INVALID", "history", "initial_cursor")
    elif (digest(state) != value.previous_state_sha256 or state.namespace != namespace(value, config)
            or state.config_sha256 != digest(config) or state.mode != value.mode
            or cursor.timeline_id != state.cursor.timeline_id or cursor.ordinal != state.cursor.ordinal + 1
            or cursor.previous_step_id != state.cursor.step_id
            or state.requests_reserved > config.max_requests_per_run
            or state.request_bytes_reserved > config.max_request_bytes_per_run
            or state.response_bytes_reserved > config.max_response_bytes_per_run
            or len({s.snapshot_id for s in state.snapshots}) != len(state.snapshots)):
        fail("G2_PR5_STATE_CHAIN_INVALID", "history", "previous_state")
    return value, config


def project_request(value, item, view, config, assets):
    if item.tier_candidate == "hold":
        return None
    approved, tier, _, _ = choose(view, value.rule_config)
    if (approved is None or tier != item.tier_candidate
            or tuple(c.claim_key for c in approved.claims) != item.selected_claim_keys
            or not quote_allowance(approved, {p.doc_version_id: p for p in view.source_pointers})):
        fail("G2_PR5_PARENT_RUN_MISMATCH", "input", "approved_request")
    if (len(approved.claims) > config.max_claims or len(approved.citations) > config.max_refs
            or len({r.doc_version_id for r in approved.citations}) > config.max_documents):
        return None
    catalog = strict_json(assets.styles)
    styles = tuple(s["id"] for s in catalog["styles"] if s["mode"] == approved.mode)
    request = ExpressionRequest(request_sha256="0" * 64, base_item_id=item.item_id,
        event_key=item.event_key, event_revision=item.event_revision, fact_revision=item.fact_revision,
        as_of=value.rule_result.cursor.as_of, mode=approved.mode, claims=approved.claims,
        citations=approved.citations, required_risks=item.risks, style_ids=styles,
        max_visible_chars=approved.max_visible_chars, prompt_sha256=config.prompt_sha256,
        style_sha256=config.style_sha256)
    return request.model_copy(update={"request_sha256": request_digest(request)})


def request_digest(request):
    return digest({k: v for k, v in data(request).items() if k != "request_sha256"})
