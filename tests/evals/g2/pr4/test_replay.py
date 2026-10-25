"""T36: frozen prefix replay, failure atomicity, deterministic bytes and role isolation."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from evals.intelligence_g2.contracts import ROOT, data, digest, json_bytes
from evals.intelligence_g2.pr4.contracts import PR4Config
from evals.intelligence_g2.pr4.evaluate import evaluate_run, load_item_run
from evals.intelligence_g2.pr4.replay import main, run_sequence

from ..pr2.support import merge_split_steps, sequence
from ..pr3.support import evidence_for
from ..support import output_path
from .support import CONFIG, FIXTURE, export_evidence, pin, replay_values, run
from .test_items import rejected


def args(parent, output, last="D8"):
    return ["--evidence-run", str(parent), "--evidence-manifest-sha256", pin(parent / "run_manifest.json"),
        "--through-step", last, "--config", str(CONFIG), "--config-sha256", pin(CONFIG), "--out", str(output)]


def test_T36_cli_seed_prefix_snapshot_immutability_and_independent_evaluation(tmp_path, capsys):
    parent = export_evidence(tmp_path)
    outputs = [output_path() for _ in range(3)]
    for seed, out in zip((1, 719), outputs[:2], strict=True):
        result = subprocess.run([sys.executable, "-B", "-m", "evals.intelligence_g2.pr4.replay", *args(parent, out)],
            cwd=ROOT, env={**os.environ, "PYTHONHASHSEED": str(seed)}, capture_output=True,
            text=True, encoding="utf-8", timeout=60)
        assert result.returncode == 0, result.stdout + result.stderr
    before = {p.name: pin(p) for p in outputs[0].iterdir()}
    for p in outputs[0].iterdir():
        if p.name != "trace.json":
            assert p.read_bytes() == (outputs[1] / p.name).read_bytes(), p.name
    assert main(args(parent, outputs[2], "D0")) == 0
    assert json.loads(capsys.readouterr().out)["ok"]
    for p in outputs[0].glob("*.jsonl"):
        assert p.read_bytes().splitlines()[0] == (outputs[2] / p.name).read_bytes().splitlines()[0]
    trace = json.loads((outputs[0] / "trace.json").read_bytes())
    assert trace["model_calls"] == trace["token_usage"] == trace["model_cost"] == 0
    assert trace["usage_reason"] == "not_called"
    manifest, rows = load_item_run(outputs[0], pin(outputs[0] / "run_manifest.json"))
    assert len(rows) == 2 and manifest.through_step == "D8"
    reference = FIXTURE / "reference/manifest.json"
    result = evaluate_run(outputs[0], run_manifest_sha256=pin(outputs[0] / "run_manifest.json"),
        reference_manifest=reference, reference_sha256=pin(reference), out=output_path())
    assert result["ok"] and result["errors"] == 0
    assert before == {p.name: pin(p) for p in outputs[0].iterdir()}


def test_T36_candidate_order_request_bytes_and_same_content_snapshots():
    inputs = replay_values("T29")
    reversed_input = inputs[0].model_copy(update={"visible_documents": tuple(reversed(inputs[0].visible_documents)),
        "sources": tuple(reversed(inputs[0].sources)), "identity_seeds": tuple(reversed(inputs[0].identity_seeds))})
    a, b = [run_sequence(*evidence_for(v), config=PR4Config()) for v in (inputs, [reversed_input])]
    assert data(a[0][0]) == data(b[0][0])
    assert data(a[1][0]) == data(b[1][0])
    _, rows = run("T36")
    assert rows[0].items[0].item_id == rows[1].items[0].item_id
    assert rows[0].items[0].fact_revision == rows[1].items[0].fact_revision
    assert rows[0].snapshots[0].snapshot_id != rows[1].snapshots[0].snapshot_id
    assert rows[1].snapshots[0].change_signal == "same_content_observed"
    assert rows[1].next_state.snapshots[:1] == rows[0].next_state.snapshots


@pytest.mark.parametrize("option,code,field", [("--config-sha256", "CONFIG_SHA_MISMATCH", "config"),
    ("--evidence-manifest-sha256", "MANIFEST_SHA_MISMATCH", "evidence_manifest")])
def test_wrong_pin_rejects_before_writing(tmp_path, capsys, option, code, field):
    parent = export_evidence(tmp_path)
    out = output_path()
    argv = args(parent, out)
    argv[argv.index(option) + 1] = "0" * 64
    assert main(argv) == 1
    issue = json.loads(capsys.readouterr().out)["errors"][0]
    assert (issue["code"], issue["stage"], issue["field"]) == (code, "input", field)
    assert not out.exists()


def test_atomic_write_failure_and_no_overwrite(tmp_path, monkeypatch, capsys):
    parent, out = export_evidence(tmp_path), output_path()
    original = Path.open
    def fail_write(self, *argv, **kw):
        if self.name == "items.jsonl" and argv and argv[0] == "xb":
            raise OSError("synthetic failure")
        return original(self, *argv, **kw)
    with monkeypatch.context() as scoped:
        scoped.setattr(Path, "open", fail_write)
        assert main(args(parent, out)) == 1
    assert json.loads(capsys.readouterr().out)["errors"][0]["code"] == "EXPORT_IO_ERROR"
    assert not out.exists() and not list(out.parent.glob("." + out.name + ".staging-*"))
    assert main(args(parent, out)) == 0
    capsys.readouterr()
    before = {p.name: pin(p) for p in out.iterdir()}
    assert main(args(parent, out)) == 1
    assert json.loads(capsys.readouterr().out)["errors"][0]["code"] == "OUTPUT_EXISTS"
    assert before == {p.name: pin(p) for p in out.iterdir()}


def refresh(parent, changed):
    manifest = json.loads((parent / "run_manifest.json").read_bytes())
    for name, raw in changed.items():
        (parent / name).write_bytes(raw)
        entry = next(v for v in manifest["artifacts"] if v["path"] == name)
        entry.update(sha256=pin(parent / name), byte_count=len(raw), record_count=len(raw.splitlines()))
    (parent / "run_manifest.json").write_bytes(json_bytes(manifest))


def test_future_parent_record_opaque_until_selected_and_current_future_ref_preflight(tmp_path, capsys):
    parent = export_evidence(tmp_path)
    rows = [json.loads(line) for line in (parent / "citations.jsonl").read_bytes().splitlines()]
    rows[1]["citations"][0]["quote"] = {"future": "POISON"}
    refresh(parent, {"citations.jsonl": b"".join(json_bytes(v) for v in rows)})
    out = output_path()
    assert main(args(parent, out, "D0")) == 0
    capsys.readouterr()
    assert b"POISON" not in (out / "items.jsonl").read_bytes()
    out = output_path()
    assert main(args(parent, out)) == 1
    assert json.loads(capsys.readouterr().out)["errors"][0]["code"] == "SCHEMA_INVALID"
    assert not out.exists()
    rows[0]["citations"][0].update(available_at=rows[1]["cursor"]["as_of"], quote={"invalid": True})
    refresh(parent, {"citations.jsonl": b"".join(json_bytes(v) for v in rows)})
    out = output_path()
    assert main(args(parent, out, "D0")) == 1
    issue = json.loads(capsys.readouterr().out)["errors"][0]
    assert (issue["code"], issue["stage"], issue["field"], issue["record_id"]) == (
        "FUTURE_VERSION", "temporal", "available_at", "a:1")
    assert not out.exists()


def test_reference_role_refused_and_output_tamper_detected(tmp_path, capsys):
    parent = export_evidence(tmp_path)
    out = output_path()
    assert main(args(parent, out)) == 0
    capsys.readouterr()
    (out / "items.jsonl").write_bytes(b"tampered\n")
    rejected(lambda: load_item_run(out, pin(out / "run_manifest.json")), "SHA_MISMATCH", "evaluation", "artifact", "items.jsonl")
    manifest = json.loads((parent / "run_manifest.json").read_bytes())
    manifest["artifacts"].append(dict(path="reference/answers.json", sha256="0" * 64, byte_count=1, record_count=None))
    (parent / "run_manifest.json").write_bytes(json_bytes(manifest))
    out = output_path()
    assert main(args(parent, out)) == 1
    issue = json.loads(capsys.readouterr().out)["errors"][0]
    assert (issue["code"], issue["stage"], issue["field"]) == ("PREDICTION_PATH_INVALID", "input", "parent_artifact")
    assert not out.exists()


def test_snapshot_state_tamper_and_cross_namespace_rejected():
    from evals.intelligence_g2.pr4.pipeline import generate_items

    values, _ = run("T36")
    v = values[1]
    for name, replacement in (("namespace", "0" * 64), ("previous_state_sha256", "0" * 64)):
        rejected(lambda: generate_items(generation_input=v.model_copy(update={name: replacement}), config=PR4Config()),
            "G2_PR4_SNAPSHOT_CHAIN_INVALID", "history", "previous_state")
    prior = v.previous_state
    snapshot = prior.snapshots[0].model_copy(update={"previous_snapshot_ids": ("missing",)})
    prior = prior.model_copy(update={"snapshots": (snapshot,)})
    bad = v.model_copy(update={"previous_state": prior, "previous_state_sha256": digest(prior)})
    rejected(lambda: generate_items(generation_input=bad, config=PR4Config()),
        "G2_PR4_SNAPSHOT_CHAIN_INVALID", "history", "snapshot.previous_snapshot_ids", snapshot.snapshot_id)


@pytest.mark.parametrize("strategy", ["r0", "r1", "r2"])
def test_cross_PR_identity_merge_split_compatibility(strategy):
    parents, evidence = evidence_for(sequence(merge_split_steps()), strategy=strategy)
    _, rows = run_sequence(parents, evidence, config=PR4Config())
    assert len(rows) == 3
    for parent, result in zip(evidence, rows, strict=True):
        assert {(i.event_key, i.event_revision) for i in result.items} == {(b.event_key, b.event_revision) for b in parent.bundles}
    assert rows[-1].next_state.snapshots[:len(rows[0].snapshots)] == rows[0].snapshots
    if strategy != "r0":
        assert set(rows[1].snapshots[0].previous_snapshot_ids) == {s.snapshot_id for s in rows[0].snapshots}
        assert rows[1].snapshots[0].change_signal == "identity_transition"
        assert all(s.previous_snapshot_ids and s.change_signal == "identity_transition" for s in rows[2].snapshots)


def test_path_escape_rejected_without_external_write(tmp_path, capsys):
    parent = export_evidence(tmp_path)
    for out in (ROOT / "backend/forbidden-pr4", ROOT / ".tmp/evals/g2/../escape"):
        assert main(args(parent, out)) == 1
        issue = json.loads(capsys.readouterr().out)["errors"][0]
        assert issue["code"] == "OUTPUT_PATH_INVALID"
        assert not out.exists()


def test_T36_audited_prediction_no_reference_or_private_access(tmp_path):
    parent = export_evidence(tmp_path)
    meta = json.loads((parent / "run_manifest.json").read_bytes())
    group = ROOT / meta["parent_run_path"]
    out = output_path()
    out.parent.mkdir(parents=True, exist_ok=True)
    canary = tmp_path / "canary.db"
    canary.write_bytes(b"synthetic canary")
    before = canary.read_bytes()
    script = r'''
import os,sys
from pathlib import Path
from evals.intelligence_g2.pr4.replay import main
from evals.intelligence_g2.contracts import ROOT,PACKAGE
parent,group,out,config=map(Path,(sys.argv[1],sys.argv[2],sys.argv[3],sys.argv[5]))
runtime=[Path(sys.prefix).resolve(),Path(sys.base_prefix).resolve()]
original_stat,original_lstat=Path.stat,Path.lstat
def sensitive(path):
    path=Path(path)
    assert not any(p.lower() in {'reference','reviews','labels','annotations','adjudications','.local','dev-diaries'}
        or p.lower().startswith('.env') or p.lower().endswith(('.db','.db-wal','.db-shm')) for p in path.parts), 'private/reference'
    if path.is_relative_to(ROOT/'evals/intelligence_v1'):
        assert path.name not in {'event_relations.jsonl','events.jsonl','claims.jsonl'}, 'G1 gold'
def stat(self,*a,**k): sensitive(self);return original_stat(self,*a,**k)
def lstat(self,*a,**k): sensitive(self);return original_lstat(self,*a,**k)
Path.stat,Path.lstat=stat,lstat
def writable(p):
    return p==out or p.is_relative_to(out) or (p.parent==out.parent and p.name.startswith('.'+out.name+'.staging-')) or (p.parent.parent==out.parent and p.parent.name.startswith('.'+out.name+'.staging-'))
def audit(event,args):
    if event.startswith('socket.'):raise AssertionError('network')
    if event=='open' and isinstance(args[0],(str,bytes)):
        p=Path(args[0]).absolute();sensitive(p)
        if args[2] & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND):
            assert writable(p), 'outside write'
        else:
            code=p.suffix in {'.py','.pyc','.pyd'} and (p.is_relative_to(ROOT/'evals') or p==ROOT/'backend/cfaw_news/retrieval.py' or any(p.is_relative_to(r) for r in runtime))
            allowed=p.is_relative_to(parent) or p.is_relative_to(group) or p.is_relative_to(PACKAGE/'schema') or p in {config,ROOT/'requirements.lock',ROOT/'frontend/package-lock.json'}
            assert code or allowed, 'outside read'
    if event=='os.rename':assert writable(Path(args[0])) and Path(args[1])==out
sys.addaudithook(audit)
status=main(['--evidence-run',str(parent),'--evidence-manifest-sha256',sys.argv[4], '--through-step','D8',
    '--config',str(config),'--config-sha256',sys.argv[6],'--out',str(out)])
assert not {'evals.intelligence_v1.oracle','evals.intelligence_v1.evaluate','evals.intelligence_v1.validate',
    'evals.intelligence_g2.pr2.evaluate','evals.intelligence_g2.pr2.reference_loader',
    'evals.intelligence_g2.pr3.evaluate','evals.intelligence_g2.pr3.reference_loader',
    'evals.intelligence_g2.pr4.evaluate','evals.intelligence_g2.pr4.reference_loader'} & set(sys.modules)
assert not any(m.startswith('cfaw_news.') and m!='cfaw_news.retrieval' for m in sys.modules)
sys.exit(status)
'''
    result = subprocess.run([sys.executable, "-B", "-c", script, str(parent), str(group), str(out),
        pin(parent / "run_manifest.json"), str(CONFIG), pin(CONFIG)], cwd=ROOT, capture_output=True,
        text=True, encoding="utf-8", timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout)["ok"]
    assert before == canary.read_bytes()


def test_evaluation_reference_pin_and_zero_denominator_are_honest(tmp_path, capsys):
    from evals.intelligence_g2.pr4.evaluate import ratio

    assert ratio(0, 0) == dict(numerator=0, denominator=0, value=None, unavailable_reason="zero_denominator")
    parent, out = export_evidence(tmp_path), output_path()
    assert main(args(parent, out)) == 0
    capsys.readouterr()
    reference = FIXTURE / "reference/manifest.json"
    rejected(lambda: evaluate_run(out, run_manifest_sha256=pin(out / "run_manifest.json"),
        reference_manifest=reference, reference_sha256="0" * 64, out=output_path()),
        "MANIFEST_SHA_MISMATCH", "evaluation", "reference_manifest")
