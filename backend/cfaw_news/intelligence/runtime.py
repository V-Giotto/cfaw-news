"""Controlled local runtime, read-only ledger export and replayable stage output."""
# ruff: noqa: E402

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from pydantic import ValidationError
from sqlalchemy import select

from .native import verify

verify()

from evals.intelligence_g2.contracts import data, digest, json_bytes, read_json
from evals.intelligence_g3.budget import STATUSES, _source_coverage
from evals.intelligence_g3.budget_contracts import CoverageDiagnostics
from evals.intelligence_v1.exceptions import ContractError
from evals.intelligence_v1.hashing import sha256_bytes

from .contracts import LedgerError
from .runtime_contracts import (
    RuntimeBudgetInput,
    RuntimeEnvelope,
    RuntimeHistoryInput,
    RuntimePlan,
    RuntimeResult,
)
from .runtime_control import Control, control_scope, controlled, current


def coverage(value, root="/input/coverage"):
    from collections import Counter

    from evals.intelligence_v1.contracts import CoverageWindow
    windows = tuple(CoverageWindow(**{k: getattr(w, k) for k in (
        "coverage_window_id", "source_id", "start_at", "end_at", "observed_at", "status")},
        reason=w.reason_code) for w in value.coverage)
    def rebase(node):
        if isinstance(node, str):
            return node.replace("/history_input/replay/source_coverage", root)
        if isinstance(node, dict):
            return {k: rebase(v) for k, v in node.items()}
        if isinstance(node, tuple):
            return tuple(rebase(v) for v in node)
        if isinstance(node, list):
            return [rebase(v) for v in node]
        return node
    sources = tuple(rebase(_source_coverage(s, tuple(enumerate(windows)), value.time_window_start,
        value.time_window_end)) for s in sorted({p.source_id for p in value.sources}))
    counts = Counter(w.status for w in windows)
    return CoverageDiagnostics(requested_start_at=value.time_window_start,
        requested_end_at=value.time_window_end, windows=windows,
        status_counts={s: counts[s] for s in STATUSES}, source_count=len(sources),
        window_count=len(windows),
        missing_source_ids=tuple(s["source_id"] for s in sources if not s["window_refs"]),
        unobserved_source_ids=tuple(s["source_id"] for s in sources if not s["window_refs"]),
        sources=sources, effective_statuses=tuple(sorted({s["status"] for s in sources})) or ("unknown",),
        has_gap=not sources or any(s["status"] != "covered" for s in sources))


@controlled
def derive(value, input_pin):
    from .g2_adapter import require_persona_prefix, run_native
    from .g3_adapter import plan_fields, plan_reasons, rank_runtime, replay_fields
    if sha256_bytes(json_bytes(value)) != input_pin:
        raise LedgerError("G4_RUNTIME_INPUT_PIN_MISMATCH")
    checkpoint = current().check
    result = dict(input_sha256=input_pin, state="raw_news_only", reason_codes=[], stages=[], projections=[],
        context=None, ranking=None, plan=None, coverage=data(coverage(value)), archive_snapshot_ids=[],
        publishable=False, semantic_truth="not_evaluated")
    if len({p.source_id for p in value.sources}) != len(value.sources):
        result["reason_codes"] = ["G4_RUNTIME_POLICY_TRANSITION_UNSUPPORTED"]
        return result
    try:
        require_persona_prefix(value)
    except LedgerError as error:
        if error.code != "G4_RUNTIME_PERSONA_HISTORY_REQUIRED":
            raise
        result.update(state="evidence_not_ready", reason_codes=[error.code])
        return result
    try:
        stages, observations, identities, projections = run_native(value, input_pin, checkpoint)
    except ContractError as error:
        result["reason_codes"] = ["G4_NATIVE_G2_REJECTED:" + error.code]
        return result
    result.update(stages=[data(s) for s in stages], projections=[data(p) for p in projections],
                  archive_snapshot_ids=[c.snapshot.snapshot_id for c in observations[-1].candidates])
    context = RuntimeHistoryInput(envelope=value,
        replay=replay_fields(value, stages, observations, identities))
    checkpoint("ranking")
    ranking = rank_runtime(context)
    result.update(context=data(context), ranking=data(ranking))
    # Frozen native G2 explicitly has no independent-support implementation. Never promote
    # these real, uncertain sources to a Focus/Radar recommendation as a side effect of scoring.
    doubts = plan_reasons(value, stages[-1].evidence)
    if doubts:
        result["reason_codes"] = doubts
        return result
    checkpoint("budget")
    budget_input = RuntimeBudgetInput(history_input=context, ranking=ranking, config=value.config.budget)
    plan = RuntimePlan.model_validate_json(json_bytes(dict(input=data(budget_input), **plan_fields(budget_input))))
    result.update(plan=data(plan), state="plan_ready" if plan.display_order else "evidence_not_ready",
        reason_codes=["G4_RUNTIME_CALCULATED_NOT_PUBLISHED" if plan.display_order else
                      "G4_RUNTIME_NO_ELIGIBLE_BUDGET_FIT"])
    checkpoint("complete")
    return result


def run(raw, *, expected_sha256, control=None):
    with control_scope(control) as active:
        return _run(raw, expected_sha256=expected_sha256, control=active)


def _run(raw, *, expected_sha256, control):
    verify()
    control.check("input")
    if not isinstance(raw, bytes) or len(raw) > 4_000_000:
        raise LedgerError("G4_RUNTIME_RESOURCE_LIMIT")
    if sha256_bytes(raw) != expected_sha256:
        raise LedgerError("G4_RUNTIME_INPUT_PIN_MISMATCH")
    value = RuntimeEnvelope.model_validate_json(json_bytes(read_json(raw)))
    if raw != json_bytes(value):
        raise LedgerError("G4_RUNTIME_CANONICAL_REQUIRED")
    if value.as_of > datetime.now(timezone.utc):
        raise LedgerError("G4_RUNTIME_FUTURE_INPUT")
    fields = derive(value, expected_sha256)
    control.check("serialization_validation")
    result = RuntimeResult.model_validate_json(json_bytes(dict(input=data(value), **fields)),
                                               context={"control": control})
    control.check("return")
    return result


def from_ledger(session, *, stream_id, as_of, time_window_start, persona, config,
                record_origin="real", synthetic_provenance_uri=None):
    """Read only. Select a complete captured as-of prefix; never query Article/Reading."""
    from .contracts import CoverageWindow, SourcePolicy
    from .contracts import digest as ledger_digest
    from .document_store import enabled, read_version
    from .models import G4Coverage, G4SourcePolicy, G4Version
    if as_of.tzinfo is None or time_window_start.tzinfo is None:
        raise LedgerError("G4_RUNTIME_INTERVAL_INVALID")
    connection = session.connection()
    if not connection.connection.driver_connection.in_transaction:
        connection.exec_driver_sql("BEGIN")
    if not enabled(session):
        raise LedgerError("G4_RUNTIME_LEDGER_NOT_MIGRATED")
    cutoff = as_of.astimezone(timezone.utc).isoformat(timespec="microseconds")
    versions = tuple(read_version(row) for row in session.scalars(select(G4Version).where(
        G4Version.available_at <= cutoff).order_by(G4Version.available_at, G4Version.document_id)))
    sources, windows = [], []
    for row in session.scalars(select(G4SourcePolicy).where(G4SourcePolicy.registered_at <= cutoff)):
        policy = SourcePolicy.model_validate_json(json_bytes(row.data))
        if row.policy_sha256 != ledger_digest(row.data) or row.source_id != policy.source_id:
            raise LedgerError("G4_RUNTIME_LEDGER_POLICY_MISMATCH")
        sources.append(policy)
    for row in session.scalars(select(G4Coverage).where(
            G4Coverage.observed_at <= cutoff).order_by(G4Coverage.observed_at)):
        window = CoverageWindow.model_validate_json(json_bytes(row.data))
        fields = ("source_id", "start_at", "end_at", "observed_at", "status")
        payload = window.model_dump(mode="json", exclude={"coverage_window_id", "schema_revision", "scope"})
        if (any(getattr(row, name) != getattr(window, name) for name in fields)
                or row.coverage_window_id != window.coverage_window_id
                or window.coverage_window_id != "g4cov:" + ledger_digest([payload, row.capture_id])):
            raise LedgerError("G4_RUNTIME_LEDGER_COVERAGE_MISMATCH")
        windows.append(window)
    return RuntimeEnvelope.model_validate_json(json_bytes(dict(record_origin=record_origin, stream_id=stream_id,
        as_of=as_of.isoformat(), time_window_start=time_window_start.isoformat(),
        time_window_end=as_of.isoformat(), persona=data(persona),
        versions=[v.model_dump(mode="json") for v in versions],
        sources=[s.model_dump(mode="json") for s in sources],
        coverage=[w.model_dump(mode="json") for w in windows], config=data(config),
        synthetic_provenance_uri=synthetic_provenance_uri)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--input-pin", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    control = Control()
    try:
        if args.out.exists():
            raise LedgerError("G4_RUNTIME_OUTPUT_EXISTS")
        if args.input.stat().st_size > 4_000_000:
            raise LedgerError("G4_RUNTIME_RESOURCE_LIMIT")
        raw = args.input.read_bytes()
        result = run(raw, expected_sha256=args.input_pin, control=control)
        payloads = {"input.json": raw, "result.json": json_bytes(result),
                    "stage_log.json": json_bytes(control.log)}
        payloads.update({f"stages/{i}.json": json_bytes(s) for i, s in enumerate(result.stages)})
        manifest = dict(revision="g4-pr3-runtime-artifacts-v1", input_sha256=args.input_pin,
                        files={p: sha256_bytes(b) for p, b in payloads.items()},
                        network_calls=0, model_calls=0, publishable=False)
        args.out.mkdir(parents=True, exist_ok=False)
        for name, content in {**payloads, "manifest.json": json_bytes(manifest)}.items():
            target = args.out / name
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("xb") as stream:
                stream.write(content)
        print(json.dumps(dict(ok=True, state=result.state, output_pin=digest(manifest))))
        return 0
    except (ValueError, OSError) as error:
        code = getattr(error, "code", "G4_RUNTIME_REJECTED")
        if isinstance(error, ValidationError):
            codes = sorted({getattr(e.get("ctx", {}).get("error"), "code", "G4_RUNTIME_SCHEMA_INVALID")
                            for e in error.errors(include_input=False)})
            code = codes[0] if len(codes) == 1 else "G4_RUNTIME_SCHEMA_INVALID"
        print(json.dumps(dict(ok=False, code=code,
                              completed_stages=control.log)))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
