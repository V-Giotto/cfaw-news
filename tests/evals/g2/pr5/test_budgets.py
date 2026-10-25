"""T46 exact limits and one-unit overflow, checked before dispatch."""

import asyncio

import pytest

from evals.intelligence_g2.contracts import G2Error, digest
from evals.intelligence_g2.pr5.adapter import MockCompletionAdapter, MockTransport
from evals.intelligence_g2.pr5.assets import request_payload
from evals.intelligence_g2.pr5.contracts import CallBudget
from evals.intelligence_g2.pr5.pipeline import execute_step
from evals.intelligence_g2.pr5.project import request_digest

from .support import immediate, request_for, run, settings


def test_T46_exact_request_byte_limit_and_one_byte_overflow():
    _, assets = settings()
    _, _, original = request_for()

    def padded(n):
        claim = original.claims[0].model_copy(update={"limitations": original.claims[0].limitations + ("x" * n,)})
        request = original.model_copy(update={"claims": (claim,) + original.claims[1:]})
        return request.model_copy(update={"request_sha256": request_digest(request)})

    amount = 32768 - len(request_payload(padded(1), assets)) + 1
    at_limit, over = padded(amount), padded(amount + 1)
    assert len(request_payload(at_limit, assets)) == 32768
    assert len(request_payload(over, assets)) == 32769

    class CountTransport(MockTransport):
        calls = 0

        async def exchange(self, raw, *, request_sha256):
            self.calls += 1
            return await super().exchange(raw, request_sha256=request_sha256)

    transport = CountTransport(assets)
    adapter = MockCompletionAdapter(assets, transport)
    assert immediate(adapter.generate(at_limit, budget=CallBudget())).finish_reason == "stop"
    assert transport.calls == 1
    with pytest.raises(G2Error) as caught:
        immediate(adapter.generate(over, budget=CallBudget()))
    assert (caught.value.code, caught.value.stage, caught.value.field) == (
        "BUDGET_EXCEEDED", "budget", "request_bytes")
    assert transport.calls == 1


@pytest.mark.parametrize("dimension", ["requests", "request_bytes", "response_bytes"])
@pytest.mark.parametrize("overflow", [False, True])
def test_T46_cumulative_boundary_reserves_before_dispatch(dimension, overflow):
    config, assets = settings()
    inputs, rows, _ = run("REPEAT")
    value = inputs[1]
    item = value.rule_result.items[0]
    from evals.intelligence_g2.pr5.project import project_request
    request = project_request(value, item, value.generation_input.events[0], config, assets)
    state = rows[0].result.next_state
    updates = {
        "requests": dict(requests_reserved=127 + int(overflow)),
        "request_bytes": dict(request_bytes_reserved=4194304 - len(request_payload(request, assets)) + int(overflow)),
        "response_bytes": dict(response_bytes_reserved=1048576 - 8192 + int(overflow)),
    }[dimension]
    # Synthetic accounting checkpoint; its digest is re-pinned explicitly only for this boundary test.
    state = state.model_copy(update=updates)
    value = value.model_copy(update={"previous_state": state, "previous_state_sha256": digest(state)})
    row = asyncio.run(execute_step(expression_input=value, generator=MockCompletionAdapter(assets),
                                   config=config, assets=assets))
    assert row.traces[0].mock_calls == (0 if overflow else 1)
    assert row.result.assessments[0].code == ("BUDGET_EXCEEDED" if overflow else None)
    assert row.result.presentations[0].selection == ("rule" if overflow else "mock_closed")
