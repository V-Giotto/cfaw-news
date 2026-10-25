"""T37-T44: structural validity does not establish semantic truth."""

from datetime import timedelta

import pytest

from evals.intelligence_g2.contracts import G2Error, json_bytes
from evals.intelligence_g2.pr4.contracts import PR4Config
from evals.intelligence_g2.pr5.adapter import (
    MockCompletionAdapter,
    TransportReply,
    parse_completion,
    reported_usage,
)
from evals.intelligence_g2.pr5.assets import request_payload, strict_json
from evals.intelligence_g2.pr5.contracts import CallBudget, CompletionResult, data
from evals.intelligence_g2.pr5.project import checked_input
from evals.intelligence_g2.pr5.styles import closed_response
from evals.intelligence_g2.pr5.validate_output import validate_draft
from evals.intelligence_v1.hashing import sha256_bytes

from .support import envelope, immediate, request_for, settings


def completed(draft):
    return parse_completion(TransportReply(json_bytes(envelope(draft))), CallBudget())


def rejected(draft, request, base, code, stage="expression", field=None):
    _, assets = settings()
    with pytest.raises(G2Error) as caught:
        validate_draft(completed(draft), request, base, assets)
    assert caught.value.code == code and caught.value.stage == stage
    if field:
        assert caught.value.field == field


@pytest.mark.parametrize("case", ["FOCUS", "RADAR", "CORRECTION", "WITHDRAWAL", "CONFLICT"])
@pytest.mark.parametrize("variant", ["a", "b"])
def test_T37_closed_positive_each_mode_and_style(case, variant):
    _, assets = settings()
    _, base, request = request_for(case)
    draft = closed_response(request, assets, request.mode + "-" + variant)
    accepted, safe = validate_draft(completed(draft), request, base, assets)
    assert accepted == draft and safe is None
    for claim in request.claims:
        assert claim.statement in draft.body
    assert base.generator == "rule"


@pytest.mark.parametrize("field,value,code", [
    ("doc_version_id", "invented:9", "CITATION_NOT_ALLOWED"),
    ("paragraph_id", "other-event-p1", "CITATION_NOT_ALLOWED"),
    ("ref_id", "unknown-ref", "CITATION_NOT_ALLOWED"),
    ("start", 1, "SPAN_MISMATCH"), ("quote_sha256", "0" * 64, "SPAN_MISMATCH")])
def test_T37_spoofed_refs_and_spans(field, value, code):
    _, assets = settings()
    _, base, request = request_for()
    draft = data(closed_response(request, assets))
    draft["refs"][0][field] = value
    rejected(draft, request, base, code, field="refs")


def test_T37_missing_duplicate_and_cross_event_refs():
    _, assets = settings()
    _, base, request = request_for()
    for refs in ([], [data(closed_response(request, assets).refs[0])] * 2):
        draft = data(closed_response(request, assets))
        draft["refs"] = refs
        rejected(draft, request, base, "CITATION_NOT_ALLOWED", field="refs")


def test_T38_legal_locator_wrong_fact_and_safe_free_draft():
    _, assets = settings()
    _, base, request = request_for("RADAR")
    draft = data(closed_response(request, assets))
    draft["body"] = draft["body"].replace("provides plugins", "speeds up training")
    rejected(draft, request, base, "EXPRESSION_NOT_CLOSED", field="closed_render")
    free = dict(kind="free_text", text="来源称训练速度更快。", refs=draft["refs"])
    accepted, safe = validate_draft(completed(free), request, base, assets)
    assert accepted is None and safe.semantic_support == "not_verified" and safe.status == "not_selected"


@pytest.mark.parametrize("old,new", [("40%", "400%"), ("40%", "40 percentage points"),
    ("v1.0", "v2.0"), ("40%", "average 40%"), ("40%", "up to 40%")])
def test_T39_numeric_unit_version_and_quantifier(old, new):
    _, assets = settings()
    _, base, request = request_for()
    draft = data(closed_response(request, assets))
    draft["body"] = draft["body"].replace(old, new)
    assert draft["body"] != closed_response(request, assets).body
    rejected(draft, request, base, "NUMERIC_SCOPE_MISMATCH", field="numeric_scope")


def test_T39_scope_metric_and_negation_not_filled_from_other_fields():
    _, assets = settings()
    _, base, request = request_for()
    for old, new, code in (("speed gain", "accuracy gain", "EXPRESSION_NOT_CLOSED"),
        ("summarization", "speed gain evaluation", "EXPRESSION_NOT_CLOSED"),
        ("claims a speed gain", "claims no speed gain", "NUMERIC_SCOPE_MISMATCH")):
        draft = data(closed_response(request, assets))
        draft["body"] = draft["body"].replace(old, new)
        rejected(draft, request, base, code)


@pytest.mark.parametrize("field", ["tier", "verification_state", "independent_support_count", "risks", "action"])
def test_T40_model_cannot_write_evidence_status_or_actions(field):
    _, assets = settings()
    _, base, request = request_for()
    draft = data(closed_response(request, assets))
    draft[field] = "independently_supported"
    rejected(draft, request, base, "SCHEMA_INVALID", field="draft")


def test_T40_no_independent_upgrade_or_missing_conflict_side():
    _, assets = settings()
    _, base, request = request_for()
    draft = data(closed_response(request, assets))
    draft["headline"] += "，独立实测证明"
    rejected(draft, request, base, "ATTRIBUTION_ESCALATION", field="attribution")
    _, base, request = request_for("CONFLICT")
    draft = data(closed_response(request, assets))
    draft["claim_order"] = draft["claim_order"][:1]
    rejected(draft, request, base, "EXPRESSION_NOT_CLOSED", field="style_order")


def test_T41_prompt_roles_schema_no_tools_and_data_only():
    _, assets = settings()
    _, _, request = request_for()
    wire = strict_json(request_payload(request, assets))
    assert [m["role"] for m in wire["messages"]] == ["system", "user"]
    assert "tools" not in wire and "functions" not in wire and wire["model"] == "mock-fixed-v1"
    content = strict_json(wire["messages"][1]["content"])
    assert "untrusted_evidence" in content and "Persona" not in content
    assert wire["messages"][0]["content"].startswith(assets.prompt.decode())


@pytest.mark.parametrize("key", ["api_key", "password", "access_token", "secret"])
def test_T41_quoted_credentials_rejected_in_free_or_closed(key):
    _, assets = settings()
    _, base, request = request_for("RADAR")
    canary = "TEST_ONLY_FAKE_CREDENTIAL_1234567890"
    draft = dict(kind="free_text", text='configuration {"' + key + '": "' + canary + '"}',
                 refs=data(closed_response(request, assets))["refs"])
    with pytest.raises(G2Error) as caught:
        validate_draft(completed(draft), request, base, assets)
    assert caught.value.code == "SENSITIVE_OUTPUT"
    assert canary not in str(caught.value)


@pytest.mark.parametrize("status,code", [(401, "AUTHENTICATION"), (403, "AUTHENTICATION"),
    (402, "QUOTA"), (429, "RATE_LIMIT"), (500, "PROVIDER_HTTP")])
def test_T42_http_statuses_do_not_expose_body(status, code):
    with pytest.raises(G2Error) as caught:
        parse_completion(TransportReply(b"PRIVATE_FAILURE_BODY", status), CallBudget())
    assert (caught.value.code, caught.value.stage, caught.value.field) == (code, "adapter", "http_status")
    assert "PRIVATE_FAILURE_BODY" not in str(caught.value)


@pytest.mark.parametrize("raw,code", [(b'{"a":1,"a":2}', "INVALID_JSON"), (b'{"a":NaN}', "INVALID_JSON"),
    (b"{broken", "INVALID_JSON"), (b"[]", "INVALID_ENVELOPE"), (b"{}", "INVALID_ENVELOPE"),
    (b" " * 8193, "OUTPUT_TOO_LARGE")])
def test_T42_invalid_json_envelope_and_size(raw, code):
    with pytest.raises(G2Error) as caught:
        parse_completion(TransportReply(raw), CallBudget())
    assert caught.value.code == code and caught.value.stage == "adapter"


@pytest.mark.parametrize("reason,code", [("length", "OUTPUT_TRUNCATED"),
    ("content_filter", "CONTENT_FILTERED"), ("tool_calls", "TOOL_CALL_FORBIDDEN")])
def test_T42_finish_reason_beats_valid_content(reason, code):
    with pytest.raises(G2Error) as caught:
        parse_completion(TransportReply(json_bytes(envelope("{}", reason=reason))), CallBudget())
    assert caught.value.code == code


def test_T42_usage_allowlist_and_reasoning_not_final_content():
    usage = reported_usage(dict(prompt_tokens=20, total_tokens=50, completion_tokens=True,
        debug="PRIVATE_SECRET", response_id="PRIVATE_SECRET"))
    assert usage == dict(prompt_tokens=20, total_tokens=50)
    raw = dict(choices=[dict(finish_reason="stop", message=dict(reasoning_content="PRIVATE_REASONING"))])
    with pytest.raises(G2Error) as caught:
        parse_completion(TransportReply(json_bytes(raw)), CallBudget())
    assert caught.value.code == "INVALID_ENVELOPE" and "PRIVATE_REASONING" not in str(caught.value)


def test_T43_future_ref_preflight_beats_malformed_span():
    _, assets = settings()
    _, base, request = request_for()
    draft = data(closed_response(request, assets))
    draft["refs"][0].update(available_at=(request.as_of + timedelta(days=1)).isoformat(), start={"poison": True})
    rejected(draft, request, base, "FUTURE_EVIDENCE", "temporal", "available_at")


def test_T43_input_future_preflight_beats_bad_quote_and_model_copy():
    config, assets = settings()
    value, _, _ = request_for()
    raw = data(value)
    raw["generation_input"]["events"][0]["citations"][0].update(
        available_at=(value.rule_result.cursor.as_of + timedelta(days=1)).isoformat(), quote={"poison": True})
    with pytest.raises(G2Error) as caught:
        checked_input(raw, config, assets)
    assert (caught.value.code, caught.value.stage, caught.value.field) == ("FUTURE_VERSION", "temporal", "available_at")
    config2 = PR4Config().model_copy(update={"budget_profile": "illegal"})
    with pytest.raises(G2Error):
        checked_input(value.model_copy(update={"rule_config": config2}), config, assets)


def test_T45_mock_immediate_is_deterministic_no_provider_calls():
    _, assets = settings()
    _, base, request = request_for()
    replies = [immediate(MockCompletionAdapter(assets).generate(request, budget=CallBudget())) for _ in range(2)]
    assert replies[0] == replies[1]
    assert replies[0].usage is None and replies[0].usage_origin == "mock_fixture"
    assert validate_draft(replies[0], request, base, assets)[0] is not None
    assert sha256_bytes(json_bytes(strict_json(replies[0].content)))


def test_T46_exact_response_byte_boundary_and_oversize():
    body = json_bytes(envelope("{}"))
    at_limit = body.rstrip() + b" " * (8192 - len(body.rstrip()))
    assert len(at_limit) == 8192
    assert parse_completion(TransportReply(at_limit), CallBudget()).response_bytes == 8192
    with pytest.raises(G2Error) as caught:
        parse_completion(TransportReply(at_limit + b" "), CallBudget())
    assert caught.value.code == "OUTPUT_TOO_LARGE"


def test_T46_completion_contract_forbids_extra_fields():
    from evals.intelligence_g2.pr5.contracts import parse
    with pytest.raises(G2Error) as caught:
        parse(CompletionResult, dict(content="{}", response_sha256="0" * 64, response_bytes=2,
                                     tools=["shell"]))
    assert caught.value.code == "SCHEMA_INVALID"
