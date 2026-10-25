"""In-memory mock and compatible JSON envelope parser. No HTTP client exists here."""

from dataclasses import dataclass

from evals.intelligence_g2.contracts import json_bytes
from evals.intelligence_g2.pr4.sensitive import sensitive_content
from evals.intelligence_v1.exceptions import ContractError
from evals.intelligence_v1.hashing import sha256_bytes

from .assets import request_payload, strict_json
from .contracts import CallBudget, Code, CompletionResult, ExpressionRequest, data, fail, parse
from .styles import closed_response


@dataclass(frozen=True)
class TransportReply:
    body: bytes
    status: int = 200


class MockTransport:
    def __init__(self, assets):
        self.assets = assets

    async def exchange(self, request_bytes, *, request_sha256):
        wire = strict_json(request_bytes)
        request = parse(ExpressionRequest, strict_json(wire["messages"][1]["content"])["untrusted_evidence"])
        if request.request_sha256 != request_sha256:
            fail("STALE_RESULT", "adapter", "request_sha256")
        overrides = strict_json(self.assets.responses)["responses"]
        if request_sha256 in overrides:
            script = overrides[request_sha256]
            if (not isinstance(script, dict) or set(script) != {"status", "body_utf8"}
                    or type(script["status"]) is not int or not isinstance(script["body_utf8"], str)):
                fail("CONFIGURATION", "adapter", "mock_response")
            return TransportReply(script["body_utf8"].encode("utf-8"), script["status"])
        result = data(closed_response(request, self.assets))
        return TransportReply(json_bytes(dict(choices=[dict(finish_reason="stop", message={
            "content": json_bytes(result).decode()})], usage=None)))


def reported_usage(value):
    if not isinstance(value, dict):
        return None
    result = {key: value[key] for key in ("prompt_tokens", "completion_tokens", "total_tokens")
              if type(value.get(key)) is int and 0 <= value[key] <= 2**63 - 1}
    return result or None


class AdapterError(Exception):
    """Injected transport faults use a fixed code, never an exception body."""
    def __init__(self, code: Code):
        self.code = code
        super().__init__("controlled transport error")


def parse_completion(reply, budget):
    if type(reply.status) is not int:
        fail("INVALID_ENVELOPE", "adapter", "http_status")
    if not isinstance(reply.body, bytes):
        fail("INVALID_ENVELOPE", "adapter", "response")
    if len(reply.body) > budget.max_response_bytes:
        fail("OUTPUT_TOO_LARGE", "adapter", "response_bytes")
    code = {401: "AUTHENTICATION", 403: "AUTHENTICATION", 402: "QUOTA", 429: "RATE_LIMIT"}.get(reply.status)
    if code or not 200 <= reply.status < 300:
        fail(code or "PROVIDER_HTTP", "adapter", "http_status")
    envelope = strict_json(reply.body)
    if sensitive_content(envelope):
        fail("SENSITIVE_OUTPUT", "adapter", "response")
    if not isinstance(envelope, dict):
        fail("INVALID_ENVELOPE", "adapter", "envelope")
    try:
        choices = envelope["choices"]
        if not isinstance(choices, list) or len(choices) != 1:
            fail("INVALID_ENVELOPE", "adapter", "choices")
        choice = choices[0]
        message = choice["message"]
        if not isinstance(message, dict):
            fail("INVALID_ENVELOPE", "adapter", "message")
        if message.get("tool_calls") or message.get("function_call") or choice.get("finish_reason") in {"tool_calls", "function_call"}:
            fail("TOOL_CALL_FORBIDDEN", "adapter", "tool_calls")
        reason = choice.get("finish_reason")
        if reason == "length":
            fail("OUTPUT_TRUNCATED", "adapter", "finish_reason")
        if reason == "content_filter":
            fail("CONTENT_FILTERED", "adapter", "finish_reason")
        if reason != "stop" or not isinstance(message.get("content"), str) or not message["content"].strip():
            fail("INVALID_ENVELOPE", "adapter", "content")
    except (KeyError, TypeError, IndexError):
        fail("INVALID_ENVELOPE", "adapter", "envelope")
    return CompletionResult(content=message["content"], response_bytes=len(reply.body),
        response_sha256=sha256_bytes(reply.body), usage=reported_usage(envelope.get("usage")))


class MockCompletionAdapter:
    def __init__(self, assets, transport=None):
        self.assets = assets
        self.transport = transport or MockTransport(assets)

    async def generate(self, request, *, budget: CallBudget):
        raw = request_payload(request, self.assets)
        if len(raw) > budget.max_request_bytes:
            fail("BUDGET_EXCEEDED", "budget", "request_bytes")
        try:
            reply = await self.transport.exchange(raw, request_sha256=request.request_sha256)
        except AdapterError as error:
            fail(error.code, "adapter", "transport")
        try:
            return parse_completion(reply, budget)
        except ContractError as error:
            usage = None
            if isinstance(reply.body, bytes) and len(reply.body) <= budget.max_response_bytes:
                try:
                    parsed = strict_json(reply.body)
                    usage = reported_usage(parsed.get("usage")) if isinstance(parsed, dict) else None
                except ContractError:
                    pass
            error.safe_telemetry = dict(usage=usage,
                response_bytes=len(reply.body) if isinstance(reply.body, bytes) else 0,
                response_sha256=sha256_bytes(reply.body) if isinstance(reply.body, bytes) else None)
            raise
