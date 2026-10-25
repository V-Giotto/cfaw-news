import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from evals.intelligence_g2.contracts import ROOT, G2Error, json_bytes
from evals.intelligence_g2.pr2.evaluate import compare_loaded, evaluate_runs, load_run
from evals.intelligence_g2.pr2.reference_loader import load_references
from evals.intelligence_g2.pr2.replay import load_sequence, main, run_replay

from ..support import output_path
from .support import CONFIG, FIXTURES, pin


def args(out, strategy="r1", timeline="EVIDENCE", last="D8", manifest=None):
    manifest = manifest or FIXTURES / "prediction/manifest.json"
    return ["--manifest", str(manifest), "--manifest-sha256", pin(manifest),
        "--timeline", timeline, "--through-step", last, "--strategy", strategy,
        "--config", str(CONFIG), "--config-sha256", pin(CONFIG), "--out", str(out)]


def export(out, strategy="r1", timeline="EVIDENCE", last="D8"):
    manifest = FIXTURES / "prediction/manifest.json"
    return run_replay(manifest, manifest_sha256=pin(manifest), timeline_id=timeline,
        through_step=last, strategy=strategy, config_path=CONFIG, config_sha256=pin(CONFIG), out=out)


def test_T18_cli_hash_seed_semantic_bytes_and_prefix(capsys):
    outputs = [output_path(), output_path(), output_path()]
    for seed, out in zip((1, 719), outputs[:2], strict=True):
        env = {**os.environ, "PYTHONHASHSEED": str(seed)}
        result = subprocess.run([sys.executable, "-B", "-m", "evals.intelligence_g2.pr2.replay",
            *args(out)], cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8", timeout=60)
        assert result.returncode == 0, result.stdout + result.stderr
    for path in outputs[0].iterdir():
        if path.name != "trace.json":
            assert path.read_bytes() == (outputs[1] / path.name).read_bytes(), path.name
    assert main(args(outputs[2], last="D0")) == 0
    assert json.loads(capsys.readouterr().out)["ok"]
    for name in ("features", "relations", "events", "event_views", "identity_log", "identity_states"):
        assert (outputs[2] / (name + ".jsonl")).read_bytes().splitlines()[0] == (
            outputs[0] / (name + ".jsonl")).read_bytes().splitlines()[0]
    trace = json.loads((outputs[0] / "trace.json").read_bytes())
    assert trace["model_calls"] == trace["token_usage"] == trace["model_cost"] == 0
    assert trace["usage_reason"] == "not_called"
    manifest = json.loads((outputs[0] / "run_manifest.json").read_bytes())
    assert trace["run_manifest_sha256"] == pin(outputs[0] / "run_manifest.json")
    for artifact in manifest["artifacts"]:
        assert pin(outputs[0] / artifact["path"]) == artifact["sha256"]


def test_T18_frozen_input_expected_groups_are_only_consumed_by_tests():
    prediction = FIXTURES / "prediction/manifest.json"
    expected = json.loads((FIXTURES / "reference/expected_groups.json").read_bytes())
    for timeline in sorted({row["timeline_id"] for row in expected}):
        rows = [r for r in expected if r["timeline_id"] == timeline]
        values, _ = load_sequence(prediction, pin=pin(prediction), timeline_id=timeline,
                                  through_step=rows[-1]["step_id"])
        from .support import run

        # BRIDGE exercises the registered R2 variant; all other contract examples use default R1.
        results = run(values, "r2" if timeline == "BRIDGE" else "r1")[1]
        for value, result, ref in zip(values, results, rows, strict=True):
            documents = {d.candidate.doc_version_id: d.candidate.document_id for d in value.visible_documents}
            actual = {frozenset(documents[m] for m in e.member_doc_version_ids) for e in result.events}
            assert actual == {frozenset(g) for g in ref["groups"]}, (timeline, result.cursor.step_id)


def test_T18_same_pool_evaluation_and_tamper_errors(capsys):
    outputs = [output_path() for _ in range(3)]
    for strategy, out in zip(("r0", "r1", "r2"), outputs, strict=True):
        export(out, strategy)
    reference = FIXTURES / "reference/manifest.json"
    evaluation = output_path()
    assert evaluate_runs(outputs, reference_manifest=reference, reference_sha256=pin(reference), out=evaluation)["ok"]
    report = json.loads((evaluation / "metrics.json").read_bytes())
    assert not report["independent_validation"]
    assert report["strategies"]["r0"]["counts"]["fn"] == 1
    assert report["strategies"]["r1"]["counts"]["tp"] == 1
    assert report["strategies"]["r1"]["counts"]["fp"] == 0
    assert report["strategies"]["r0"]["confusion_matrix"] is None
    assert report["strategies"]["r1"]["stability"]["value"] == 1
    loaded = [load_run(p) for p in outputs]
    m, i, r = loaded[0]
    loaded[0] = (m.model_copy(update={"candidate_pool_sha256": "0" * 64}), i, r)
    with pytest.raises(G2Error) as error:
        compare_loaded(loaded, pairs=(), continuity=(), reference_sha256=pin(reference))
    assert (error.value.code, error.value.stage, error.value.field) == (
        "G2_PR2_COMPARISON_POOL_MISMATCH", "evaluation", "candidate_pool_or_runtime")
    (outputs[0] / "events.jsonl").write_bytes(b"tampered\n")
    with pytest.raises(G2Error) as error:
        load_run(outputs[0])
    assert (error.value.code, error.value.stage, error.value.field) == ("SHA_MISMATCH", "evaluation", "artifact")


def test_T18_reference_uncertain_and_zero_denominators_are_not_true_negatives():
    from evals.intelligence_g2.pr2.evaluate import ratio

    assert ratio(0, 0) == {"value": None, "unavailable_reason": "zero_denominator"}
    outputs = [output_path() for _ in range(3)]
    for s, out in zip(("r0", "r1", "r2"), outputs, strict=True):
        export(out, s, "NO_TARGET", "D0")
    ref = FIXTURES / "reference/manifest.json"
    _, pairs, continuity = load_references(ref, pin=pin(ref))
    report, _ = compare_loaded([load_run(o) for o in outputs], pairs=pairs, continuity=continuity,
                               reference_sha256=pin(ref))
    for result in report["strategies"].values():
        assert result["counts"]["reference_uncertain"] == 1
        assert result["counts"]["tn"] == result["counts"]["fp"] == 0
        assert result["precision"]["value"] is None


def test_T17_future_fixture_payload_is_opaque_until_visible(tmp_path):
    raw = [json.loads(line) for line in (FIXTURES / "prediction/inputs.jsonl").read_bytes().splitlines()]
    rows = [r for r in raw if r["context"]["timeline_id"] == "FUTURE"]
    rows[1]["visible_documents"][0]["candidate"]["paragraphs"] = "FUTURE_POISON_INVALID_SHAPE"
    input_bytes = b"".join(json_bytes(row) for row in rows)
    (tmp_path / "inputs.jsonl").write_bytes(input_bytes)
    from evals.intelligence_v1.hashing import sha256_bytes

    manifest = {"format": "g2-pr2-prediction-v1", "record_origin": "synthetic", "files": [
        {"path": "inputs.jsonl", "role": "prediction", "sha256": sha256_bytes(input_bytes)}]}
    path = tmp_path / "manifest.json"
    path.write_bytes(json_bytes(manifest))
    early, _ = load_sequence(path, pin=pin(path), timeline_id="FUTURE", through_step="D0")
    assert "POISON" not in early[0].model_dump_json()
    from .support import run

    assert run(early)[1][0].validation.ok
    with pytest.raises(G2Error) as error:
        load_sequence(path, pin=pin(path), timeline_id="FUTURE", through_step="D8")
    assert error.value.code == "SCHEMA_INVALID"


@pytest.mark.parametrize("paragraphs", ["FUTURE_POISON_INVALID_SHAPE", {"poison": "future"}])
def test_review_current_step_future_candidate_precedes_body_parsing(
        tmp_path, monkeypatch, capsys, paragraphs):
    from datetime import timedelta

    from evals.intelligence_g2.contracts import G2ReplayInput, data
    from evals.intelligence_g2.pr2 import replay
    from evals.intelligence_v1.hashing import sha256_bytes

    from .support import make_input

    value = make_input([{"id": "a"}])
    row = data(value)
    row["visible_documents"][0]["candidate"]["available_at"] = (
        value.context.as_of + timedelta(days=1)).isoformat()
    row["visible_documents"][0]["candidate"]["paragraphs"] = paragraphs
    raw = json_bytes(row)
    (tmp_path / "inputs.jsonl").write_bytes(raw)
    path = tmp_path / "manifest.json"
    path.write_bytes(json_bytes({"format": "g2-pr2-prediction-v1", "record_origin": "synthetic",
        "files": [{"path": "inputs.jsonl", "role": "prediction", "sha256": sha256_bytes(raw)}]}))
    parsed = []
    predicted = []
    original_parse = replay.parse

    def observed_parse(model, payload, **kwargs):
        if model is G2ReplayInput:
            parsed.append(model)
        return original_parse(model, payload, **kwargs)

    def forbidden_prediction(**kwargs):
        predicted.append(kwargs)
        raise AssertionError("future candidate reached prediction")

    monkeypatch.setattr(replay, "parse", observed_parse)
    monkeypatch.setattr(replay, "run_grouping_step", forbidden_prediction)
    with pytest.raises(G2Error) as error:
        load_sequence(path, pin=pin(path), timeline_id=value.context.timeline_id,
                      through_step=value.context.step_id)
    assert (error.value.code, error.value.stage, error.value.field, error.value.record_id) == (
        "FUTURE_VERSION", "bridge", "candidate.available_at", "a:1")
    assert parsed == predicted == []
    output = output_path()
    assert main(args(output, timeline=value.context.timeline_id,
                     last=value.context.step_id, manifest=path)) == 1
    issue = json.loads(capsys.readouterr().out)["errors"][0]
    assert (issue["code"], issue["stage"], issue["field"], issue["record_id"]) == (
        "FUTURE_VERSION", "bridge", "candidate.available_at", "a:1")
    assert parsed == predicted == []
    assert not output.exists()


@pytest.mark.parametrize("target,code", [("manifest", "MANIFEST_SHA_MISMATCH"),
                                       ("config", "CONFIG_SHA_MISMATCH")])
def test_T18_wrong_pin_never_writes(target, code, capsys):
    output = output_path()
    argv = args(output)
    option = "--manifest-sha256" if target == "manifest" else "--config-sha256"
    argv[argv.index(option) + 1] = "0" * 64
    assert main(argv) == 1
    issue = json.loads(capsys.readouterr().out)["errors"][0]
    assert issue["code"] == code and issue["field"] == target
    assert not output.exists()


def test_T18_existing_output_and_atomic_failure(capsys, monkeypatch):
    output = output_path()
    original = Path.open

    def fail_events(self, *args, **kwargs):
        if self.name == "events.jsonl" and args and args[0] == "xb":
            raise OSError("synthetic staging failure")
        return original(self, *args, **kwargs)

    with monkeypatch.context() as scoped:
        scoped.setattr(Path, "open", fail_events)
        assert main(args(output)) == 1
    assert json.loads(capsys.readouterr().out)["errors"][0]["code"] == "EXPORT_IO_ERROR"
    assert not output.exists()
    assert not list(output.parent.glob("." + output.name + ".staging-*"))
    export(output)
    before = {p.name: p.read_bytes() for p in output.iterdir()}
    assert main(args(output)) == 1
    assert json.loads(capsys.readouterr().out)["errors"][0]["code"] == "OUTPUT_EXISTS"
    assert before == {p.name: p.read_bytes() for p in output.iterdir()}


def test_T18_forbidden_output_and_argument_errors(capsys):
    for target in (ROOT / "evals/intelligence_g2/escape", ROOT / ".tmp/evals/g2/../escape",
                   ROOT / ".local/escape", ROOT / ".tmp/evals/g2/.env"):
        assert main(args(target)) == 1
        assert json.loads(capsys.readouterr().out)["errors"][0]["code"] == "OUTPUT_PATH_INVALID"
    with pytest.raises(SystemExit) as error:
        main([])
    assert error.value.code == 2


def test_T18_reference_conflicts_are_diagnostics_not_prediction_inputs(tmp_path):
    from evals.intelligence_g2.pr2.contracts import ReferenceManifest
    from evals.intelligence_v1.hashing import sha256_bytes

    source = FIXTURES / "reference/manifest.json"
    header = json.loads(source.read_bytes())
    rows = (FIXTURES / "reference/pairs.jsonl").read_bytes().splitlines()
    rows = rows[:1] * 2
    content = b"\n".join(rows) + b"\n"
    (tmp_path / "pairs.jsonl").write_bytes(content)
    (tmp_path / "continuity.jsonl").write_bytes(b"")
    header.update(pairs_sha256=sha256_bytes(content), continuity_sha256=sha256_bytes(b""))
    path = tmp_path / "manifest.json"
    path.write_bytes(json_bytes(ReferenceManifest.model_validate_json(json.dumps(header))))
    with pytest.raises(G2Error) as error:
        load_references(path, pin=pin(path))
    assert (error.value.code, error.value.stage, error.value.field) == (
        "G2_PR2_REFERENCE_CONFLICT", "evaluation", "reference_pairs")
