"""Test-only bundle copies and tampering. Product code never refreshes a pin."""

import json
from pathlib import Path
from uuid import uuid4

from evals.intelligence_g2.bridge import load_replay_input, project_step
from evals.intelligence_g2.contracts import G1_PIN, PACKAGE, ROOT, G2Config, json_bytes
from evals.intelligence_g2.replay import OUTPUT_BASE
from evals.intelligence_v1.hashing import sha256_bytes
from evals.intelligence_v1.loader import PREDICTION_ROLES, load_bundle

SOURCE = ROOT / "evals/intelligence_v1"
CONFIG = PACKAGE / "manifests/pr1_config.json"


def input_at(timeline="DEV-01", step="D0", *, root=SOURCE):
    manifest = root / "manifests/dataset_manifest.json"
    pin = G1_PIN if root == SOURCE else sha256_bytes(manifest.read_bytes())
    return load_replay_input(manifest, manifest_sha256=pin, timeline_id=timeline,
                              step_id=step, config=G2Config())[0]


def copied_bundle(tmp_path):
    """Copy only prediction materials. References need not even exist for a replay."""
    root = tmp_path / "bundle"
    manifest = json.loads((SOURCE / "manifests/dataset_manifest.json").read_bytes())
    for entry in manifest["file_hashes"]:
        if entry["role"] not in PREDICTION_ROLES:
            continue
        target = root / entry["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((SOURCE / entry["path"]).read_bytes())
    target = root / "manifests/dataset_manifest.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(json_bytes(manifest))
    return root


def rows(root, path):
    return [json.loads(line) for line in (root / path).read_bytes().splitlines()]


def save_rows(root, path, records):
    (root / path).write_bytes(b"".join(json_bytes(record) for record in records))


def refresh_copy(root):
    """Explicit synthetic test preparation, never used for a tampering-integrity test."""
    path = root / "manifests/dataset_manifest.json"
    manifest = json.loads(path.read_bytes())
    manifest["dataset_revision"] = "g2-pr1-test-copy-v1"
    for entry in manifest["file_hashes"]:
        if entry["role"] not in PREDICTION_ROLES:
            continue
        raw = (root / entry["path"]).read_bytes()
        entry["sha256"] = sha256_bytes(raw)
        if entry["path"].endswith(".jsonl"):
            entry["record_count"] = len(raw.splitlines())
        if entry["role"] == "source_registry":
            entry["record_count"] = len(json.loads(raw)["sources"])
            manifest["source_registry_sha256"] = entry["sha256"]
        if entry["role"] == "baseline_config":
            manifest["baseline_config_sha256"] = entry["sha256"]
    path.write_bytes(json_bytes(manifest))
    return sha256_bytes(path.read_bytes())


def project(root=SOURCE, *, timeline="DEV-01", step="D0", **kwargs):
    manifest = root / "manifests/dataset_manifest.json"
    pin = G1_PIN if root == SOURCE else sha256_bytes(manifest.read_bytes())
    bundle = load_bundle(manifest, manifest_sha256=pin)
    return project_step(bundle, manifest_sha256=pin, timeline_id=timeline, step_id=step,
                         config=G2Config(), **kwargs)


def output_path():
    return OUTPUT_BASE / "tests" / ("case-" + uuid4().hex)


def cli_args(out, root=SOURCE, *, pin=None, config=CONFIG, config_pin=None):
    manifest = root / "manifests/dataset_manifest.json"
    return ["--manifest", str(manifest), "--manifest-sha256",
            pin if pin is not None else (G1_PIN if root == SOURCE
                                        else sha256_bytes(manifest.read_bytes())),
            "--timeline", "DEV-01", "--step", "D0", "--config", str(config),
            "--config-sha256", config_pin if config_pin is not None else sha256_bytes(
                Path(config).read_bytes()), "--out", str(out)]


def assert_error(caught, code, stage=None, field=None):
    error = caught.value
    assert error.code == code
    if stage is not None:
        assert error.stage == stage
    if field is not None:
        assert error.field == field
