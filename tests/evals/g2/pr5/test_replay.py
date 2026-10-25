import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from evals.intelligence_g2.contracts import ROOT, G2Error, json_bytes
from evals.intelligence_g2.pr5.assets import FIXTURE
from evals.intelligence_g2.pr5.evaluate import evaluate_run, ratio
from evals.intelligence_g2.pr5.load_run import load_rule_run
from evals.intelligence_g2.pr5.replay import main

from ..support import output_path
from .support import cli_args, export_rule, pin


def test_T45_cli_seed_prefix_parent_immutability_and_evaluation(tmp_path):
    parent = export_rule(tmp_path)
    before = {p.name: pin(p) for p in parent.iterdir()}
    outputs = [output_path() for _ in range(3)]
    for seed, out in zip((1, 719), outputs[:2], strict=True):
        proc = subprocess.run([sys.executable, "-B", "-m", "evals.intelligence_g2.pr5.replay", *cli_args(parent, out)],
            cwd=ROOT, env={**os.environ, "PYTHONHASHSEED": str(seed)}, capture_output=True,
            text=True, encoding="utf-8", timeout=60)
        assert proc.returncode == 0, proc.stdout + proc.stderr
    for path in outputs[0].iterdir():
        if path.name != "trace.json":
            assert path.read_bytes() == (outputs[1] / path.name).read_bytes(), path.name
    assert main(cli_args(parent, outputs[2], step="D0")) == 0
    for path in outputs[2].glob("*.jsonl"):
        assert path.read_bytes().splitlines()[0] == (outputs[0] / path.name).read_bytes().splitlines()[0]
    assert before == {p.name: pin(p) for p in parent.iterdir()}
    refs = FIXTURE / "reference/manifest.json"
    result = evaluate_run(outputs[0], run_manifest_sha256=pin(outputs[0] / "run_manifest.json"),
        reference_manifest=refs, reference_sha256=pin(refs), out=output_path())
    assert result["ok"]
    trace = json.loads((outputs[0] / "trace.json").read_bytes())
    assert trace["model_calls"] == trace["external_requests"] == trace["billed_cost"] == 0


@pytest.mark.parametrize("option,code", [("--config-sha256", "CONFIG_SHA_MISMATCH"),
    ("--rule-manifest-sha256", "MANIFEST_SHA_MISMATCH")])
def test_invalid_pin_no_directory(tmp_path, capsys, option, code):
    parent, out = export_rule(tmp_path), output_path()
    args = cli_args(parent, out)
    args[args.index(option) + 1] = "0" * 64
    assert main(args) == 1
    assert json.loads(capsys.readouterr().out)["errors"][0]["code"] == code
    assert not out.exists()


def test_T45_atomic_failure_no_overwrite_and_path_escape(tmp_path, monkeypatch, capsys):
    parent, out = export_rule(tmp_path), output_path()
    original = Path.open

    def broken(self, *args, **kwargs):
        if self.name == "presentations.jsonl" and args and args[0] == "xb":
            raise OSError("PRIVATE_WRITE_FAILURE")
        return original(self, *args, **kwargs)
    with monkeypatch.context() as scoped:
        scoped.setattr(Path, "open", broken)
        assert main(cli_args(parent, out)) == 1
    message = capsys.readouterr().out
    assert json.loads(message)["errors"][0]["code"] == "EXPORT_IO_ERROR"
    assert "PRIVATE_WRITE_FAILURE" not in message
    assert not out.exists() and not list(out.parent.glob("." + out.name + ".staging-*"))
    assert main(cli_args(parent, out)) == 0
    capsys.readouterr()
    before = {p.name: pin(p) for p in out.iterdir()}
    assert main(cli_args(parent, out)) == 1
    assert json.loads(capsys.readouterr().out)["errors"][0]["code"] == "OUTPUT_EXISTS"
    assert before == {p.name: pin(p) for p in out.iterdir()}
    escaped = ROOT / "evals/intelligence_v1/forbidden-pr5-output"
    assert main(cli_args(parent, escaped)) == 1
    assert json.loads(capsys.readouterr().out)["errors"][0]["code"] == "OUTPUT_PATH_INVALID"
    assert not escaped.exists()


def refresh(parent, name, raw):
    manifest = json.loads((parent / "run_manifest.json").read_bytes())
    (parent / name).write_bytes(raw)
    entry = next(e for e in manifest["artifacts"] if e["path"] == name)
    entry.update(sha256=pin(parent / name), byte_count=len(raw), record_count=len(raw.splitlines()))
    (parent / "run_manifest.json").write_bytes(json_bytes(manifest))


def test_T43_future_parent_text_stays_opaque_until_selected(tmp_path, capsys):
    parent = export_rule(tmp_path)
    rows = [json.loads(line) for line in (parent / "presentations.jsonl").read_bytes().splitlines()] if (parent / "presentations.jsonl").exists() else [
        json.loads(line) for line in (parent / "items.jsonl").read_bytes().splitlines()]
    rows[1]["items"][0]["headline"] = {"future_poison": True}
    refresh(parent, "items.jsonl", b"".join(json_bytes(r) for r in rows))
    early = output_path()
    assert main(cli_args(parent, early, step="D0")) == 0
    capsys.readouterr()
    assert b"future_poison" not in (early / "presentations.jsonl").read_bytes()
    out = output_path()
    assert main(cli_args(parent, out)) == 1
    assert json.loads(capsys.readouterr().out)["errors"][0]["code"] == "SCHEMA_INVALID"
    assert not out.exists()


def test_prediction_rejects_reference_role_before_open(tmp_path, monkeypatch):
    parent = export_rule(tmp_path)
    raw = json.loads((parent / "run_manifest.json").read_bytes())
    raw["artifacts"][0]["path"] = "reference/labels.json"
    (parent / "run_manifest.json").write_bytes(json_bytes(raw))
    original = Path.open

    def guarded(self, *args, **kwargs):
        assert "reference" not in self.parts
        return original(self, *args, **kwargs)
    monkeypatch.setattr(Path, "open", guarded)
    with pytest.raises(G2Error) as caught:
        load_rule_run(parent, manifest_sha256=pin(parent / "run_manifest.json"), through_step="D8")
    assert (caught.value.code, caught.value.stage, caught.value.field) == (
        "PREDICTION_PATH_INVALID", "input", "parent_artifact")


def test_reference_pin_and_zero_denominator(tmp_path):
    assert ratio(0, 0)["value"] is None and ratio(0, 0)["unavailable_reason"] == "zero_denominator"
    parent, out = export_rule(tmp_path), output_path()
    assert main(cli_args(parent, out)) == 0
    with pytest.raises(G2Error) as caught:
        evaluate_run(out, run_manifest_sha256=pin(out / "run_manifest.json"),
            reference_manifest=FIXTURE / "reference/manifest.json", reference_sha256="0" * 64, out=output_path())
    assert caught.value.code == "MANIFEST_SHA_MISMATCH"


def test_T46_empty_cli_retains_global_coverage(tmp_path, capsys):
    parent, out = export_rule(tmp_path, case="T32_EMPTY"), output_path()
    assert main(cli_args(parent, out, step="D0")) == 0
    capsys.readouterr()
    report = json.loads((out / "validation_report.json").read_bytes())
    # This fixture declares no observed windows. Preserve unknown rather than inventing coverage.
    assert report["steps"][0]["source_coverage"] == []
    assert report["steps"][0]["coverage_gaps"] == [dict(code="coverage_unknown", source_id=None,
        doc_version_id=None, coverage_window_id=None)]
    assert report["counts"] == dict(attempts=0, accepted=0, fallback=0, skipped=0)
    assert json.loads((out / "presentations.jsonl").read_bytes().splitlines()[0])["presentations"] == []
