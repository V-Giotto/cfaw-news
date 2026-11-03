"""Independent review regressions; authored engineering inputs, no live news."""

import inspect
import json
import os
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest
from cfaw_news.intelligence import g2_adapter
from cfaw_news.intelligence.contracts import SourcePolicy, instant
from cfaw_news.intelligence.runtime import Control, run
from cfaw_news.intelligence.runtime_contracts import RuntimeConfig, RuntimePlan, RuntimeResult

from evals.intelligence_g2.contracts import json_bytes

from .runtime_support import NOW, envelope, source, version, wire


def chain():
    value = envelope()
    first = version(source(), body="Atlas Tool releases local agent tooling with latency <= 10 ms.")
    second = version(source(), previous=first, observed=instant("2026-01-02T01:00:00Z"),
                     body="Atlas Tool releases local agent tooling with latency > 10 ms.")
    value["versions"] = [d.model_dump(mode="json") for d in (first, second)]
    return value


def test_rss_excerpt_permission_never_changes_material_type():
    value = envelope("real")
    from cfaw_news.intelligence.runtime_contracts import RuntimeEnvelope
    parsed = RuntimeEnvelope.model_validate_json(json_bytes(value))
    assert g2_adapter.native_doc(parsed.versions[0], parsed).content_kind == "feed_summary"
    raw, pin = wire(value)
    result = run(raw, expected_sha256=pin)
    assert result.state == "raw_news_only" and result.plan is None and result.ranking is None
    assert result.reason_codes == ("G4_NATIVE_G2_REJECTED:RIGHTS_USE_NOT_ALLOWED",)
    assert not result.stages and result.input.versions[0].content_kind == "feed_summary"


def test_permitted_rss_stays_secondary_unverified():
    value = envelope("real")
    policy = SourcePolicy.model_validate_json(json_bytes({**source("real", "permitted").model_dump(mode="json"),
        "allowed_use": ["metadata", "excerpt", "fulltext"]}))
    value["sources"] = [policy.model_dump(mode="json")]
    value["versions"] = [version(policy).model_dump(mode="json")]
    raw, pin = wire(value)
    result = run(raw, expected_sha256=pin)
    assert result.stages[-1].replay_input.visible_documents[0].candidate.content_kind == "feed_summary"
    assert result.stages[-1].evidence.claims
    assert all(c.attribution.attribution_kind == "secondary_material" and c.claim_type == "other"
               for c in result.stages[-1].evidence.claims)
    assert all(a.verification_state == "unverified" for a in result.stages[-1].evidence.assessments)
    assert all("primary_text_unavailable" in c.limitations for c in result.stages[-1].evidence.claims)
    assert any(g.code == "primary_text_unavailable" for g in result.stages[-1].evidence.validation.coverage_gaps)


def test_persona_before_first_document_keeps_birth_anchor_and_claim_archive():
    value = chain()
    raw, pin = wire(value)
    before = run(raw, expected_sha256=pin)
    value["persona"]["persona"].update(persona_version_id="local:v2", available_at=NOW)
    raw, pin = wire(value)
    after = run(raw, expected_sha256=pin)
    assert before.archive_snapshot_ids == after.archive_snapshot_ids
    assert before.stages[-1].grouping.next_state == after.stages[-1].grouping.next_state or (
        before.stages[-1].grouping.events == after.stages[-1].grouping.events)
    assert len(before.stages[-1].evidence.next_state.claims) == len(after.stages[-1].evidence.next_state.claims) == 2
    assert before.stages[0].replay_input.visible_documents[0].candidate.doc_version_id == value["versions"][0]["doc_version_id"]


@pytest.mark.parametrize("available", ["2026-01-02T00:30:00Z", "2026-01-02T02:00:00Z"])
def test_missing_historical_persona_blocks_continuity_without_new_identity(available):
    value = chain()
    value["persona"]["persona"].update(persona_version_id="local:v2", available_at=available)
    raw, pin = wire(value)
    result = run(raw, expected_sha256=pin)
    assert result.state == "evidence_not_ready"
    assert result.reason_codes == ("G4_RUNTIME_PERSONA_HISTORY_REQUIRED",)
    assert result.context is None and result.ranking is None and result.plan is None
    assert not result.stages and not result.archive_snapshot_ids
    assert len(result.input.versions) == 2 and not result.publishable
    with pytest.raises(ValueError, match="PERSONA_HISTORY_REQUIRED"):
        g2_adapter.run_native(result.input, pin, lambda _: None)


def target_frame(target):
    frames = inspect.stack()
    model_names = {type(f.frame.f_locals.get("self")).__name__ for f in frames
                   if f.function in {"bound", "replay"}}
    if target == "result_model":
        return "RuntimeResult" in model_names
    if target == "plan_model":
        return "RuntimePlan" in model_names and "RuntimeResult" not in model_names
    is_budget = any(f.function == "plan_fields" for f in frames)
    is_context = any(f.function == "validate_context" for f in frames)
    return is_context and not model_names & {"RuntimePlan", "RuntimeResult"} and (
        is_budget if target == "budget" else not is_budget)


@pytest.mark.parametrize("target", ["ranking", "budget", "plan_model", "result_model"])
@pytest.mark.parametrize("kind", ["cancel", "timeout"])
def test_all_internal_validation_replays_stop_before_next_stage(monkeypatch, target, kind):
    state = dict(armed=False, groups_after_trigger=0)
    control = Control(cancelled=lambda: kind == "cancel" and state["armed"], timeout_seconds=1,
                      clock=lambda: 2 if kind == "timeout" and state["armed"] else 0)
    native, grouping = g2_adapter.run_native, g2_adapter.run_grouping_step
    def intercepted(*args, **kwargs):
        if not state["armed"] and target_frame(target):
            state["armed"] = True
        return native(*args, **kwargs)
    def counted(*args, **kwargs):
        state["groups_after_trigger"] += int(state["armed"])
        return grouping(*args, **kwargs)
    monkeypatch.setattr(g2_adapter, "run_native", intercepted)
    monkeypatch.setattr(g2_adapter, "run_grouping_step", counted)
    raw, pin = wire(chain())
    with pytest.raises(ValueError, match="CANCELLED" if kind == "cancel" else "TIMEOUT"):
        run(raw, expected_sha256=pin, control=control)
    assert state["armed"] and state["groups_after_trigger"] == 0


@pytest.mark.parametrize("model", [RuntimePlan, RuntimeResult])
def test_direct_model_json_validation_accepts_request_control(model):
    raw, pin = wire(envelope())
    result = run(raw, expected_sha256=pin)
    payload = result.plan.model_dump_json() if model is RuntimePlan else result.model_dump_json()
    with pytest.raises(ValueError, match="CANCELLED"):
        model.model_validate_json(payload, context={"control": Control(cancelled=lambda: True)})


def test_pre_review_config_pin_cannot_be_reused():
    old = json.loads((Path(__file__).resolve().parents[3] / "audit/g4/pr3/BASELINE.json").read_bytes())
    with pytest.raises(ValueError, match="CONFIG_PIN_MISMATCH"):
        RuntimeConfig.model_validate_json(json_bytes(deepcopy(old["development_config"]["value"])))


@pytest.mark.parametrize("kind", ["cancel", "timeout"])
def test_request_control_scope_does_not_leak_after_failure(kind):
    raw, pin = wire(envelope())
    failed = Control(cancelled=lambda: kind == "cancel")
    if kind == "timeout":
        failed.deadline = -1
    with pytest.raises(ValueError, match="CANCELLED|TIMEOUT"):
        run(raw, expected_sha256=pin, control=failed)
    assert run(raw, expected_sha256=pin).state == "plan_ready"


@pytest.mark.parametrize("kind", ["cancel", "timeout"])
def test_cancel_after_native_input_validation_never_starts_grouping(monkeypatch, kind):
    state = dict(stopped=False, groups=0)
    control = Control(cancelled=lambda: kind == "cancel" and state["stopped"], timeout_seconds=1,
                      clock=lambda: 2 if kind == "timeout" and state["stopped"] else 0)
    checked, grouping = g2_adapter.checked_input, g2_adapter.run_grouping_step
    def stop_after_input(*args, **kwargs):
        result = checked(*args, **kwargs)
        state["stopped"] = True
        return result
    def counted(*args, **kwargs):
        state["groups"] += 1
        return grouping(*args, **kwargs)
    monkeypatch.setattr(g2_adapter, "checked_input", stop_after_input)
    monkeypatch.setattr(g2_adapter, "run_grouping_step", counted)
    raw, pin = wire(envelope())
    with pytest.raises(ValueError, match="CANCELLED|TIMEOUT"):
        run(raw, expected_sha256=pin, control=control)
    assert state["stopped"] and state["groups"] == 0


@pytest.mark.parametrize("case", ["excerpt", "late-persona"])
def test_cli_downgrade_has_explicit_reason_and_no_promoted_result(tmp_path, case):
    value = envelope("real") if case == "excerpt" else chain()
    if case == "late-persona":
        value["persona"]["persona"].update(persona_version_id="local:v2", available_at="2026-01-02T02:00:00Z")
    raw, pin = wire(value)
    path, output = tmp_path / "input.json", tmp_path / "output"
    path.write_bytes(raw)
    process = subprocess.run([sys.executable, "-B", "-m", "cfaw_news.intelligence.runtime",
        "--input", str(path), "--input-pin", pin, "--out", str(output)],
        capture_output=True, text=True, env={**os.environ}, timeout=60)
    assert process.returncode == 0, process.stderr
    result = json.loads((output / "result.json").read_bytes())
    assert result["reason_codes"] == (["G4_NATIVE_G2_REJECTED:RIGHTS_USE_NOT_ALLOWED"] if case == "excerpt"
                                      else ["G4_RUNTIME_PERSONA_HISTORY_REQUIRED"])
    assert result["context"] is None and result["ranking"] is None and result["plan"] is None
    assert result["stages"] == [] and result["publishable"] is False
