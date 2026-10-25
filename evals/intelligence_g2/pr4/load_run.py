"""Pinned prediction-role reader; no reference/evaluation modules are imported."""

from evals.intelligence_g2.contracts import PACKAGE, ROOT, json_bytes, read_json
from evals.intelligence_g2.pr3.contracts import (
    EvidenceInput,
    EvidenceResult,
    PR3Config,
    PR3RunManifest,
)
from evals.intelligence_g2.pr3.load_run import load_grouping_run
from evals.intelligence_g2.pr3.replay import STREAMS, current_sources, run_sequence
from evals.intelligence_g2.replay import OUTPUT_BASE, safe_path
from evals.intelligence_v1.hashing import sha256_bytes

from .contracts import data, digest, fail, parse

ARTIFACTS = {n + ".jsonl" for n in STREAMS} | {"claim_history.jsonl", "config_snapshot.json", "validation_report.json"}


def preflight_result(row, cutoff):
    from evals.intelligence_g2.pr2.validate_output import instant

    for container in (row, row.get("next_state", {})):
        for ref in container.get("citations", ()):
            if isinstance(ref, dict) and ref.get("available_at") and instant(ref["available_at"]) > cutoff:
                fail("FUTURE_VERSION", "temporal", "available_at", ref.get("doc_version_id", ""))
        for collection, field in (("claims", "first_extracted_as_of"), ("transitions", "effective_at"),
                ("memberships", "effective_at"), ("assessments", "as_of")):
            for value in container.get(collection, ()):
                if isinstance(value, dict) and value.get(field) and instant(value[field]) > cutoff:
                    fail("G2_PR4_HISTORY_FUTURE", "history", collection + "." + field)


def load_evidence_run(directory, *, manifest_sha256, through_step):
    directory = safe_path(directory, areas=(OUTPUT_BASE,))
    raw = safe_path(directory / "run_manifest.json", areas=(directory,)).read_bytes()
    if sha256_bytes(raw) != manifest_sha256:
        fail("MANIFEST_SHA_MISMATCH", "input", "evidence_manifest")
    manifest = parse(PR3RunManifest, read_json(raw))
    if manifest.runtime_source_sha256 != current_sources():
        fail("RUNTIME_CODE_MISMATCH", "input", "parent_runtime_source_sha256")
    expected_schema = {p.relative_to(PACKAGE).as_posix(): sha256_bytes(p.read_bytes())
                       for p in (PACKAGE / "schema/v3").glob("*.schema.json")}
    if manifest.schema_sha256 != expected_schema:
        fail("SHA_MISMATCH", "input", "parent_schema")
    if set(manifest.dependency_lock_sha256) != {"requirements.lock", "frontend/package-lock.json"}:
        fail("G2_PR4_PARENT_RUN_MISMATCH", "input", "parent_locks")
    for name, pin in manifest.dependency_lock_sha256.items():
        if sha256_bytes((ROOT / name).read_bytes()) != pin:
            fail("SHA_MISMATCH", "input", "parent_locks")
    payloads = {}
    for entry in manifest.artifacts:
        if entry.path not in ARTIFACTS or entry.path in payloads:
            fail("PREDICTION_PATH_INVALID", "input", "parent_artifact")
        content = safe_path(directory / entry.path, areas=(directory,)).read_bytes()
        if (sha256_bytes(content) != entry.sha256 or len(content) != entry.byte_count
                or entry.record_count is not None and entry.record_count != len(content.splitlines())):
            fail("SHA_MISMATCH", "input", "parent_artifact", entry.path)
        payloads[entry.path] = content
    if set(payloads) != ARTIFACTS:
        fail("G2_PR4_PARENT_RUN_MISMATCH", "input", "parent_artifacts")
    config = parse(PR3Config, read_json(payloads["config_snapshot.json"]))
    if digest(config) != manifest.config_sha256:
        fail("CONFIG_SHA_MISMATCH", "input", "parent_config")
    columns = {field: [read_json(line) for line in payloads[name + ".jsonl"].splitlines()]
               for name, field in STREAMS.items()}
    history = [read_json(line) for line in payloads["claim_history.jsonl"].splitlines()]
    report = read_json(payloads["validation_report.json"])
    names = [row["cursor"]["step_id"] for row in history]
    if (not names or len(set(names)) != len(names) or names[-1] != manifest.through_step
            or through_step not in names or any(len(v) != len(names) for v in columns.values())
            or report.get("ok") is not True or len(report["steps"]) != len(names)):
        fail("G2_PR4_PARENT_RUN_MISMATCH", "input", "through_step")
    parent_path = safe_path(ROOT / manifest.parent_run_path, areas=(OUTPUT_BASE,))
    _, group_inputs, groups, group_config = load_grouping_run(parent_path,
        manifest_sha256=manifest.parent_manifest_sha256, through_step=through_step)
    # Verify the parent's full audit digest without validating future nested text objects.
    raw_inputs = [read_json(line) for line in safe_path(parent_path / "input_snapshots.jsonl", areas=(parent_path,)).read_bytes().splitlines()]
    raw_results = [read_json(line) for line in safe_path(parent_path / "results.jsonl", areas=(parent_path,)).read_bytes().splitlines()]
    parent_names = [v["cursor"]["step_id"] for v in raw_inputs]
    if manifest.through_step not in parent_names or parent_names[:len(names)] != names:
        fail("G2_PR4_PARENT_RUN_MISMATCH", "input", "parent_prefix")
    full_sha = sha256_bytes(json_bytes({"inputs": raw_inputs[:len(names)], "results": raw_results[:len(names)]}))
    if full_sha != manifest.selected_input_sha256:
        fail("G2_PR4_PARENT_RUN_MISMATCH", "input", "selected_input_sha256")
    for i, value in enumerate(group_inputs):
        row = {field: rows[i][field] for field, rows in columns.items()}
        row.update(transitions=history[i]["transitions"], memberships=history[i]["memberships"])
        preflight_result(row, value.cursor.as_of)
    expected = run_sequence(group_inputs, groups, grouping_config=group_config, config=config)
    results, inputs, prior = [], [], None
    for i, step in enumerate(expected):
        cursor = data(step.cursor)
        if history[i]["cursor"] != cursor or any(rows[i]["cursor"] != cursor for rows in columns.values()):
            fail("G2_PR4_PARENT_RUN_MISMATCH", "input", "cursor")
        row = {field: rows[i][field] for field, rows in columns.items()}
        row.update(cursor=cursor, transitions=history[i]["transitions"], memberships=history[i]["memberships"],
                   validation=report["steps"][i])
        preflight_result(row, step.cursor.as_of)
        result = parse(EvidenceResult, row)
        if result != step:
            fail("G2_PR4_PARENT_RUN_MISMATCH", "input", "evidence_result", step.cursor.step_id)
        value = EvidenceInput(grouping_input=group_inputs[i], grouping_result=groups[i], grouping_config=group_config,
            config_sha256=digest(config), previous_state=prior, previous_state_sha256=digest(prior) if prior else None)
        results.append(result)
        inputs.append(value)
        prior = result.next_state
    return manifest, tuple(inputs), tuple(results), config
