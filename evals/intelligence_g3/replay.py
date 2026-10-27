"""Pinned read-only parent loading and exclusive G3 input export; never replay G2 algorithms."""

import argparse
import json
import platform
import re
import subprocess
import sys
from pathlib import Path

from evals.intelligence_g2.contracts import (
    G1_PIN,
    G2ReplayInput,
    data,
    digest,
    json_bytes,
    read_json,
)
from evals.intelligence_g2.pr2.replay import load_sequence
from evals.intelligence_g2.pr6.contracts import (
    CampaignSpec,
    CaseExecution,
    G2AcceptanceResult,
    SourceRelease,
)
from evals.intelligence_g2.pr6.manifest import sealed
from evals.intelligence_g2.replay import safe_path
from evals.intelligence_v1.hashing import sha256_bytes
from evals.intelligence_v1.temporal import parse_instant

from .bridge import adapt, preflight, preflight_step, same, unique
from .contracts import (
    PACKAGE,
    ROOT,
    G3Config,
    InputManifest,
    NativeStep,
    ParentBinding,
    SelectionDiagnostic,
    SyntheticParent,
    ValidationResult,
    fail,
    parse,
)

OUTPUT_BASE = ROOT / ".tmp/evals/g3"
READ_AREAS = (PACKAGE / "fixtures", PACKAGE / "manifests", OUTPUT_BASE,
              ROOT / ".tmp/evals/g2", ROOT / "evals/intelligence_g2", ROOT / "evals/intelligence_v1")
FORBIDDEN = {"reference", "labels", "events", "claims", "annotations", "adjudications", "review"}


def relative(value):
    if (not isinstance(value, str) or "\\" in value or ":" in value
            or any(p in {"", ".", ".."} or p.casefold() in FORBIDDEN for p in value.split("/"))):
        fail("G3_PATH_INVALID", "path")
    return Path(value)


def checked_path(value, areas=READ_AREAS):
    return safe_path(value, areas=areas, code="G3_PATH_INVALID")


def pinned_file(entry):
    path = checked_path(ROOT / relative(entry.path))
    raw = path.read_bytes()
    if sha256_bytes(raw) != entry.sha256:
        fail("G3_SHA_MISMATCH", "file")
    return raw


def verify_release(raw):
    release = parse(SourceRelease, read_json(raw))
    required = {p.relative_to(ROOT).as_posix()
                for area in (ROOT / "evals/intelligence_v1", ROOT / "evals/intelligence_g2")
                for p in area.rglob("*.py") if "__pycache__" not in p.parts}
    required.add("backend/cfaw_news/retrieval.py")
    schemas = {p.relative_to(ROOT).as_posix()
               for area in (ROOT / "evals/intelligence_v1/schema", ROOT / "evals/intelligence_g2/schema")
               for p in area.rglob("*.json")}
    if (not required <= release.runtime_files.keys() or not schemas <= release.schema_files.keys()
            or set(release.dependency_locks) != {"requirements.lock", "frontend/package-lock.json"}):
        fail("G3_PARENT_INVALID", "release_file_set")
    for group in (release.runtime_files, release.schema_files, release.dependency_locks):
        for name, pin in group.items():
            # Only code/schema/locks; no reference answer or user-data payloads.
            if not (name in required or name in schemas or name in release.dependency_locks
                    or name.startswith("evals/") and name.endswith(".py")):
                fail("G3_PARENT_INVALID", "release_path")
            p = checked_path(ROOT / relative(name), (ROOT / "evals", ROOT / "backend", ROOT / "frontend", ROOT))
            if release.files.get(name) != pin or sha256_bytes(p.read_bytes()) != pin:
                fail("G3_UPSTREAM_CHANGED", "source_or_schema_or_lock")
    return release


def selected_prefix(rows, manifest, *, cursor):
    identities = [cursor(r)["step_id"] for r in rows]
    if len(identities) != len(set(identities)):
        fail("G3_DUPLICATE_ID", "parent.step_id")
    if manifest.step_id not in identities:
        fail("G3_REFERENCE_NOT_FOUND", "step_id")
    stop = identities.index(manifest.step_id) + 1
    selected = rows[:stop]
    same(parse_instant(cursor(selected[-1])["as_of"]), manifest.as_of, "selected.as_of")
    # Whole-file hashing may read later bytes. Later bodies are not model-parsed.
    return selected, len(rows) - stop


def accepted_steps(manifest):
    acceptance = checked_path(ROOT / relative(manifest.acceptance.path), (ROOT / ".tmp/evals/g2",))
    campaign = checked_path(ROOT / relative(manifest.campaign.path), (ROOT / ".tmp/evals/g2",))
    acc = sealed(acceptance, manifest.acceptance.manifest_sha256)
    pred = sealed(campaign, manifest.campaign.manifest_sha256)
    same(acc.get("role"), "g2_development_acceptance", "acceptance.role")
    same(pred.get("role"), "prediction_campaign", "campaign.role")
    same(acc.get("prediction_manifest_sha256"), manifest.campaign.manifest_sha256, "parent_pin")
    result = parse(G2AcceptanceResult, read_json((acceptance / "G2_ACCEPTANCE.json").read_bytes()))
    if result.overall_status != "PASS" or not result.g3_offline_eligible:
        fail("G3_PARENT_NOT_ELIGIBLE", "g2_development")
    release_raw = (campaign / "source_release.json").read_bytes()
    release = verify_release(release_raw)
    same(read_json((acceptance / "source_release.json").read_bytes()), data(release), "source_release")
    same((result.source_commit, acc.get("source_commit")),
         (release.source_commit, pred.get("source_commit")), "source_commit")
    spec = parse(CampaignSpec, read_json((campaign / "campaign_snapshot.json").read_bytes()))
    same(spec.scope, "full", "campaign.scope")
    same(spec.g1_manifest.sha256, G1_PIN, "g1_pin")
    same(digest(spec), pred.get("campaign_sha256"), "campaign.config")
    executions = tuple(parse(CaseExecution, r)
                       for r in read_json((campaign / "predictions_index.json").read_bytes()))
    by_job = unique(executions, lambda e: e.job.job_id, "job_id")
    if manifest.job_id not in by_job:
        fail("G3_REFERENCE_NOT_FOUND", "job_id")
    execution = by_job[manifest.job_id]
    job = execution.job
    if not execution.returned:
        fail("G3_PARENT_INVALID", "rejected_job")
    same((job.strategy, job.profile, job.mode, job.seed, job.order, job.prefix, job.timeline_id),
         ("r1", "standard", "mock", 1, "canonical", False, manifest.timeline_id), "job.selection")
    raw = (checked_path(campaign / relative(execution.result_path), (campaign,))).read_bytes()
    same(sha256_bytes(raw), execution.semantic_sha256, "steps.sha256")
    rows, withheld = selected_prefix([read_json(line) for line in raw.splitlines()], manifest,
                                    cursor=lambda r: r["grouping"]["cursor"])
    if job.raw_input is None:
        inputs, _ = load_sequence(ROOT / relative(spec.g1_manifest.path),
            pin=spec.g1_manifest.sha256, timeline_id=job.timeline_id, through_step=manifest.step_id)
        from evals.intelligence_v1.loader import load_bundle

        bundle = load_bundle(ROOT / relative(spec.g1_manifest.path), manifest_sha256=G1_PIN)
        future_exposures = sum(parse_instant(r["occurred_at"]) > manifest.as_of
                               for r in bundle.rows["exposures"])
    else:
        future_exposures = None
        raw_inputs = [read_json(line) for line in pinned_file(job.raw_input).splitlines()]
        prefix, _ = selected_prefix(raw_inputs, manifest, cursor=lambda r: r["context"])
        inputs = []
        for r in prefix:
            preflight(r, manifest.as_of)
            inputs.append(parse(G2ReplayInput, r))
    same(len(inputs), len(rows), "prefix.length")
    handoff = read_json((acceptance / "G3_HANDOFF.json").read_bytes())
    selected_views = [v for v in handoff if v.get("trace_pointer") == execution.trace_path
                      and parse_instant(v["as_of"]) <= manifest.as_of]
    trace = dict(path=(Path(manifest.campaign.path) / relative(execution.trace_path)).as_posix(),
                 sha256=execution.trace_sha256)
    from evals.intelligence_g2.pr6.contracts import FilePin

    same(sha256_bytes(pinned_file(parse(FilePin, trace))), execution.trace_sha256, "trace")
    steps = []
    for replay, record in zip(inputs, rows, strict=True):
        current_views = [v for v in selected_views if parse_instant(v["as_of"]) == replay.context.as_of]
        raw_step = dict(replay_input=data(replay), record=record, trace=trace,
                        handoff_trace_pointer=execution.trace_path, handoff=current_views)
        preflight_step(raw_step, manifest.as_of)
        steps.append(parse(NativeStep, raw_step))
    return tuple(steps), release, sha256_bytes(release_raw), SelectionDiagnostic(
        withheld_parent_steps=withheld, withheld_handoff_views=len(handoff) - len(selected_views),
        unresolved_g1_exposures=inputs[-1].context.unresolved_exposure_ids,
        g1_visible_history_not_imported=len(inputs[-1].context.exposure_history),
        g1_source_future_exposure_records=future_exposures)


def load_input(manifest_path, *, manifest_sha256):
    if not isinstance(manifest_sha256, str) or re.fullmatch(r"[0-9a-f]{64}", manifest_sha256) is None:
        fail("G3_MANIFEST_SHA_MISMATCH", "manifest_sha256")
    path = checked_path(manifest_path, (PACKAGE / "manifests", OUTPUT_BASE))
    raw = path.read_bytes()
    if sha256_bytes(raw) != manifest_sha256:
        fail("G3_MANIFEST_SHA_MISMATCH", "manifest_sha256")
    manifest = parse(InputManifest, read_json(raw))
    config = parse(G3Config, read_json(pinned_file(manifest.config)))
    if manifest.kind == "accepted_g2":
        steps, release, release_pin, diagnostic = accepted_steps(manifest)
    else:
        probe_raw = read_json(pinned_file(manifest.fixture))
        # Temporal preflight only on the selected prefix, before nested model parsing.
        prefix, withheld = selected_prefix(probe_raw["steps"], manifest,
                                          cursor=lambda r: r["record"]["grouping"]["cursor"])
        selected = {**probe_raw, "steps": prefix}
        for step in prefix:
            preflight_step(step, manifest.as_of)
        probe = parse(SyntheticParent, selected)
        same(probe.job_id, manifest.job_id, "fixture.job_id")
        steps = probe.steps
        if any(d.record_origin != "synthetic" for s in steps for d in s.replay_input.visible_documents):
            fail("G3_PROVENANCE_INVALID", "synthetic_parent")
        release_raw = pinned_file(probe.source_release)
        release, release_pin = verify_release(release_raw), sha256_bytes(release_raw)
        for s in steps:
            pinned_file(s.trace)
        diagnostic = SelectionDiagnostic(withheld_parent_steps=withheld,
            unresolved_g1_exposures=steps[-1].replay_input.context.unresolved_exposure_ids,
            g1_visible_history_not_imported=len(steps[-1].replay_input.context.exposure_history))
    personas = read_json(pinned_file(manifest.personas))
    history = read_json(pinned_file(manifest.history))
    deliveries = read_json(pinned_file(manifest.deliveries))
    # Explicit files are a complete selected snapshot: reject every future row, no filtering.
    for value in (personas, history, deliveries):
        preflight(value, manifest.as_of)
    binding = ParentBinding(kind=manifest.kind, input_manifest_sha256=manifest_sha256,
        acceptance=manifest.acceptance, campaign=manifest.campaign, fixture=manifest.fixture,
        job_id=manifest.job_id, source_commit=release.source_commit,
        source_release_sha256=release_pin, g2_input_manifest_sha256=steps[-1].replay_input.input_manifest_sha256,
        pool_sha256=steps[-1].record.pool_sha256, config_file_sha256=manifest.config.sha256,
        config_sha256=digest(config))
    return adapt(manifest=manifest, binding=binding, steps=steps, personas=personas,
                 history=history, deliveries=deliveries, diagnostic=diagnostic)


def export_input(manifest_path, *, manifest_sha256, out):
    value = load_input(manifest_path, manifest_sha256=manifest_sha256)
    output = checked_path(out, (OUTPUT_BASE,))
    if output.exists():
        fail("G3_OUTPUT_EXISTS", "out")
    # Validate completely before creating any output. Exclusive files; failures have no seal.
    payloads = {"input_snapshot.json": json_bytes(value),
                "validation_report.json": json_bytes(ValidationResult(input_sha256=digest(value),
                    candidate_count=len(value.candidates), history_count=len(value.history),
                    diagnostic=value.diagnostic))}
    git = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, timeout=10)
    if git.returncode:
        fail("G3_SOURCE_UNAVAILABLE", "git")
    sources = {p.relative_to(ROOT).as_posix(): sha256_bytes(p.read_bytes())
               for p in sorted(PACKAGE.rglob("*")) if p.is_file()
               and (p.suffix == ".py" or "/schema/" in p.as_posix())}
    metadata = dict(schema_revision=value.schema_revision, role="g3_pr1_validated_input",
        input_manifest_sha256=manifest_sha256, source_commit=git.stdout.decode().strip(),
        source_files=sources, python_version=platform.python_version(),
        artifacts=[dict(path=n, sha256=sha256_bytes(b), byte_count=len(b)) for n, b in sorted(payloads.items())],
        model_calls=0, external_requests=0, scope="contracts_only_not_stage_acceptance")
    payloads["run_manifest.json"] = json_bytes(metadata)
    pin = sha256_bytes(payloads["run_manifest.json"])
    output.mkdir(parents=True, exist_ok=False)
    for name, raw in payloads.items():
        with (output / name).open("xb") as stream:
            stream.write(raw)
    with (output / "sealed.json").open("xb") as stream:
        stream.write(json_bytes(dict(status="complete", run_manifest_sha256=pin)))
    return value, pin


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--manifest-sha256", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    try:
        value, pin = export_input(args.manifest, manifest_sha256=args.manifest_sha256, out=args.out)
    except (ValueError, OSError, KeyError, TypeError) as e:
        print(json.dumps(dict(ok=False, code=getattr(e, "code", "G3_INPUT_INVALID"),
                              stage="g3_pr1", field=getattr(e, "field", "input_or_artifact"))))
        return 1
    print(json.dumps(dict(ok=True, candidates=len(value.candidates), run_manifest_sha256=pin)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
