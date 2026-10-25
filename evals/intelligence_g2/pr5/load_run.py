"""Prediction-only PR4 reader. Never imports evaluate or a reference loader."""

from evals.intelligence_g2.contracts import PACKAGE, ROOT, json_bytes
from evals.intelligence_g2.pr2.validate_output import instant
from evals.intelligence_g2.pr4.contracts import GenerationResult, PR4Config
from evals.intelligence_g2.pr4.contracts import RunManifest as RuleManifest
from evals.intelligence_g2.pr4.load_run import load_evidence_run
from evals.intelligence_g2.pr4.replay import (
    STREAMS,
    current_sources,
    projection_record,
    run_sequence,
)
from evals.intelligence_g2.pr4.validate_output import validate_output as validate_rule
from evals.intelligence_g2.replay import OUTPUT_BASE, safe_path
from evals.intelligence_v1.hashing import sha256_bytes

from .assets import strict_json
from .contracts import data, digest, fail, parse

ARTIFACTS = {n + ".jsonl" for n in STREAMS} | {
    "input_projections.jsonl", "config_snapshot.json", "validation_report.json"}


def preflight_rule(row, cutoff):
    for ref in row.get("citations", ()):
        if isinstance(ref, dict) and ref.get("available_at") and instant(ref["available_at"]) > cutoff:
            fail("FUTURE_VERSION", "temporal", "available_at")
    for snapshot in row.get("snapshots", ()):
        if isinstance(snapshot, dict) and snapshot.get("as_of") and instant(snapshot["as_of"]) > cutoff:
            fail("FUTURE_EVIDENCE", "temporal", "snapshot.as_of")


def load_rule_run(directory, *, manifest_sha256, through_step):
    directory = safe_path(directory, areas=(OUTPUT_BASE,))
    raw = safe_path(directory / "run_manifest.json", areas=(directory,)).read_bytes()
    if sha256_bytes(raw) != manifest_sha256:
        fail("MANIFEST_SHA_MISMATCH", "input", "rule_manifest")
    manifest = parse(RuleManifest, strict_json(raw))
    if manifest.runtime_source_sha256 != current_sources():
        fail("RUNTIME_CODE_MISMATCH", "input", "parent_runtime_source_sha256")
    schemas = {p.relative_to(PACKAGE).as_posix(): sha256_bytes(p.read_bytes())
               for p in (PACKAGE / "schema/v4").glob("*.schema.json")}
    if manifest.schema_sha256 != schemas:
        fail("SHA_MISMATCH", "input", "parent_schema")
    if set(manifest.dependency_lock_sha256) != {"requirements.lock", "frontend/package-lock.json"}:
        fail("G2_PR5_PARENT_RUN_MISMATCH", "input", "parent_locks")
    for name, pin in manifest.dependency_lock_sha256.items():
        if sha256_bytes((ROOT / name).read_bytes()) != pin:
            fail("SHA_MISMATCH", "input", "parent_locks")
    payloads = {}
    for entry in manifest.artifacts:
        if entry.path not in ARTIFACTS or entry.path in payloads:
            fail("PREDICTION_PATH_INVALID", "input", "parent_artifact")
        raw = safe_path(directory / entry.path, areas=(directory,)).read_bytes()
        if (sha256_bytes(raw) != entry.sha256 or len(raw) != entry.byte_count
                or entry.record_count is not None and len(raw.splitlines()) != entry.record_count):
            fail("SHA_MISMATCH", "input", "parent_artifact")
        payloads[entry.path] = raw
    if set(payloads) != ARTIFACTS:
        fail("G2_PR5_PARENT_RUN_MISMATCH", "input", "artifacts")
    config = parse(PR4Config, strict_json(payloads["config_snapshot.json"]))
    if digest(config) != manifest.config_sha256:
        fail("CONFIG_SHA_MISMATCH", "input", "parent_config")
    columns = {field: [strict_json(line) for line in payloads[name + ".jsonl"].splitlines()]
               for name, field in STREAMS.items()}
    projections = [strict_json(line) for line in payloads["input_projections.jsonl"].splitlines()]
    names = [p["cursor"]["step_id"] for p in projections]
    report = strict_json(payloads["validation_report.json"])
    if (not names or len(names) != len(set(names)) or names[-1] != manifest.through_step
            or through_step not in names or any(len(v) != len(names) for v in columns.values())
            or report.get("ok") is not True or len(report["steps"]) != len(names)):
        fail("G2_PR5_PARENT_RUN_MISMATCH", "input", "through_step")
    if digest([p["input_sha256"] for p in projections]) != manifest.selected_input_sha256:
        fail("G2_PR5_PARENT_RUN_MISMATCH", "input", "selected_input_sha256")
    parent = safe_path(ROOT / manifest.parent_run_path, areas=(OUTPUT_BASE,))
    evidence_manifest, inputs, evidence, evidence_config = load_evidence_run(parent,
        manifest_sha256=manifest.parent_manifest_sha256, through_step=through_step)
    if manifest.dependency_lock_sha256 != evidence_manifest.dependency_lock_sha256:
        fail("SHA_MISMATCH", "input", "parent_locks")
    values, expected = run_sequence(inputs, evidence, config=config, evidence_config=evidence_config)
    actual = []
    for i, result in enumerate(expected):
        row = {field: rows[i][field] for field, rows in columns.items()}
        preflight_rule(row, result.cursor.as_of)
        if (projections[i] != strict_json(json_bytes(projection_record(values[i])))
                or any(rows[i]["cursor"] != data(result.cursor) for rows in columns.values())):
            fail("G2_PR5_PARENT_RUN_MISMATCH", "input", "cursor_projection")
        row.update(cursor=data(result.cursor), validation=report["steps"][i])
        got = parse(GenerationResult, row)
        validate_rule(got, values[i], config)
        if got != result:
            fail("G2_PR5_PARENT_RUN_MISMATCH", "input", "rule_result")
        actual.append(got)
    return manifest, values, tuple(actual), config
