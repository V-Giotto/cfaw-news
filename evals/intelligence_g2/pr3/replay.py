"""Pinned offline prefix replay. This module has no reference or model imports."""

import argparse
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

import pydantic

from evals.intelligence_g2.contracts import PACKAGE, ROOT, ArtifactDigest, json_bytes, read_json
from evals.intelligence_g2.pr2.replay import current_source_hashes as parent_sources
from evals.intelligence_g2.replay import output_location, safe_path, write_payloads
from evals.intelligence_v1.exceptions import ContractError
from evals.intelligence_v1.hashing import sha256_bytes

from .contracts import (
    EvidenceInput,
    PR3Config,
    PR3Diagnostic,
    PR3Issue,
    PR3RunManifest,
    PR3Trace,
    check_schemas,
    data,
    digest,
    fail,
    parse,
)
from .load_run import load_grouping_run, selected_digest
from .pipeline import run_evidence_step

STREAMS = {"claims": "claims", "citations": "citations", "claim_assessments": "assessments",
    "evidence_links": "links", "source_lineage": "lineage", "conflicts": "conflicts",
    "bundles": "bundles", "evidence_states": "next_state"}


def current_sources():
    result = parent_sources()
    result.update({p.relative_to(ROOT).as_posix(): sha256_bytes(p.read_bytes())
                   for p in (PACKAGE / "pr3").glob("*.py")})
    return result


def load_config(path, pin):
    path = safe_path(path, areas=(PACKAGE / "manifests", ROOT / ".tmp"), code="MANIFEST_PATH_INVALID")
    raw = path.read_bytes()
    if sha256_bytes(raw) != pin:
        fail("CONFIG_SHA_MISMATCH", "input", "config")
    return parse(PR3Config, read_json(raw))


def run_sequence(inputs, results, *, grouping_config, config):
    prior, outputs = None, []
    for grouping, grouped in zip(inputs, results, strict=True):
        value = EvidenceInput(grouping_input=grouping, grouping_result=grouped,
            grouping_config=grouping_config, config_sha256=digest(config), previous_state=prior,
            previous_state_sha256=digest(prior) if prior else None)
        result = run_evidence_step(evidence_input=value, config=config)
        outputs.append(result)
        prior = result.next_state
    return tuple(outputs)


def run_replay(grouping_run, *, grouping_manifest_sha256, through_step, config_path, config_sha256, out):
    start = perf_counter()
    output = output_location(out)
    config = load_config(config_path, config_sha256)
    if not check_schemas():
        fail("SCHEMA_INVALID", "input", "schema/v3")
    parent, inputs, grouped, grouping_config = load_grouping_run(grouping_run,
        manifest_sha256=grouping_manifest_sha256, through_step=through_step)
    results = run_sequence(inputs, grouped, grouping_config=grouping_config, config=config)
    payloads = {"config_snapshot.json": json_bytes(config),
        "validation_report.json": json_bytes({"ok": True, "steps": [data(r.validation) for r in results]})}
    for filename, field in STREAMS.items():
        payloads[filename + ".jsonl"] = b"".join(json_bytes({"cursor": data(r.cursor),
            field: data(getattr(r, field)) if field == "next_state" else [data(v) for v in getattr(r, field)]})
                                                    for r in results)
    payloads["claim_history.jsonl"] = b"".join(json_bytes({"cursor": data(r.cursor),
        "transitions": [data(v) for v in r.transitions], "memberships": [data(v) for v in r.memberships]}) for r in results)
    git = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, timeout=10, check=True)
    manifest = PR3RunManifest(parent_manifest_sha256=grouping_manifest_sha256,
        parent_run_path=Path(grouping_run).resolve().relative_to(ROOT).as_posix(), through_step=through_step,
        config_file_sha256=config_sha256, config_sha256=digest(config), git_sha=git.stdout.strip(),
        runtime_source_sha256=current_sources(),
        schema_sha256={p.relative_to(PACKAGE).as_posix(): sha256_bytes(p.read_bytes())
                       for p in (PACKAGE / "schema/v3").glob("*.schema.json")},
        dependency_lock_sha256=parent.dependency_lock_sha256,
        dependency_versions={"python": platform.python_version(), "pydantic": pydantic.__version__},
        selected_input_sha256=selected_digest(inputs, grouped),
        artifacts=tuple(ArtifactDigest(path=name, sha256=sha256_bytes(raw), byte_count=len(raw),
            record_count=len(raw.splitlines()) if name.endswith(".jsonl") else None) for name, raw in sorted(payloads.items())))
    payloads["run_manifest.json"] = json_bytes(manifest)
    payloads["trace.json"] = json_bytes(PR3Trace(run_manifest_sha256=sha256_bytes(payloads["run_manifest.json"]),
        generated_at=datetime.now(timezone.utc), execution_ms=float((perf_counter() - start) * 1000)))
    write_payloads(output, payloads)
    return dict(ok=True, steps=len(results), run_manifest_sha256=sha256_bytes(payloads["run_manifest.json"]),
                trace_sha256=sha256_bytes(payloads["trace.json"]))


def print_error(error):
    issue = PR3Issue(code=error.code, stage=getattr(error, "stage", "input"), field=error.field,
                     record_id=error.record_id or None)
    print(json_bytes(PR3Diagnostic(ok=False, counts={}, errors=(issue,), locator_validation="failed",
                                   rule_contract_validation="failed")).decode().strip())


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--grouping-run", type=Path, required=True)
    parser.add_argument("--grouping-manifest-sha256", required=True)
    parser.add_argument("--through-step", required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--config-sha256", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = run_replay(args.grouping_run, grouping_manifest_sha256=args.grouping_manifest_sha256,
            through_step=args.through_step, config_path=args.config, config_sha256=args.config_sha256, out=args.out)
    except ContractError as error:
        print_error(error)
        return 1
    except (OSError, ValueError, TypeError, KeyError, RuntimeError, subprocess.SubprocessError):
        from evals.intelligence_g2.contracts import G2Error
        print_error(G2Error("EXPORT_IO_ERROR", stage="export", field="run"))
        return 1
    print(json_bytes(result).decode().strip())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
