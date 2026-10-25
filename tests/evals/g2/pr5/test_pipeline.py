"""T38/T41/T42/T44-T46: real asynchronous mock orchestration, no external model."""

import asyncio

import pytest

from evals.intelligence_g2.contracts import G2Error, json_bytes
from evals.intelligence_g2.pr4.contracts import PR4Config
from evals.intelligence_g2.pr4.pipeline import generate_items
from evals.intelligence_g2.pr5.adapter import AdapterError, MockCompletionAdapter, TransportReply
from evals.intelligence_g2.pr5.contracts import data, digest
from evals.intelligence_g2.pr5.pipeline import GenerationControl, execute_step
from evals.intelligence_g2.pr5.replay import run_sequence
from evals.intelligence_g2.pr5.styles import closed_response
from evals.intelligence_g2.pr5.validate_output import validate_output

from .support import envelope, parent_values, reply, request_for, run, secondary_values, settings


@pytest.mark.parametrize("case", ["FOCUS", "RADAR", "CORRECTION", "WITHDRAWAL", "CONFLICT", "REPEAT"])
def test_T45_positive_mock_and_exact_rule_control(case):
    _, mock, _ = run(case)
    _, rule, _ = run(case, mode="rule")
    assert len(mock) == len(rule)
    for a, b in zip(mock, rule, strict=True):
        for p, q in zip(a.result.presentations, b.result.presentations, strict=True):
            assert p.selection == "mock_closed" and q.selection == "rule"
            assert p.base_item == q.base_item and p.fact_revision == q.fact_revision
            assert p.event_key == q.event_key and p.event_revision == q.event_revision
        assert all(t.model_calls == t.external_requests == t.billed_cost == 0 for t in a.traces)
        assert all(t.mock_calls == 0 for t in b.traces)
        assert all(s.semantic_truth == "not_evaluated" for s in a.result.assessments)


@pytest.mark.parametrize("variant", ["a", "b"])
def test_T44_secondary_contract_positive(variant):
    config, assets = settings()
    values, rules = secondary_values()

    class Generator:
        async def generate(self, request, *, budget):
            assert request.mode == "secondary"
            from evals.intelligence_g2.pr5.adapter import parse_completion
            return parse_completion(reply(envelope(closed_response(request, assets, "secondary-" + variant))), budget)

    _, rows = asyncio.run(run_sequence(values, rules, rule_config=PR4Config(), config=config,
        assets=assets, generator=Generator()))
    p = rows[0].result.presentations[0]
    assert p.selection == "mock_closed" and p.base_item.tier_candidate == "radar"
    assert "摘要" in p.body and p.base_item.claim_summaries[0].verification_state == "unverified"


def test_T38_free_draft_never_replaces_rule():
    _, assets = settings()
    _, _, request = request_for("RADAR")
    draft = dict(kind="free_text", text="Training is faster, according to this report.",
                 refs=data(closed_response(request, assets))["refs"])
    _, rows, transport = run("RADAR", script=lambda _: reply(envelope(draft)))
    result = rows[0].result
    assert len(transport.calls) == 1 and result.presentations[0].selection == "rule"
    assert result.presentations[0].body == result.presentations[0].base_item.what_happened.text
    assert result.assessments[0].code == "EXPRESSION_NOT_CLOSED"
    assert result.drafts[0].semantic_support == "not_verified" and result.drafts[0].status == "not_selected"


@pytest.mark.parametrize("status,code", [(401, "AUTHENTICATION"), (403, "AUTHENTICATION"),
    (402, "QUOTA"), (429, "RATE_LIMIT"), (500, "PROVIDER_HTTP")])
def test_T42_service_errors_fallback_once(status, code):
    _, rows, transport = run(script=lambda _: TransportReply(b"PRIVATE_PROVIDER_MESSAGE", status))
    e = rows[0]
    assert len(transport.calls) == 1 and e.traces[0].mock_calls == 1
    assert (e.result.assessments[0].code, e.result.assessments[0].status) == (code, "fallback")
    assert e.result.presentations[0].selection == "rule"
    assert "PRIVATE_PROVIDER_MESSAGE" not in json_bytes(e).decode()
    assert e.traces[0].usage is None and e.traces[0].usage_complete is False


@pytest.mark.parametrize("fault,code", [("length", "OUTPUT_TRUNCATED"), ("content_filter", "CONTENT_FILTERED"),
    ("bad_json", "INVALID_JSON"), ("too_large", "OUTPUT_TOO_LARGE"), ("connection", "CONNECTION")])
def test_T42_faults_classification_and_returned_usage(fault, code):
    def script(_):
        if fault == "bad_json":
            return TransportReply(b"{bad")
        if fault == "too_large":
            return TransportReply(b" " * 8193)
        if fault == "connection":
            raise AdapterError("CONNECTION")
        return reply(envelope("{}", reason=fault, usage=dict(total_tokens=50, debug="discard")))
    _, rows, transport = run(script=script)
    e = rows[0]
    assert e.result.assessments[0].code == code and len(transport.calls) == 1
    assert e.result.presentations[0].base_item.generator == "rule"
    if fault in {"length", "content_filter"}:
        assert e.traces[0].usage == {"total_tokens": 50} and e.traces[0].usage_complete
    else:
        assert e.traces[0].usage is None


def test_T42_timeout_cancels_mock_and_falls_back_once():
    cancelled = []

    async def script(_):
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.append(True)
    _, rows, transport = run(script=script)
    assert cancelled == [True] and len(transport.calls) == 1
    assert rows[0].result.assessments[0].code == "TIMEOUT"
    assert rows[0].result.presentations[0].selection == "rule"


@pytest.mark.parametrize("cancelled", [True, False])
def test_T42_revocation_and_late_completion_cannot_publish(cancelled):
    config, assets = settings()
    control = GenerationControl()

    class Late:
        async def generate(self, request, *, budget):
            control.cancelled = cancelled
            control.valid = False
            from evals.intelligence_g2.pr5.adapter import parse_completion
            return parse_completion(reply(envelope(closed_response(request, assets))), budget)
    if cancelled:
        with pytest.raises(asyncio.CancelledError):
            run(generator=Late(), control=control)
    else:
        with pytest.raises(G2Error) as caught:
            run(generator=Late(), control=control)
        assert caught.value.code == "STALE_RESULT"


def test_T41_sensitive_model_output_never_retained_anywhere(capsys, caplog):
    _, assets = settings()
    _, _, request = request_for("RADAR")
    canary = "TEST_ONLY_FAKE_CREDENTIAL_1234567890"
    draft = dict(kind="free_text", text='{"api_key": "' + canary + '"}',
                 refs=data(closed_response(request, assets))["refs"])
    _, rows, _ = run("RADAR", script=lambda _: reply(envelope(draft)))
    assert rows[0].result.assessments[0].code == "SENSITIVE_OUTPUT"
    assert rows[0].result.drafts == () and rows[0].result.presentations[0].selection == "rule"
    assert canary not in json_bytes(rows[0]).decode() + capsys.readouterr().out + caplog.text


def test_T41_injected_tool_call_rejected_without_capabilities():
    raw = envelope("{}")
    raw["choices"][0]["message"]["tool_calls"] = [dict(name="read_file", arguments=".env")]
    _, rows, transport = run(script=lambda _: reply(raw))
    assert rows[0].result.assessments[0].code == "TOOL_CALL_FORBIDDEN"
    assert len(transport.calls) == 1 and rows[0].traces[0].external_requests == 0


@pytest.mark.parametrize("right", ["metadata_only", "unknown"])
def test_T44_no_model_for_unavailable_excerpt_rights(right):
    config, assets = settings()
    values, _ = parent_values()
    view = values[0].events[0]
    pointers = tuple(p.model_copy(update={"redistribution_rights": right,
        "policy": p.policy.model_copy(update={"redistribution_rights": right, "allowed_use": ("metadata",)})})
        for p in view.source_pointers)
    value = values[0].model_copy(update={"events": (view.model_copy(update={"source_pointers": pointers}),)})
    rule = generate_items(generation_input=value, config=PR4Config())

    class Never:
        async def generate(self, request, *, budget):
            pytest.fail("permission gate must precede adapter")
    _, rows = asyncio.run(run_sequence((value,), (rule,), rule_config=PR4Config(), config=config,
        assets=assets, generator=Never()))
    assert rule.items[0].tier_candidate == "hold" and rows[0].traces[0].mock_calls == 0


@pytest.mark.parametrize("case", ["EMPTY", "HOLD"])
def test_T46_empty_and_hold_do_not_call(case):
    _, rows, _ = run(case)
    assert all(t.mock_calls == 0 for t in rows[0].traces)
    assert all(p.selection == "rule" and p.body is None for p in rows[0].result.presentations)
    if case == "EMPTY":
        assert rows[0].result.presentations == ()


def test_T45_output_tampering_and_state_chain_rejected():
    config, assets = settings()
    inputs, rows, _ = run("REPEAT")
    assert rows[1].result.next_state.snapshots[:1] == rows[0].result.next_state.snapshots
    result = rows[0].result
    p = result.presentations[0]
    bad = result.model_copy(update={"presentations": (p.model_copy(update={"body": "fabricated"}),)})
    with pytest.raises(G2Error) as caught:
        validate_output(bad, inputs[0], config, assets, rows[0].traces)
    assert caught.value.code == "G2_PR5_OUTPUT_INVALID" and caught.value.field == "presentation"
    wrong = inputs[1].model_copy(update={"previous_state_sha256": "0" * 64})
    with pytest.raises(G2Error) as caught:
        asyncio.run(execute_step(expression_input=wrong, generator=MockCompletionAdapter(assets), config=config, assets=assets))
    assert caught.value.code == "G2_PR5_STATE_CHAIN_INVALID"


def test_T46_run_budget_is_reserved_before_mock_call():
    config, assets = settings()
    inputs, rows, _ = run("REPEAT")
    state = rows[0].result.next_state.model_copy(update={"requests_reserved": 128})
    value = inputs[1].model_copy(update={"previous_state": state, "previous_state_sha256": digest(state)})

    class Never:
        async def generate(self, request, *, budget):
            pytest.fail("exhausted run must not call")
    row = asyncio.run(execute_step(expression_input=value, generator=Never(), config=config, assets=assets))
    assert row.traces[0].mock_calls == 0 and row.result.assessments[0].code == "BUDGET_EXCEEDED"
    assert row.result.next_state.requests_reserved == 128


def test_T46_step_limit_keeps_all_events_in_deterministic_order():
    from evals.intelligence_g2.pr4.replay import run_sequence as parent_sequence
    from tests.evals.g2.pr2.support import make_input
    from tests.evals.g2.pr3.support import evidence_for

    config, assets = settings()
    specs = [dict(id="a" + str(i), title=f"Atlas Tool v{i}.0 release",
                  body=f"Atlas Tool v{i}.0 is released.") for i in range(20)]
    parents, evidence = evidence_for([make_input(specs, timeline="BUDGET-STEP")])
    values, rules = parent_sequence(parents, evidence, config=PR4Config())
    _, rows = asyncio.run(run_sequence(values, rules, rule_config=PR4Config(), config=config, assets=assets))
    row = rows[0]
    assert len(row.result.presentations) == 20
    assert sum(t.mock_calls for t in row.traces) == 16
    assert [p.event_key for p in row.result.presentations] == sorted(p.event_key for p in row.result.presentations)
    assert all(a.status == "accepted" for a in row.result.assessments[:16])
    assert all(a.status == "skipped" and a.code == "BUDGET_EXCEEDED" for a in row.result.assessments[16:])


def test_T43_current_future_input_calls_zero():
    config, assets = settings()
    value, _, _ = request_for()
    raw = data(value)
    raw["generation_input"]["events"][0]["citations"][0].update(
        available_at="2099-01-01T00:00:00Z", quote={"poison": True})

    class Never:
        async def generate(self, request, *, budget):
            pytest.fail("future input must not call")
    with pytest.raises(G2Error) as caught:
        asyncio.run(execute_step(expression_input=raw, generator=Never(), config=config, assets=assets))
    assert caught.value.code == "FUTURE_VERSION" and caught.value.field == "available_at"


def test_T42_oversized_http_error_body_still_falls_back_safely():
    _, rows, transport = run(script=lambda _: TransportReply(b"x" * 8193, 429))
    assert len(transport.calls) == 1
    assert rows[0].result.assessments[0].code == "OUTPUT_TOO_LARGE"
    assert rows[0].result.presentations[0].selection == "rule"


def test_T42_safe_result_ok_does_not_mark_failed_model_attempt_passed():
    from evals.intelligence_g2.pr5.replay import validation_report

    inputs, rows, _ = run(script=lambda _: TransportReply(b"PRIVATE_HTTP_BODY", 429))
    report = validation_report(inputs, rows)
    assert report["ok"] is True and report["model_attempts_ok"] is False and report["degraded"] is True
    assert report["counts"]["fallback"] == 1 and report["counts"]["accepted"] == 0
