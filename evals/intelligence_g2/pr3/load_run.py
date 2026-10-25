"""Prediction-only PR2 artifact reader. References are never stat'ed or imported."""

from evals.intelligence_g2.contracts import ROOT, json_bytes, read_json
from evals.intelligence_g2.pr2.contracts import (
    GroupingInput,
    GroupingResult,
    PR2Config,
    PR2RunManifest,
)
from evals.intelligence_g2.pr2.replay import current_source_hashes
from evals.intelligence_g2.pr2.validate_output import validate_output as validate_grouping
from evals.intelligence_g2.replay import OUTPUT_BASE, safe_path
from evals.intelligence_g2.validate_output import preflight_time
from evals.intelligence_v1.hashing import sha256_bytes

from .contracts import digest, fail, parse

PARENT_ARTIFACTS = {"input_snapshots.jsonl", "results.jsonl", "config_snapshot.json",
    "validation_report.json", "features.jsonl", "relations.jsonl", "events.jsonl", "event_views.jsonl",
    "identity_log.jsonl", "identity_states.jsonl", "compatibility_links.jsonl"}


def load_grouping_run(directory, *, manifest_sha256, through_step):
    directory = safe_path(directory, areas=(OUTPUT_BASE,))
    path = safe_path(directory / "run_manifest.json", areas=(directory,))
    raw = path.read_bytes()
    if sha256_bytes(raw) != manifest_sha256:
        fail("MANIFEST_SHA_MISMATCH", "input", "grouping_manifest")
    manifest = parse(PR2RunManifest, read_json(raw))
    if manifest.runtime_source_sha256 != current_source_hashes():
        fail("RUNTIME_CODE_MISMATCH", "input", "parent_runtime_source_sha256")
    expected_schema_names = {p.relative_to(ROOT / "evals/intelligence_g2").as_posix()
        for folder in ("v1", "v2") for p in (ROOT / "evals/intelligence_g2/schema" / folder).glob("*.schema.json")}
    if set(manifest.schema_sha256) != expected_schema_names:
        fail("G2_PR3_PARENT_RUN_MISMATCH", "input", "parent_schema")
    for name, pin in manifest.schema_sha256.items():
        if sha256_bytes((ROOT / "evals/intelligence_g2" / name).read_bytes()) != pin:
            fail("SHA_MISMATCH", "input", "parent_schema")
    if set(manifest.dependency_lock_sha256) != {"requirements.lock", "frontend/package-lock.json"}:
        fail("G2_PR3_PARENT_RUN_MISMATCH", "input", "parent_locks")
    for name, pin in manifest.dependency_lock_sha256.items():
        if sha256_bytes((ROOT / name).read_bytes()) != pin:
            fail("SHA_MISMATCH", "input", "parent_locks")
    payloads = {}
    for artifact in manifest.artifacts:
        if artifact.path not in PARENT_ARTIFACTS:
            fail("PREDICTION_PATH_INVALID", "input", "parent_artifact")
        if artifact.path in payloads:
            fail("DUPLICATE_ID", "input", "parent_artifact")
        path = safe_path(directory / artifact.path, areas=(directory,))
        content = path.read_bytes()
        if (sha256_bytes(content) != artifact.sha256 or len(content) != artifact.byte_count
                or (artifact.record_count is not None and artifact.record_count != len(content.splitlines()))):
            fail("SHA_MISMATCH", "input", "parent_artifact", artifact.path)
        payloads[artifact.path] = content
    if set(payloads) != PARENT_ARTIFACTS:
        fail("G2_PR3_PARENT_RUN_MISMATCH", "input", "parent_artifacts")
    config = parse(PR2Config, read_json(payloads["config_snapshot.json"]))
    # Artifact SHA already checks snapshot bytes. Original config-file bytes can differ
    # in formatting/default omission; compare the parsed snapshot's semantic digest here.
    if digest(config) != manifest.config_sha256:
        fail("CONFIG_SHA_MISMATCH", "input", "parent_config")
    # JSON syntax and full-file hashes are checked, but future nested model/body validation
    # is deferred until its step. Whole-file bytes never enter the extraction algorithm.
    inputs_raw = [read_json(line) for line in payloads["input_snapshots.jsonl"].splitlines()]
    results_raw = [read_json(line) for line in payloads["results.jsonl"].splitlines()]
    names = [row["cursor"]["step_id"] for row in inputs_raw]
    if (not names or len(inputs_raw) != len(results_raw) or len(set(names)) != len(names)
            or through_step not in names):
        fail("G2_PR3_PARENT_RUN_MISMATCH", "input", "through_step")
    pool = [{"context": row["replay_input"]["context"],
        "documents": sorted(row["replay_input"]["visible_documents"], key=lambda d: d["candidate"]["doc_version_id"]),
        "sources": row["replay_input"]["sources"],
        "input_manifest_sha256": row["replay_input"]["input_manifest_sha256"]} for row in inputs_raw]
    if digest(pool) != manifest.candidate_pool_sha256:
        fail("G2_PR3_PARENT_RUN_MISMATCH", "input", "candidate_pool_sha256")
    inputs, results, prior = [], [], None
    for row, output in zip(inputs_raw[:names.index(through_step) + 1], results_raw, strict=False):
        preflight_time(row["replay_input"])
        value = parse(GroupingInput, row)
        result = parse(GroupingResult, output)
        if (value.previous_state != prior or value.strategy != manifest.strategy
                or value.replay_input.input_manifest_sha256 != manifest.input_manifest_sha256):
            fail("G2_PR3_PARENT_RUN_MISMATCH", "input", "parent_state_chain")
        validate_grouping(result, value, config)
        inputs.append(value)
        results.append(result)
        prior = result.next_state
    return manifest, tuple(inputs), tuple(results), config


def selected_digest(inputs, results):
    return sha256_bytes(json_bytes({"inputs": [v.model_dump(mode="json") for v in inputs],
                                   "results": [v.model_dump(mode="json") for v in results]}))
