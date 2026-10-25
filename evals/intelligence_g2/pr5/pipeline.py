"""Optional mock expression cannot change the validated rule result."""

import asyncio
from dataclasses import dataclass
from time import perf_counter

from evals.intelligence_g2.pr4.sensitive import sensitive_content
from evals.intelligence_v1.exceptions import ContractError

from .assets import request_payload
from .contracts import (
    AttemptTrace,
    CallBudget,
    CompletionResult,
    ExpressionAssessment,
    ExpressionResult,
    ExpressionSnapshot,
    ExpressionState,
    IntelligencePresentation,
    StepExecution,
    data,
    digest,
    fail,
    parse,
)
from .project import checked_input, namespace, project_request, request_digest
from .validate_output import validate_draft


@dataclass
class GenerationControl:
    """In-memory revocation token only; no Goal, DB or external action capability."""
    cancelled: bool = False
    valid: bool = True

    def require_current(self):
        if self.cancelled:
            raise asyncio.CancelledError()
        if not self.valid:
            fail("STALE_RESULT", "control", "request")


def identify(item, headline, body, style, order, selection):
    payload = dict(base_item_id=item.item_id, event_key=item.event_key,
        event_revision=item.event_revision, fact_revision=item.fact_revision,
        headline=headline, body=body, style_id=style, claim_order=order,
        selection=selection, schema_revision="g2-pr5-1")
    sha = digest(payload)
    return IntelligencePresentation(presentation_id="g2:expression:" + sha, content_revision=sha,
        base_item=item, **{k: v for k, v in payload.items() if k not in {"base_item_id", "schema_revision"}})


def rule_presentation(item):
    return identify(item, item.headline.text if item.headline else None,
        item.what_happened.text if item.what_happened else None, None, item.selected_claim_keys, "rule")


def observe(presentation, base_snapshot, prior):
    latest = {s.event_key: s for s in prior}
    parents = [latest[k].snapshot_id for k in sorted(latest) if k == base_snapshot.event_key]
    # Parent rule snapshots encode merges/splits. Link only actual matching predecessor observations.
    parents += [s.snapshot_id for s in prior if s.base_snapshot_id in base_snapshot.previous_snapshot_ids]
    parents = tuple(dict.fromkeys(parents))
    sha = digest(dict(presentation_id=presentation.presentation_id, as_of=base_snapshot.as_of.isoformat(),
                      base_snapshot_id=base_snapshot.snapshot_id))
    return ExpressionSnapshot(snapshot_id="g2:expression-snapshot:" + sha,
        presentation_id=presentation.presentation_id, base_snapshot_id=base_snapshot.snapshot_id,
        event_key=base_snapshot.event_key, as_of=base_snapshot.as_of,
        previous_snapshot_ids=parents, lineage_ids=base_snapshot.lineage_ids)


async def execute_step(*, expression_input, generator, config, assets, control=None):
    value, config = checked_input(expression_input, config, assets)
    control = control or GenerationControl()
    control.require_current()
    prior = value.previous_state
    requests = prior.requests_reserved if prior else 0
    request_bytes = prior.request_bytes_reserved if prior else 0
    response_bytes = prior.response_bytes_reserved if prior else 0
    step_calls = 0
    presentations, snapshots, assessments, drafts, traces = [], [], [], [], []
    views = {v.bundle.event_key: v for v in value.generation_input.events}
    base_snapshots = {s.event_key: s for s in value.rule_result.snapshots}
    for item in sorted(value.rule_result.items, key=lambda i: i.event_key):
        control.require_current()
        request = project_request(value, item, views[item.event_key], config, assets)
        result = rule_presentation(item)
        accepted, safe, completion = None, None, None
        failed_telemetry = {}
        code, status, called, size = None, "skipped", 0, 0
        start = perf_counter()
        if request and value.mode == "mock":
            size = len(request_payload(request, assets))
            if (size > config.max_request_bytes or step_calls >= config.max_requests_per_step
                    or requests >= config.max_requests_per_run
                    or request_bytes + size > config.max_request_bytes_per_run
                    or response_bytes + config.max_response_bytes > config.max_response_bytes_per_run):
                code = "BUDGET_EXCEEDED"
            else:
                requests += 1
                step_calls += 1
                request_bytes += size
                # Reserve the maximum response before starting; missing usage never releases budget.
                response_bytes += config.max_response_bytes
                called, status = 1, "fallback"
                loop = asyncio.get_running_loop()
                deadline = loop.time() + config.timeout_seconds
                try:
                    raw_completion = await asyncio.wait_for(generator.generate(request, budget=CallBudget()),
                                                            timeout=config.timeout_seconds)
                    control.require_current()
                    # wait_for can return after its timeout if the transport suppresses cancellation.
                    # Discard expired data before parsing it or accepting any expression/telemetry.
                    if loop.time() >= deadline:
                        raise TimeoutError
                    if request.request_sha256 != request_digest(request):
                        fail("STALE_RESULT", "control", "request_sha256")
                    completion = parse(CompletionResult, raw_completion, stage="adapter")
                    if (completion.response_bytes > config.max_response_bytes
                            or len(completion.content.encode("utf-8")) > config.max_response_bytes):
                        fail("OUTPUT_TOO_LARGE", "adapter", "response_bytes")
                    accepted, safe = validate_draft(completion, request, item, assets)
                    if accepted:
                        result = identify(item, accepted.headline, accepted.body, accepted.style_id,
                                          accepted.claim_order, "mock_closed")
                        status = "accepted"
                    else:
                        code = "EXPRESSION_NOT_CLOSED"
                except TimeoutError:
                    code = "TIMEOUT"
                except ContractError as error:
                    if error.code in {"CANCELLED", "STALE_RESULT"}:
                        raise
                    control.require_current()
                    if loop.time() >= deadline:
                        code, completion, failed_telemetry = "TIMEOUT", None, {}
                    else:
                        code = error.code if error.code in {
                            "CONFIGURATION", "NETWORK_DISABLED", "INVALID_ENVELOPE", "AUTHENTICATION",
                            "QUOTA", "RATE_LIMIT", "PROVIDER_HTTP", "CONNECTION", "OUTPUT_TOO_LARGE",
                            "OUTPUT_TRUNCATED", "CONTENT_FILTERED", "INVALID_JSON", "SCHEMA_INVALID",
                            "TOOL_CALL_FORBIDDEN", "CITATION_NOT_ALLOWED", "FUTURE_EVIDENCE",
                            "SPAN_MISMATCH", "NUMERIC_SCOPE_MISMATCH", "ATTRIBUTION_ESCALATION",
                            "EXPRESSION_NOT_CLOSED", "SENSITIVE_OUTPUT", "BUDGET_EXCEEDED"} else "SCHEMA_INVALID"
                        failed_telemetry = getattr(error, "safe_telemetry", {})
                except Exception:
                    # Raw injected adapter exceptions must not enter output or logs.
                    control.require_current()
                    if loop.time() >= deadline:
                        code, completion, failed_telemetry = "TIMEOUT", None, {}
                    else:
                        code = "INVALID_ENVELOPE"
        elif request is None and item.tier_candidate != "hold":
            code = "BUDGET_EXCEEDED"
        control.require_current()
        if safe:
            drafts.append(safe)
        presentations.append(result)
        snapshot = observe(result, base_snapshots[item.event_key], prior.snapshots if prior else ())
        snapshots.append(snapshot)
        locator = "passed" if accepted or safe or completion and code in {
            "NUMERIC_SCOPE_MISMATCH", "ATTRIBUTION_ESCALATION", "EXPRESSION_NOT_CLOSED", "BUDGET_EXCEEDED"} else "failed" if code in {
            "CITATION_NOT_ALLOWED", "FUTURE_EVIDENCE", "SPAN_MISMATCH"} else "not_evaluated"
        assessments.append(ExpressionAssessment(base_item_id=item.item_id, status=status, code=code,
            locator_status=locator, numeric_scope_status="passed" if accepted else
                "failed" if code == "NUMERIC_SCOPE_MISMATCH" else "not_evaluated",
            closed_render_status="passed" if accepted else "failed" if called else "not_evaluated"))
        usage = completion.usage if completion else failed_telemetry.get("usage")
        traces.append(AttemptTrace(request_sha256=request.request_sha256 if request else None,
            base_item_id=item.item_id, status=status, code=code, mock_calls=called,
            request_bytes=size if called else 0,
            response_bytes=completion.response_bytes if completion else failed_telemetry.get("response_bytes", 0),
            response_sha256=completion.response_sha256 if completion else failed_telemetry.get("response_sha256"),
            usage=usage, usage_origin="mock_fixture" if completion or usage else "unknown" if called else "not_called",
            usage_complete=bool(usage and "total_tokens" in usage), elapsed_ms=float((perf_counter() - start) * 1000)))
    state = ExpressionState(namespace=namespace(value, config), config_sha256=digest(config), mode=value.mode,
        cursor=value.rule_result.cursor, previous_state_sha256=digest(prior) if prior else None,
        requests_reserved=requests, request_bytes_reserved=request_bytes, response_bytes_reserved=response_bytes,
        snapshots=(prior.snapshots if prior else ()) + tuple(snapshots))
    result = ExpressionResult(cursor=value.rule_result.cursor, presentations=tuple(presentations),
        snapshots=tuple(snapshots), assessments=tuple(assessments), drafts=tuple(drafts), next_state=state,
        coverage_gaps=tuple(data(g) for g in value.generation_input.coverage_gaps))
    if sensitive_content(result):
        fail("SENSITIVE_OUTPUT", "output", "result")
    from .validate_output import validate_output
    validate_output(result, value, config, assets, tuple(traces))
    return StepExecution(result=result, traces=tuple(traces))


async def generate_expressions(*, expression_input, generator, config, assets):
    """Public domain result; the CLI uses execute_step for separate nonsemantic trace capture."""
    return (await execute_step(expression_input=expression_input, generator=generator,
                               config=config, assets=assets)).result
