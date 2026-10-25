"""PR5 review regressions: expired completions and unvalidated return objects."""

import asyncio

import pytest

from evals.intelligence_g2.contracts import G2Error, json_bytes
from evals.intelligence_g2.pr5 import pipeline
from evals.intelligence_g2.pr5.adapter import (
    MockCompletionAdapter,
    TransportReply,
    parse_completion,
)
from evals.intelligence_g2.pr5.contracts import CallBudget, data
from evals.intelligence_g2.pr5.pipeline import GenerationControl, execute_step, rule_presentation
from evals.intelligence_g2.pr5.styles import closed_response
from evals.intelligence_v1.hashing import sha256_bytes

from .support import envelope, reply, request_for, settings


def assert_fallback(row, item, code):
    assessment, trace = row.result.assessments[0], row.traces[0]
    assert (assessment.status, assessment.code) == ("fallback", code)
    assert (trace.status, trace.code, trace.mock_calls) == ("fallback", code, 1)
    assert json_bytes(row.result.presentations[0]) == json_bytes(rule_presentation(item))
    assert row.result.drafts == ()
    assert trace.usage is None and trace.usage_origin == "unknown"
    assert trace.response_bytes == 0 and trace.response_sha256 is None
    assert trace.model_calls == trace.external_requests == trace.billed_cost == 0
    assert row.result.next_state.requests_reserved == 1
    assert row.result.next_state.response_bytes_reserved == 8192


@pytest.mark.parametrize("malformed", [False, True])
def test_T42_review_cancel_suppressed_response_is_expired(malformed, monkeypatch):
    config, assets = settings()
    value, item, request = request_for()
    cancelled, calls = [], []

    class SwallowsCancellation:
        async def exchange(self, raw, *, request_sha256):
            calls.append(request_sha256)
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                cancelled.append(True)
                await asyncio.sleep(0.01)
                return reply(envelope(closed_response(request, assets)))

    class LateMalformed:
        async def generate(self, request, *, budget):
            await transport.exchange(b"", request_sha256=request.request_sha256)
            return {"content": "{}"}

    def never_validate(*args, **kwargs):
        pytest.fail("expired response reached expression validation")

    monkeypatch.setattr(pipeline, "validate_draft", never_validate)
    transport = SwallowsCancellation()
    generator = LateMalformed() if malformed else MockCompletionAdapter(assets, transport)
    row = asyncio.run(execute_step(expression_input=value, generator=generator, config=config, assets=assets))
    assert cancelled == [True] and calls == [request.request_sha256]
    assert row.traces[0].elapsed_ms >= config.timeout_seconds * 1000
    assert_fallback(row, item, "TIMEOUT")


@pytest.mark.parametrize("kind", ["dict", "string", "object", "invalid_model"])
def test_T42_review_unvalidated_completion_cannot_supply_telemetry(kind, capsys, caplog):
    config, assets = settings()
    value, item, request = request_for()
    canary = "UNVALIDATED_RESPONSE_MUST_NOT_BE_LOGGED"
    valid = parse_completion(reply(envelope(closed_response(request, assets))), CallBudget())

    class Opaque:
        @property
        def usage(self):
            pytest.fail("unvalidated object telemetry was accessed")

    raw = {"dict": {"content": canary, "usage": {"total_tokens": 999}},
        "string": canary, "object": Opaque(),
        "invalid_model": valid.model_copy(update={"response_bytes": "invalid"})}[kind]
    calls = []

    class InvalidGenerator:
        async def generate(self, request, *, budget):
            calls.append(request.request_sha256)
            return raw

    row = asyncio.run(execute_step(expression_input=value, generator=InvalidGenerator(), config=config, assets=assets))
    assert calls == [request.request_sha256]
    assert_fallback(row, item, "SCHEMA_INVALID")
    assert row.result.assessments[0].locator_status == "not_evaluated"
    assert canary not in json_bytes(row).decode() + capsys.readouterr().out + caplog.text


@pytest.mark.parametrize("as_dict", [False, True])
def test_T42_review_timely_valid_completion_keeps_usage(as_dict):
    config, assets = settings()
    value, item, request = request_for()
    calls = []
    completion = parse_completion(reply(envelope(closed_response(request, assets),
        usage={"total_tokens": 17})), CallBudget())

    class TimelyGenerator:
        async def generate(self, request, *, budget):
            calls.append(request.request_sha256)
            await asyncio.sleep(0)
            return data(completion) if as_dict else completion

    row = asyncio.run(execute_step(expression_input=value, generator=TimelyGenerator(), config=config, assets=assets))
    assessment, trace = row.result.assessments[0], row.traces[0]
    assert calls == [request.request_sha256]
    assert (assessment.status, assessment.code) == ("accepted", None)
    assert row.result.presentations[0].selection == "mock_closed"
    assert row.result.presentations[0].base_item == item
    assert row.result.presentations[0].event_revision == item.event_revision
    assert row.result.presentations[0].fact_revision == item.fact_revision
    assert trace.usage == {"total_tokens": 17} and trace.usage_complete
    assert trace.usage_origin == "mock_fixture"
    assert trace.response_sha256 == completion.response_sha256
    assert trace.response_bytes == completion.response_bytes and trace.mock_calls == 1


def error_response(fault):
    if fault == "truncated":
        return reply(envelope("{}", reason="length", usage={"total_tokens": 77}))
    if fault == "http429":
        return TransportReply(b'{"usage":{"total_tokens":77}}', 429)
    if fault == "invalid_json":
        return TransportReply(b"{bad")
    raise RuntimeError("PRIVATE_TRANSPORT_ERROR_MUST_NOT_BE_LOGGED")


@pytest.mark.parametrize("late", [False, True])
@pytest.mark.parametrize("fault,code,usage", [
    ("truncated", "OUTPUT_TRUNCATED", {"total_tokens": 77}),
    ("http429", "RATE_LIMIT", {"total_tokens": 77}),
    ("invalid_json", "INVALID_JSON", None),
    ("exception", "INVALID_ENVELOPE", None),
])
def test_T42_review_error_deadline_and_timely_telemetry(late, fault, code, usage, capsys, caplog):
    config, assets = settings()
    value, item, request = request_for()
    calls, cancelled = [], []

    class ErrorTransport:
        async def exchange(self, raw, *, request_sha256):
            calls.append(request_sha256)
            if late:
                try:
                    await asyncio.Event().wait()
                except asyncio.CancelledError:
                    cancelled.append(True)
                    await asyncio.sleep(0.02)
            else:
                await asyncio.sleep(0)
            return error_response(fault)

    row = asyncio.run(execute_step(expression_input=value,
        generator=MockCompletionAdapter(assets, ErrorTransport()), config=config, assets=assets))
    assert calls == [request.request_sha256] and cancelled == ([True] if late else [])
    if late:
        assert row.traces[0].elapsed_ms >= config.timeout_seconds * 1000
        assert_fallback(row, item, "TIMEOUT")
    else:
        a, t = row.result.assessments[0], row.traces[0]
        assert (a.status, a.code, t.status, t.code) == ("fallback", code, "fallback", code)
        assert json_bytes(row.result.presentations[0]) == json_bytes(rule_presentation(item))
        assert t.mock_calls == 1 and row.result.next_state.requests_reserved == 1
        assert row.result.drafts == ()
        if fault != "exception":
            response = error_response(fault)
            assert t.response_bytes == len(response.body)
            assert t.response_sha256 == sha256_bytes(response.body)
        else:
            assert t.response_bytes == 0 and t.response_sha256 is None
        assert t.usage == usage
        assert t.usage_origin == ("mock_fixture" if usage else "unknown")
        assert t.usage_complete is (usage is not None)
    assert "PRIVATE_TRANSPORT_ERROR_MUST_NOT_BE_LOGGED" not in (
        row.model_dump_json() + capsys.readouterr().out + caplog.text)


@pytest.mark.parametrize("cancelled", [False, True])
def test_T42_review_revocation_precedes_expired_adapter_error(cancelled):
    config, assets = settings()
    value, _, _ = request_for()
    control = GenerationControl()
    calls = []

    class RevokedTransport:
        async def exchange(self, raw, *, request_sha256):
            calls.append(request_sha256)
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                control.cancelled = cancelled
                control.valid = False
                await asyncio.sleep(0.02)
                return error_response("http429")

    async def check():
        with pytest.raises(asyncio.CancelledError if cancelled else G2Error) as caught:
            await execute_step(expression_input=value,
                generator=MockCompletionAdapter(assets, RevokedTransport()),
                config=config, assets=assets, control=control)
        if not cancelled:
            assert (caught.value.code, caught.value.stage, caught.value.field) == (
                "STALE_RESULT", "control", "request")

    asyncio.run(check())
    assert len(calls) == 1
