"""Pinned single-step offline G2 replay. No network, providers or production database."""

import argparse
import logging
import platform
import re
import stat
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter, sleep

import pydantic
import pydantic_core

from evals.intelligence_v1.exceptions import ContractError
from evals.intelligence_v1.hashing import canonical_json, sha256_bytes

from .bridge import load_replay_input
from .contracts import (
    PACKAGE,
    ROOT,
    ArtifactDigest,
    DiagnosticReport,
    G2Config,
    G2Error,
    GenerationTrace,
    RunManifest,
    ValidationIssue,
    check_schemas,
    data,
    digest,
    json_bytes,
    parse,
    read_json,
)
from .pipeline import run_g2_offline

OUTPUT_BASE = ROOT / ".tmp/evals/g2"
FORBIDDEN = {".local", ".git", "dev-diaries"}
PUBLISH_RETRY_DELAYS = (0.05, 0.1, 0.2, 0.4, 0.8)
LOGGER = logging.getLogger(__name__)


def safe_path(value, *, areas, code="OUTPUT_PATH_INVALID"):
    """Check lexical components before filesystem resolution, including Windows reparse points."""
    path = Path(value).absolute()
    if any(p in {".", ".."} or p.casefold() in FORBIDDEN or p.casefold().startswith(".env")
           or p.endswith((".", " ")) or ":" in p
           or p.casefold().endswith((".db", ".db-wal", ".db-shm"))
           for p in path.parts[1:]):
        raise G2Error(code, stage="export", field="path")
    if not any(path.is_relative_to(area) and path != area for area in areas):
        raise G2Error(code, stage="export", field="path")
    if code == "MANIFEST_PATH_INVALID" and any(p.casefold() in {
            "labels", "events", "claims", "annotations", "adjudications"} for p in path.parts):
        raise G2Error("PREDICTION_PATH_INVALID", stage="export", field="path")
    # Do not follow a junction into another directory before rejecting it.
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current /= part
        try:
            info = current.lstat()
        except FileNotFoundError:
            continue
        if (stat.S_ISLNK(info.st_mode)
                or getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT):
            raise G2Error(code, stage="export", field="path")
    resolved = path.resolve()
    if not any(resolved.is_relative_to(area) and resolved != area for area in areas):
        raise G2Error(code, stage="export", field="path")
    return resolved


def output_location(value):
    path = safe_path(value, areas=(OUTPUT_BASE,))
    if path.exists():
        raise G2Error("OUTPUT_EXISTS", stage="export", field="out")
    return path


def load_config(path, pin):
    path = safe_path(path, areas=(PACKAGE / "manifests", ROOT / ".tmp"),
                     code="MANIFEST_PATH_INVALID")
    if not isinstance(pin, str) or re.fullmatch(r"[0-9a-f]{64}", pin) is None:
        raise G2Error("CONFIG_SHA_MISMATCH", field="config")
    raw = path.read_bytes()
    if sha256_bytes(raw) != pin:
        raise G2Error("CONFIG_SHA_MISMATCH", field="config")
    return parse(G2Config, read_json(raw)), sha256_bytes(raw)


def io_diagnostic(operation, error, attempts):
    """Only numeric OS status, never exception text, filenames or payloads."""
    number = error.errno if isinstance(error.errno, int) else None
    native = getattr(error, "winerror", None)
    native = native if isinstance(native, int) else None
    return f"{operation}:attempts={attempts}:errno={number}:winerror={native}"


def publish_staging(staging, output):
    """Retry short Windows sharing/access denials, never replace or copy a destination."""
    for attempt in range(1, len(PUBLISH_RETRY_DELAYS) + 2):
        # A competing writer or changed ancestor must abort even after a retryable denial.
        output_location(output)
        safe_path(staging, areas=(OUTPUT_BASE,))
        try:
            staging.rename(output)
            return
        except OSError as error:
            field = io_diagnostic("publish.rename", error, attempt)
            retryable = getattr(error, "winerror", None) in {5, 32, 33}
            if not retryable or attempt > len(PUBLISH_RETRY_DELAYS):
                raise G2Error("EXPORT_IO_ERROR", stage="export", field=field) from None
            LOGGER.warning("G2 export retry %s", field)
            sleep(PUBLISH_RETRY_DELAYS[attempt - 1])


def write_payloads(output, payloads):
    """Flat, private staging directory; an error cannot publish a partial result directory."""
    output = output_location(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    # Recheck existing ancestors after mkdir, before creating staging or writing files.
    output_location(output)
    staging = Path(tempfile.mkdtemp(prefix="." + output.name + ".staging-", dir=output.parent))
    try:
        for name, raw in sorted(payloads.items()):
            if Path(name).name != name:
                raise G2Error("OUTPUT_PATH_INVALID", stage="export", field="artifact.path")
            with (staging / name).open("xb") as stream:
                stream.write(raw)
        publish_staging(staging, output)
    except BaseException:
        # Only unlink known flat artifacts inside our freshly created directory; no recursive rm.
        if staging.exists() and staging.resolve().is_relative_to(OUTPUT_BASE.resolve()):
            for name in payloads:
                target = staging / name
                if Path(name).name == name and target.is_file():
                    target.unlink()
            staging.rmdir()
        raise


def run_replay(manifest_path, *, manifest_sha256, timeline_id, step_id,
               config_path, config_sha256, out):
    started = perf_counter()
    output = output_location(out)
    manifest_path = safe_path(manifest_path, areas=(ROOT / "evals/intelligence_v1", ROOT / ".tmp"),
                              code="MANIFEST_PATH_INVALID")
    config, config_file_sha = load_config(config_path, config_sha256)
    if not check_schemas():
        raise G2Error("SCHEMA_INVALID", field="schema/v1")
    value, metadata = load_replay_input(manifest_path, manifest_sha256=manifest_sha256,
        timeline_id=timeline_id, step_id=step_id, config=config)
    result = run_g2_offline(replay_input=value, config=config)
    payloads = {"input_snapshot.json": json_bytes(value), "config_snapshot.json": json_bytes(config),
                "result.json": json_bytes(result),
                "validation_report.json": json_bytes(result.validation)}
    counts = {name: None for name in payloads}
    for name in ("events", "relations", "bundles", "items"):
        rows = getattr(result, name)
        payloads[name + ".jsonl"] = b"".join(json_bytes(row) for row in rows)
        counts[name + ".jsonl"] = len(rows)
    git = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                         text=True, timeout=10)
    if git.returncode:
        raise G2Error("EXPORT_IO_ERROR", stage="export", field="git_sha")
    sources = dict(metadata["runtime_source_sha256"])
    sources.update({p.relative_to(ROOT).as_posix(): sha256_bytes(p.read_bytes())
                    for p in PACKAGE.glob("*.py")})
    schema_hashes = {p.relative_to(PACKAGE).as_posix(): sha256_bytes(p.read_bytes())
                     for p in (PACKAGE / "schema/v1").glob("*.schema.json")}
    manifest = RunManifest(run_id=result.run_id, dataset_id=value.dataset_id,
        dataset_revision=value.dataset_revision, g1_schema_revision=metadata["g1_schema_revision"],
        input_manifest_sha256=value.input_manifest_sha256,
        config_file_sha256=config_file_sha, config_sha256=digest(config), git_sha=git.stdout.strip(),
        runtime_source_sha256=sources, schema_sha256=schema_hashes,
        dependency_lock_sha256={name: sha256_bytes((ROOT / name).read_bytes()) for name in
                                ("requirements.lock", "frontend/package-lock.json")},
        python_version=platform.python_version(), dependency_versions={
            "pydantic": pydantic.__version__, "pydantic_core": pydantic_core.__version__},
        input_sha256=result.input_sha256, context_sha256=digest(value.context),
        candidate_sha256=digest([data(d.candidate) for d in value.visible_documents]),
        source_coverage_digest=value.source_coverage_digest,
        artifacts=tuple(ArtifactDigest(path=name, sha256=sha256_bytes(raw), byte_count=len(raw),
                                      record_count=counts[name])
                        for name, raw in sorted(payloads.items())))
    payloads["run_manifest.json"] = json_bytes(manifest)
    trace = GenerationTrace(run_id=result.run_id, input_sha256=result.input_sha256,
        run_manifest_sha256=sha256_bytes(payloads["run_manifest.json"]),
        generated_at=datetime.now(timezone.utc), execution_ms=float((perf_counter() - started) * 1000),
        stage_revisions={"pipeline": config.pipeline_revision, "identity": config.identity_revision,
                         "claim": config.claim_strategy, "generator": config.generator_revision},
        validation_ok=result.validation.ok)
    payloads["trace.json"] = json_bytes(trace)
    write_payloads(output, payloads)
    return {"ok": True, "run_id": result.run_id, "counts": result.validation.counts,
            "run_manifest_sha256": sha256_bytes(payloads["run_manifest.json"]),
            "trace_sha256": sha256_bytes(payloads["trace.json"])}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--manifest-sha256", required=True)
    parser.add_argument("--timeline", required=True)
    parser.add_argument("--step", required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--config-sha256", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = run_replay(args.manifest, manifest_sha256=args.manifest_sha256,
            timeline_id=args.timeline, step_id=args.step, config_path=args.config,
            config_sha256=args.config_sha256, out=args.out)
    except ContractError as error:
        # G1's codes are preserved; neither evidence nor exception input is printed.
        issue = ValidationIssue(code=error.code, stage=getattr(error, "stage", "bridge"),
            field=error.field, record_id=error.record_id or None)
        print(canonical_json(data(DiagnosticReport(ok=False, counts={}, errors=(issue,)))))
        return 1
    except (OSError, ValueError, TypeError, KeyError, RuntimeError, subprocess.SubprocessError):
        issue = ValidationIssue(code="EXPORT_IO_ERROR", stage="export")
        print(canonical_json(data(DiagnosticReport(ok=False, counts={}, errors=(issue,)))))
        return 1
    print(canonical_json(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
