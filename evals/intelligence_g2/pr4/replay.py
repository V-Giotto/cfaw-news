"""Offline PR4 prefix CLI. Zero network/model/database capabilities."""

import argparse
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

import pydantic

from evals.intelligence_g2.contracts import (
    PACKAGE,
    ROOT,
    ArtifactDigest,
    G2Error,
    json_bytes,
    read_json,
)
from evals.intelligence_g2.pr3.replay import current_sources as parent_sources
from evals.intelligence_g2.replay import output_location, safe_path, write_payloads
from evals.intelligence_v1.exceptions import ContractError
from evals.intelligence_v1.hashing import sha256_bytes

from .contracts import (
    Diagnostic,
    GenerationTrace,
    Issue,
    PR4Config,
    RunManifest,
    check_schemas,
    data,
    digest,
    fail,
    parse,
)
from .load_run import load_evidence_run
from .pipeline import generate_items
from .project import project_step

STREAMS = {"items": "items", "snapshots": "snapshots", "citations": "citations", "snapshot_states": "next_state"}


def current_sources():
    result = parent_sources()
    result.update({p.relative_to(ROOT).as_posix(): sha256_bytes(p.read_bytes()) for p in (PACKAGE / "pr4").glob("*.py")})
    return result


def run_sequence(inputs, evidence, *, config, evidence_config=None):
    prior, values, results = None, [], []
    for parent_input, parent in zip(inputs, evidence, strict=True):
        value = project_step(parent_input, parent, previous_state=prior, config=config, evidence_config=evidence_config)
        result = generate_items(generation_input=value, config=config)
        values.append(value)
        results.append(result)
        prior = result.next_state
    return tuple(values), tuple(results)


def projection_record(value):
    """Audit-only input export: no Persona, body archive or unnecessary claim quotes."""
    return dict(cursor=data(value.cursor), input_sha256=digest(value), namespace=value.namespace,
        config_sha256=value.config_sha256, previous_state_sha256=value.previous_state_sha256,
        events=[dict(event_key=v.bundle.event_key, event_revision=v.bundle.event_revision,
            bundle_id=v.bundle.bundle_id, bundle_sha256=v.bundle.bundle_sha256,
            current_claim_keys=v.bundle.current_claim_keys, historical_claim_keys=v.bundle.historical_claim_keys,
            source_pointers=[data(p) for p in v.source_pointers]) for v in value.events],
        coverage_gaps=[data(g) for g in value.coverage_gaps])


def run_replay(evidence_run, *, evidence_manifest_sha256, through_step, config_path, config_sha256, out):
    start = perf_counter()
    output = output_location(out)
    path = safe_path(config_path, areas=(PACKAGE / "manifests", ROOT / ".tmp"), code="MANIFEST_PATH_INVALID")
    raw = path.read_bytes()
    if sha256_bytes(raw) != config_sha256:
        fail("CONFIG_SHA_MISMATCH", "input", "config")
    config = parse(PR4Config, read_json(raw))
    if not check_schemas():
        fail("SCHEMA_INVALID", "input", "schema/v4")
    parent, inputs, evidence, evidence_config = load_evidence_run(evidence_run,
        manifest_sha256=evidence_manifest_sha256, through_step=through_step)
    values, results = run_sequence(inputs, evidence, config=config, evidence_config=evidence_config)
    payloads = {"config_snapshot.json": json_bytes(config),
        "input_projections.jsonl": b"".join(json_bytes(projection_record(v)) for v in values),
        "validation_report.json": json_bytes(dict(ok=True, steps=[data(r.validation) for r in results]))}
    for filename, field in STREAMS.items():
        payloads[filename + ".jsonl"] = b"".join(json_bytes({"cursor": data(r.cursor),
            field: data(getattr(r, field)) if field == "next_state" else [data(v) for v in getattr(r, field)]}) for r in results)
    git = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, timeout=10, check=True)
    manifest = RunManifest(parent_manifest_sha256=evidence_manifest_sha256,
        parent_run_path=Path(evidence_run).resolve().relative_to(ROOT).as_posix(), through_step=through_step,
        config_file_sha256=config_sha256, config_sha256=digest(config), git_sha=git.stdout.strip(),
        runtime_source_sha256=current_sources(), schema_sha256={p.relative_to(PACKAGE).as_posix(): sha256_bytes(p.read_bytes())
            for p in (PACKAGE / "schema/v4").glob("*.schema.json")}, dependency_lock_sha256=parent.dependency_lock_sha256,
        dependency_versions={"python": platform.python_version(), "pydantic": pydantic.__version__},
        selected_input_sha256=digest([digest(v) for v in values]),
        artifacts=tuple(ArtifactDigest(path=name, sha256=sha256_bytes(content), byte_count=len(content),
            record_count=len(content.splitlines()) if name.endswith(".jsonl") else None) for name, content in sorted(payloads.items())))
    payloads["run_manifest.json"] = json_bytes(manifest)
    payloads["trace.json"] = json_bytes(GenerationTrace(run_manifest_sha256=sha256_bytes(payloads["run_manifest.json"]),
        generated_at=datetime.now(timezone.utc), execution_ms=float((perf_counter() - start) * 1000)))
    write_payloads(output, payloads)
    return dict(ok=True, steps=len(results), run_manifest_sha256=sha256_bytes(payloads["run_manifest.json"]),
                trace_sha256=sha256_bytes(payloads["trace.json"]))


def print_error(error):
    issue = Issue(code=error.code, stage=getattr(error, "stage", "input"), field=error.field, record_id=error.record_id or None)
    print(json_bytes(Diagnostic(ok=False, counts={}, errors=(issue,))).decode().strip())


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-run", type=Path, required=True)
    parser.add_argument("--evidence-manifest-sha256", required=True)
    parser.add_argument("--through-step", required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--config-sha256", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = run_replay(args.evidence_run, evidence_manifest_sha256=args.evidence_manifest_sha256,
            through_step=args.through_step, config_path=args.config, config_sha256=args.config_sha256, out=args.out)
    except ContractError as error:
        print_error(error)
        return 1
    except (OSError, ValueError, KeyError, TypeError, RuntimeError, subprocess.SubprocessError):
        print_error(G2Error("EXPORT_IO_ERROR", stage="export", field="run"))
        return 1
    print(json_bytes(result).decode().strip())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
