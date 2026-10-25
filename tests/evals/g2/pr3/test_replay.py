import json
import os
import subprocess
import sys

import pytest

from evals.intelligence_g2.contracts import ROOT, G2Error, json_bytes
from evals.intelligence_g2.pr3.evaluate import evaluate_run, load_evidence_run
from evals.intelligence_g2.pr3.replay import main

from ..support import output_path
from .support import CONFIG, FIXTURE, export_parent, pin


def args(parent, output, last="D8"):
    return ["--grouping-run", str(parent), "--grouping-manifest-sha256", pin(parent / "run_manifest.json"),
        "--through-step", last, "--config", str(CONFIG), "--config-sha256", pin(CONFIG), "--out", str(output)]


def test_cli_hash_seeds_prefix_and_zero_model_cost(tmp_path, capsys):
    parent = export_parent(tmp_path)
    outputs = [output_path() for _ in range(3)]
    for seed, out in zip((1, 719), outputs[:2], strict=True):
        result = subprocess.run([sys.executable, "-B", "-m", "evals.intelligence_g2.pr3.replay", *args(parent, out)],
            cwd=ROOT, env={**os.environ, "PYTHONHASHSEED": str(seed)}, capture_output=True,
            text=True, encoding="utf-8", timeout=60)
        assert result.returncode == 0, result.stdout + result.stderr
    for path in outputs[0].iterdir():
        if path.name != "trace.json":
            assert path.read_bytes() == (outputs[1] / path.name).read_bytes(), path.name
    assert main(args(parent, outputs[2], "D0")) == 0
    assert json.loads(capsys.readouterr().out)["ok"]
    for path in outputs[0].glob("*.jsonl"):
        assert path.read_bytes().splitlines()[0] == (outputs[2] / path.name).read_bytes().splitlines()[0]
    trace = json.loads((outputs[0] / "trace.json").read_bytes())
    assert trace["model_calls"] == trace["token_usage"] == trace["model_cost"] == 0
    assert trace["usage_reason"] == "not_called"
    manifest, results = load_evidence_run(outputs[0])
    assert len(results) == 2 and manifest.through_step == "D8"
    evaluation = output_path()
    ref = FIXTURE / "reference/manifest.json"
    assert evaluate_run(outputs[0], reference_manifest=ref, reference_sha256=pin(ref), out=evaluation)["errors"] == 0


@pytest.mark.parametrize("option,code", [("--config-sha256", "CONFIG_SHA_MISMATCH"),
    ("--grouping-manifest-sha256", "MANIFEST_SHA_MISMATCH")])
def test_wrong_pins_fail_before_output(tmp_path, capsys, option, code):
    parent = export_parent(tmp_path)
    output = output_path()
    argv = args(parent, output)
    argv[argv.index(option) + 1] = "0" * 64
    assert main(argv) == 1
    assert json.loads(capsys.readouterr().out)["errors"][0]["code"] == code
    assert not output.exists()


def test_existing_output_and_staging_failure_are_atomic(tmp_path, capsys, monkeypatch):
    from pathlib import Path

    parent = export_parent(tmp_path)
    output = output_path()
    original = Path.open

    def fail_write(self, *argv, **kwargs):
        if self.name == "bundles.jsonl" and argv and argv[0] == "xb":
            raise OSError("synthetic staging failure")
        return original(self, *argv, **kwargs)

    with monkeypatch.context() as scoped:
        scoped.setattr(Path, "open", fail_write)
        assert main(args(parent, output)) == 1
    assert json.loads(capsys.readouterr().out)["errors"][0]["code"] == "EXPORT_IO_ERROR"
    assert not output.exists()
    assert not list(output.parent.glob("." + output.name + ".staging-*"))
    assert main(args(parent, output)) == 0
    capsys.readouterr()
    before = {p.name: p.read_bytes() for p in output.iterdir()}
    assert main(args(parent, output)) == 1
    assert json.loads(capsys.readouterr().out)["errors"][0]["code"] == "OUTPUT_EXISTS"
    assert before == {p.name: p.read_bytes() for p in output.iterdir()}


def refresh_parent(parent, changed):
    from evals.intelligence_g2.pr3.contracts import digest

    path = parent / "run_manifest.json"
    manifest = json.loads(path.read_bytes())
    for name, raw in changed.items():
        (parent / name).write_bytes(raw)
        entry = next(a for a in manifest["artifacts"] if a["path"] == name)
        entry.update(sha256=pin(parent / name), byte_count=len(raw), record_count=len(raw.splitlines()))
    if "input_snapshots.jsonl" in changed:
        rows = [json.loads(line) for line in changed["input_snapshots.jsonl"].splitlines()]
        pool = [{"context": row["replay_input"]["context"],
            "documents": sorted(row["replay_input"]["visible_documents"], key=lambda d: d["candidate"]["doc_version_id"]),
            "sources": row["replay_input"]["sources"],
            "input_manifest_sha256": row["replay_input"]["input_manifest_sha256"]} for row in rows]
        manifest["candidate_pool_sha256"] = digest(pool)
    path.write_bytes(json_bytes(manifest))


def test_T26_current_future_body_preflight_and_whole_future_step_opaque(tmp_path, capsys):
    parent = export_parent(tmp_path)
    rows = [json.loads(line) for line in (parent / "input_snapshots.jsonl").read_bytes().splitlines()]
    rows[1]["replay_input"]["visible_documents"][0]["candidate"]["paragraphs"] = "FUTURE_POISON_INVALID"
    refresh_parent(parent, {"input_snapshots.jsonl": b"".join(json_bytes(r) for r in rows)})
    early = output_path()
    assert main(args(parent, early, "D0")) == 0
    capsys.readouterr()
    assert b"POISON" not in (early / "claims.jsonl").read_bytes()
    late = output_path()
    assert main(args(parent, late)) == 1
    assert json.loads(capsys.readouterr().out)["errors"][0]["code"] == "SCHEMA_INVALID"
    assert not late.exists()
    rows[0]["replay_input"]["visible_documents"][0]["candidate"].update(
        available_at=rows[1]["cursor"]["as_of"], paragraphs="CURRENT_STEP_FUTURE_POISON")
    refresh_parent(parent, {"input_snapshots.jsonl": b"".join(json_bytes(r) for r in rows)})
    output = output_path()
    assert main(args(parent, output, "D0")) == 1
    issue = json.loads(capsys.readouterr().out)["errors"][0]
    assert (issue["code"], issue["stage"], issue["field"], issue["record_id"]) == (
        "FUTURE_VERSION", "bridge", "candidate.available_at", "a:1")
    assert not output.exists()


def test_parent_reference_artifact_is_rejected_without_opening_it(tmp_path, capsys):
    parent = export_parent(tmp_path)
    path = parent / "run_manifest.json"
    value = json.loads(path.read_bytes())
    value["artifacts"].append(dict(path="reference/answer.json", sha256="0" * 64, byte_count=1, record_count=None))
    path.write_bytes(json_bytes(value))
    output = output_path()
    assert main(args(parent, output)) == 1
    assert json.loads(capsys.readouterr().out)["errors"][0]["code"] == "PREDICTION_PATH_INVALID"
    assert not output.exists()


def test_evaluation_detects_prediction_file_tampering(tmp_path, capsys):
    parent = export_parent(tmp_path)
    output = output_path()
    assert main(args(parent, output)) == 0
    capsys.readouterr()
    (output / "claims.jsonl").write_bytes(b"tampered\n")
    with pytest.raises(G2Error) as error:
        load_evidence_run(output)
    assert (error.value.code, error.value.stage, error.value.field, error.value.record_id) == (
        "SHA_MISMATCH", "evaluation", "artifact", "claims.jsonl")
