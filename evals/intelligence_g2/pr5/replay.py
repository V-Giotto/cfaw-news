"""Pinned PR5 prefix CLI, with rule/mock only and no network or credential options."""

import argparse
import asyncio
import platform
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

import pydantic

from evals.intelligence_g2.contracts import PACKAGE, ROOT, ArtifactDigest, json_bytes
from evals.intelligence_g2.pr4.replay import current_sources as parent_sources
from evals.intelligence_g2.replay import output_location, write_payloads
from evals.intelligence_v1.exceptions import ContractError
from evals.intelligence_v1.hashing import sha256_bytes

from .adapter import MockCompletionAdapter
from .assets import asset_hashes, load_config
from .contracts import (
    ExpressionInput,
    ExpressionTrace,
    RunManifest,
    check_schemas,
    data,
    digest,
    fail,
)
from .load_run import load_rule_run
from .pipeline import GenerationControl, execute_step

STREAMS = {"presentations": "presentations", "expression_snapshots": "snapshots",
    "assessments": "assessments", "drafts": "drafts", "expression_states": "next_state"}


def current_sources():
    result = parent_sources()
    result.update({p.relative_to(ROOT).as_posix(): sha256_bytes(p.read_bytes())
                   for p in (PACKAGE / "pr5").glob("*.py")})
    return result


async def run_sequence(values, rules, *, rule_config, config, assets, mode="mock", generator=None, control=None):
    prior, executions, inputs = None, [], []
    generator = generator or MockCompletionAdapter(assets)
    for value, rule in zip(values, rules, strict=True):
        item = ExpressionInput(generation_input=value, rule_result=rule, rule_config=rule_config,
            mode=mode, config_sha256=digest(config), previous_state=prior,
            previous_state_sha256=digest(prior) if prior else None)
        execution = await execute_step(expression_input=item, generator=generator, config=config,
                                       assets=assets, control=control)
        inputs.append(item)
        executions.append(execution)
        prior = execution.result.next_state
    return tuple(inputs), tuple(executions)


def projection_record(value):
    # No raw Prompt, Persona, body archive, credentials or repeated evidence quotations.
    return dict(cursor=data(value.rule_result.cursor), input_sha256=digest(value),
        mode=value.mode, config_sha256=value.config_sha256,
        previous_state_sha256=value.previous_state_sha256,
        rule_item_ids=[i.item_id for i in value.rule_result.items])


def validation_report(inputs, executions):
    assessments = [a for e in executions for a in e.result.assessments]
    traces = [t for e in executions for t in e.traces]
    return dict(ok=True, semantic_truth="not_evaluated",
        model_attempts_ok=all(t.status == "accepted" for t in traces if t.mock_calls),
        degraded=any(a.status == "fallback" or a.code == "BUDGET_EXCEEDED" for a in assessments),
        counts=dict(attempts=sum(t.mock_calls for t in traces),
            accepted=sum(a.status == "accepted" for a in assessments),
            fallback=sum(a.status == "fallback" for a in assessments),
            skipped=sum(a.status == "skipped" for a in assessments)),
        steps=[dict(cursor=data(e.result.cursor), assessments=[data(a) for a in e.result.assessments],
            coverage_gaps=list(e.result.coverage_gaps), source_coverage=[data(w) for w in v.generation_input.source_coverage])
            for v, e in zip(inputs, executions, strict=True)])


def run_replay(rule_run, *, rule_manifest_sha256, through_step, config_path, config_sha256, out, mode="mock"):
    start = perf_counter()
    output = output_location(out)
    if mode not in {"rule", "mock"}:
        fail("NETWORK_DISABLED", "input", "mode")
    config, assets = load_config(config_path, config_sha256)
    if not check_schemas():
        fail("SCHEMA_INVALID", "input", "schema")
    parent, values, rules, rule_config = load_rule_run(rule_run,
        manifest_sha256=rule_manifest_sha256, through_step=through_step)
    source_hashes = current_sources()
    control = GenerationControl()
    inputs, executions = asyncio.run(run_sequence(values, rules, rule_config=rule_config,
        config=config, assets=assets, mode=mode, control=control))
    payloads = {"config_snapshot.json": json_bytes(config),
        "input_projections.jsonl": b"".join(json_bytes(projection_record(v)) for v in inputs),
        "validation_report.json": json_bytes(validation_report(inputs, executions))}
    for name, field in STREAMS.items():
        payloads[name + ".jsonl"] = b"".join(json_bytes(dict(cursor=data(e.result.cursor),
            **{field: data(getattr(e.result, field)) if field == "next_state" else [data(v) for v in getattr(e.result, field)]}))
            for e in executions)
    git = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, timeout=10, check=True)
    manifest = RunManifest(parent_run_path=Path(rule_run).resolve().relative_to(ROOT).as_posix(),
        parent_manifest_sha256=rule_manifest_sha256, through_step=through_step, mode=mode,
        config_file_sha256=config_sha256, config_sha256=digest(config), git_sha=git.stdout.strip(),
        runtime_source_sha256=source_hashes, schema_sha256={p.relative_to(PACKAGE).as_posix(): sha256_bytes(p.read_bytes())
            for p in (PACKAGE / "schema/v5").glob("*.schema.json")}, asset_sha256=asset_hashes(assets),
        dependency_lock_sha256=parent.dependency_lock_sha256,
        dependency_versions={"python": platform.python_version(), "pydantic": pydantic.__version__},
        selected_input_sha256=digest([digest(v) for v in inputs]),
        artifacts=tuple(ArtifactDigest(path=name, sha256=sha256_bytes(raw), byte_count=len(raw),
            record_count=len(raw.splitlines()) if name.endswith(".jsonl") else None) for name, raw in sorted(payloads.items())))
    payloads["run_manifest.json"] = json_bytes(manifest)
    traces = tuple(t for e in executions for t in e.traces)
    payloads["trace.json"] = json_bytes(ExpressionTrace(run_manifest_sha256=sha256_bytes(payloads["run_manifest.json"]),
        generated_at=datetime.now(timezone.utc), elapsed_ms=float((perf_counter() - start) * 1000),
        attempts=traces, mock_calls=sum(t.mock_calls for t in traces)))
    # Reject parent/code changes after awaiting a completion, before atomic publication.
    control.require_current()
    load_config(config_path, config_sha256)
    if current_sources() != source_hashes:
        fail("STALE_RESULT", "control", "runtime_source_sha256")
    checked, _, _, _ = load_rule_run(rule_run, manifest_sha256=rule_manifest_sha256, through_step=through_step)
    if checked != parent:
        fail("STALE_RESULT", "control", "parent_manifest")
    write_payloads(output, payloads)
    return dict(ok=True, steps=len(executions), mode=mode,
        mock_calls=sum(t.mock_calls for t in traces), model_calls=0, external_requests=0,
        fallback_count=sum(a.status == "fallback" for e in executions for a in e.result.assessments),
        model_attempts_ok=all(t.status == "accepted" for t in traces if t.mock_calls),
        degraded=any(a.status == "fallback" or a.code == "BUDGET_EXCEEDED" for e in executions for a in e.result.assessments),
        run_manifest_sha256=sha256_bytes(payloads["run_manifest.json"]), trace_sha256=sha256_bytes(payloads["trace.json"]))


def print_error(error):
    # Even schema paths and record IDs can contain attacker-provided keys; use fixed public fields.
    fields = {"available_at", "as_of", "config", "schema", "mode", "rule_manifest", "path", "out",
              "runtime_source_sha256", "parent_manifest", "through_step", "config_sha256",
              "parent_artifact", "approved_request", "response_bytes", "request_bytes", "request_sha256",
              "style_order", "refs", "numeric_scope", "attribution", "closed_render", "snapshot.as_of",
              "previous_state", "immutable_base", "rule_fallback", "state", "partition", "drafts", "trace",
              "presentation", "mock_manifest", "mock_responses", "asset_sha256", "envelope", "http_status",
              "content", "finish_reason", "json", "rule_result", "selection", "cursor", "cursor_projection",
              "parent_schema", "parent_config", "parent_locks", "parent_runtime_source_sha256", "source_coverage"}
    rename = re.fullmatch(r"publish\.rename:attempts=\d+:errno=(?:\d+|None):winerror=(?:\d+|None)", error.field)
    field = error.field if error.field in fields or rename else "validation"
    stage = getattr(error, "stage", "input")
    if stage not in {"input", "temporal", "history", "adapter", "expression", "budget", "control", "output", "export", "evaluation"}:
        stage = "input"
    print(json_bytes(dict(ok=False, errors=[dict(code=error.code, stage=stage, field=field,
        record_id=digest(error.record_id) if error.record_id else None)])).decode().strip())


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rule-run", type=Path, required=True)
    parser.add_argument("--rule-manifest-sha256", required=True)
    parser.add_argument("--through-step", required=True)
    parser.add_argument("--mode", choices=("rule", "mock"), default="mock")
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--config-sha256", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = run_replay(args.rule_run, rule_manifest_sha256=args.rule_manifest_sha256,
            through_step=args.through_step, mode=args.mode, config_path=args.config,
            config_sha256=args.config_sha256, out=args.out)
    except ContractError as error:
        print_error(error)
        return 1
    except (asyncio.CancelledError, KeyboardInterrupt):
        from evals.intelligence_g2.contracts import G2Error
        print_error(G2Error("CANCELLED", stage="control", field="request"))
        return 1
    except (OSError, ValueError, KeyError, TypeError, RuntimeError, subprocess.SubprocessError):
        from evals.intelligence_g2.contracts import G2Error
        print_error(G2Error("EXPORT_IO_ERROR", stage="export", field="run"))
        return 1
    print(json_bytes(result).decode().strip())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
