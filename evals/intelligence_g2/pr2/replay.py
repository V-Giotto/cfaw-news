"""Pinned prefix replay; predictions never load development references."""

import argparse
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

import pydantic

from evals.intelligence_g2.bridge import project_step
from evals.intelligence_g2.contracts import (
    G1_PIN,
    PACKAGE,
    ROOT,
    ArtifactDigest,
    G2Config,
    G2ReplayInput,
    data,
    digest,
    json_bytes,
    parse,
    read_json,
)
from evals.intelligence_g2.contracts import check_schemas as check_pr1_schemas
from evals.intelligence_g2.replay import load_config as load_pr1_config
from evals.intelligence_g2.replay import output_location, safe_path, write_payloads
from evals.intelligence_g2.validate_output import preflight_time
from evals.intelligence_v1.exceptions import ContractError
from evals.intelligence_v1.hashing import sha256_bytes
from evals.intelligence_v1.loader import load_bundle
from evals.intelligence_v1.temporal import parse_instant

from .contracts import (
    FixtureManifest,
    GroupingInput,
    PR2Config,
    PR2Diagnostic,
    PR2Issue,
    PR2RunManifest,
    PR2Trace,
    ReplayCursor,
    check_schemas,
    checked_relative_path,
    fail,
)
from .pipeline import run_grouping_step


def load_config(path, pin):
    path = safe_path(path, areas=(PACKAGE / "manifests", ROOT / ".tmp"),
                     code="MANIFEST_PATH_INVALID")
    raw = path.read_bytes()
    if sha256_bytes(raw) != pin:
        fail("CONFIG_SHA_MISMATCH", "input", "config")
    config = parse(PR2Config, read_json(raw))
    load_pr1_config(PACKAGE / "manifests/pr1_config.json", config.pr1_config_file_sha256)
    return config


def fixture_inputs(path, manifest, *, pin, timeline_id, through_step):
    manifest = parse(FixtureManifest, manifest)
    paths = [f.path for f in manifest.files]
    if len(paths) != len(set(paths)):
        fail("DUPLICATE_ID", "input", "files")
    rows = []
    for entry in manifest.files:
        if entry.role != "prediction":
            continue  # References are not even stat'ed, including missing reference files.
        checked_relative_path(entry.path)
        target = safe_path(path.parent / entry.path, areas=(path.parent,), code="MANIFEST_PATH_INVALID")
        raw = target.read_bytes()
        if sha256_bytes(raw) != entry.sha256:
            fail("SHA_MISMATCH", "input", "prediction")
        rows.extend(read_json(line) for line in raw.splitlines())
    selected = [r for r in rows if r["context"]["timeline_id"] == timeline_id]
    selected.sort(key=lambda r: (parse_instant(r["context"]["as_of"]), r["context"]["step_id"]))
    names = [r["context"]["step_id"] for r in selected]
    if through_step not in names or len(names) != len(set(names)):
        fail("REFERENCE_NOT_FOUND", "input", "through_step")
    selected = selected[:names.index(through_step) + 1]
    result = []
    for row in selected:
        # Only selected step objects are validated; a future poison payload stays opaque.
        row = {**row, "input_manifest_sha256": pin}
        preflight_time(row)
        value = parse(G2ReplayInput, row)
        if any(d.record_origin != "synthetic" for d in value.visible_documents):
            fail("ORIGIN_MISMATCH", "input", "fixture.record_origin")
        result.append(value)
    return tuple(result), {}


def load_sequence(path, *, pin, timeline_id, through_step):
    path = safe_path(path, areas=(ROOT / "evals/intelligence_v1", ROOT / ".tmp",
        PACKAGE / "fixtures/pr2"), code="MANIFEST_PATH_INVALID")
    raw = path.read_bytes()
    if sha256_bytes(raw) != pin:
        fail("MANIFEST_SHA_MISMATCH", "input", "manifest")
    header = read_json(raw)
    if header.get("format") == "g2-pr2-prediction-v1":
        values, _ = fixture_inputs(path, header, pin=pin, timeline_id=timeline_id, through_step=through_step)
        # Freeze R0's actual source even for standalone synthetic inputs. Read code-role files
        # only; loading the full G1 reference validator here would break prediction isolation.
        root = ROOT / "evals/intelligence_v1"
        frozen = (root / "manifests/dataset_manifest.json").read_bytes()
        if sha256_bytes(frozen) != G1_PIN:
            fail("MANIFEST_SHA_MISMATCH", "input", "g1_manifest")
        hashes = {}
        for entry in read_json(frozen)["file_hashes"]:
            if entry["role"] == "code":
                name = checked_relative_path(entry["path"])
                actual = sha256_bytes((root / name).read_bytes())
                if actual != entry["sha256"]:
                    fail("RUNTIME_CODE_MISMATCH", "input", "r0_source", name)
                hashes["evals/intelligence_v1/" + name] = actual
            elif entry["role"] == "baseline_config":
                name = checked_relative_path(entry["path"])
                config_raw = (root / name).read_bytes()
                if sha256_bytes(config_raw) != entry["sha256"]:
                    fail("SHA_MISMATCH", "input", "r0_config")
                baseline = read_json(config_raw)
                from evals.intelligence_v1.contracts import BaselineConfig

                defaults = BaselineConfig()
                if any(baseline[k] != getattr(defaults, k) for k in (
                        "grouping_revision", "body_jaccard", "title_jaccard", "min_body_tokens")):
                    fail("CONFIG_NOT_PINNED", "input", "r0_config")
                retrieval = ROOT / "backend/cfaw_news/retrieval.py"
                if sha256_bytes(retrieval.read_bytes()) != baseline["retrieval_sha256"]:
                    fail("RUNTIME_CODE_MISMATCH", "input", "retrieval")
        return values, hashes
    bundle = load_bundle(path, manifest_sha256=pin)
    steps = sorted((s for s in bundle.steps if s.timeline_id == timeline_id),
                   key=lambda s: (s.as_of, s.step_id))
    names = [s.step_id for s in steps]
    if through_step not in names:
        fail("REFERENCE_NOT_FOUND", "input", "through_step")
    values = tuple(project_step(bundle, manifest_sha256=pin, timeline_id=timeline_id,
        step_id=s.step_id, config=G2Config()) for s in steps[:names.index(through_step) + 1])
    hashes = {"evals/intelligence_v1/" + k: h for k, h in bundle.verified_hashes.items()
              if k.endswith(".py")}
    hashes["backend/cfaw_news/retrieval.py"] = bundle.config.retrieval_sha256
    return values, hashes


def run_sequence(values, *, strategy, config):
    prior, inputs, results = None, [], []
    for ordinal, replay in enumerate(values):
        cursor = ReplayCursor(timeline_id=replay.context.timeline_id, step_id=replay.context.step_id,
            as_of=replay.context.as_of, ordinal=ordinal,
            previous_step_id=prior.cursor.step_id if prior else None)
        value = GroupingInput(replay_input=replay, strategy=strategy,
            grouping_config_sha256=digest(config), cursor=cursor, previous_state=prior,
            previous_state_sha256=digest(prior) if prior else None)
        result = run_grouping_step(grouping_input=value, config=config)
        inputs.append(value)
        results.append(result)
        prior = result.next_state
    return tuple(inputs), tuple(results)


def candidate_pool(inputs):
    return [{"context": data(v.replay_input.context),
             "documents": [data(d) for d in sorted(v.replay_input.visible_documents,
                                                    key=lambda d: d.candidate.doc_version_id)],
             "sources": [data(s) for s in v.replay_input.sources],
             "input_manifest_sha256": v.replay_input.input_manifest_sha256}
            for v in inputs]


def current_source_hashes():
    paths = [p for directory in (PACKAGE, PACKAGE / "pr2", ROOT / "evals/intelligence_v1")
             for p in directory.glob("*.py")]
    paths.append(ROOT / "backend/cfaw_news/retrieval.py")
    return {p.relative_to(ROOT).as_posix(): sha256_bytes(p.read_bytes()) for p in paths}


def run_replay(manifest_path, *, manifest_sha256, timeline_id, through_step, strategy,
               config_path, config_sha256, out):
    started = perf_counter()
    output = output_location(out)
    config = load_config(config_path, config_sha256)
    if not check_schemas() or not check_pr1_schemas():
        fail("SCHEMA_INVALID", "schema", "schema/v2")
    values, sources = load_sequence(manifest_path, pin=manifest_sha256,
        timeline_id=timeline_id, through_step=through_step)
    inputs, results = run_sequence(values, strategy=strategy, config=config)
    payloads = {"input_snapshots.jsonl": b"".join(json_bytes(v) for v in inputs),
                "results.jsonl": b"".join(json_bytes(r) for r in results),
                "config_snapshot.json": json_bytes(config),
                "validation_report.json": json_bytes(PR2Diagnostic(ok=True,
                    counts={"steps": len(results)}))}
    for name, attribute in (("features", "features"), ("relations", "relations"),
            ("events", "events"), ("event_views", "views"), ("identity_log", "transitions"),
            ("identity_states", "next_state")):
        payloads[name + ".jsonl"] = b"".join(json_bytes({"cursor": data(r.cursor),
            attribute: data(getattr(r, attribute)) if attribute == "next_state" else
                       [data(v) for v in getattr(r, attribute)]}) for r in results)
    payloads["compatibility_links.jsonl"] = b"".join(json_bytes({"cursor": data(r.cursor),
        "links": [data(link) for view in r.views for link in view.compatibility_links]}) for r in results)
    git = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                         text=True, timeout=10, check=True)
    sources.update(current_source_hashes())
    schema_hashes = {p.relative_to(PACKAGE).as_posix(): sha256_bytes(p.read_bytes())
                     for directory in (PACKAGE / "schema/v1", PACKAGE / "schema/v2")
                     for p in directory.glob("*.schema.json")}
    manifest = PR2RunManifest(strategy=strategy, input_manifest_sha256=manifest_sha256,
        config_file_sha256=config_sha256, config_sha256=digest(config), git_sha=git.stdout.strip(),
        runtime_source_sha256=sources, schema_sha256=schema_hashes,
        dependency_lock_sha256={p: sha256_bytes((ROOT / p).read_bytes()) for p in (
            "requirements.lock", "frontend/package-lock.json")},
        dependency_versions={"python": platform.python_version(), "pydantic": pydantic.__version__},
        candidate_pool_sha256=digest(candidate_pool(inputs)),
        artifacts=tuple(ArtifactDigest(path=name, sha256=sha256_bytes(raw), byte_count=len(raw),
            record_count=len(raw.splitlines()) if name.endswith(".jsonl") else None)
            for name, raw in sorted(payloads.items())))
    payloads["run_manifest.json"] = json_bytes(manifest)
    payloads["trace.json"] = json_bytes(PR2Trace(run_manifest_sha256=sha256_bytes(
        payloads["run_manifest.json"]), generated_at=datetime.now(timezone.utc),
        execution_ms=float((perf_counter() - started) * 1000)))
    write_payloads(output, payloads)
    return {"ok": True, "steps": len(results), "strategy": strategy,
        "run_manifest_sha256": sha256_bytes(payloads["run_manifest.json"]),
        "trace_sha256": sha256_bytes(payloads["trace.json"])}


def print_error(error):
    issue = PR2Issue(code=error.code, stage=getattr(error, "stage", "input"), field=error.field,
                     record_id=error.record_id or None)
    print(json_bytes(PR2Diagnostic(ok=False, counts={}, errors=(issue,))).decode().strip())


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--manifest-sha256", required=True)
    parser.add_argument("--timeline", required=True)
    parser.add_argument("--through-step", required=True)
    parser.add_argument("--strategy", choices=("r0", "r1", "r2"), default="r1")
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--config-sha256", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = run_replay(args.manifest, manifest_sha256=args.manifest_sha256,
            timeline_id=args.timeline, through_step=args.through_step, strategy=args.strategy,
            config_path=args.config, config_sha256=args.config_sha256, out=args.out)
    except ContractError as error:
        print_error(error)
        return 1
    except (OSError, ValueError, TypeError, KeyError, RuntimeError, subprocess.SubprocessError):
        from evals.intelligence_g2.contracts import G2Error

        print_error(G2Error("EXPORT_IO_ERROR", stage="export"))
        return 1
    print(json_bytes(result).decode().strip())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
