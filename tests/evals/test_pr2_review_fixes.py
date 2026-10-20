"""Independent PR2 review regressions; temporary probes are never human results."""

import json
import subprocess
import sys

import pytest
from conftest import refresh
from test_annotation_records import probe, records, save

from evals.intelligence_v1.hashing import sha256_bytes
from evals.intelligence_v1.validate import validate_dataset


def cli(manifest, pin, out, *extra):
    return subprocess.run([
        sys.executable, "-B", "-m", "evals.intelligence_v1.replay", "--manifest", str(manifest),
        "--manifest-sha256", pin, "--timeline", "DEV-01", "--dry-run", "--out", str(out), *extra,
    ], capture_output=True, text=True, timeout=25)


@pytest.mark.parametrize("reverse,relation", [(True, "unrelated"), (True, "syndicated"),
                                             (False, "unrelated")])
def test_R1_annotation_pair_and_instant_is_unique_without_rewriting(bundle, reverse, relation):
    row = probe(bundle, step_index=1)
    first = records(bundle, "events/event_relations.jsonl")[0]
    second = {**first, "relation": relation}
    if reverse:
        second.update(left_doc_version_id=first["right_doc_version_id"],
                      right_doc_version_id=first["left_doc_version_id"])
    row["initial_label"]["document_relations"] = [first, second]
    save(bundle, "labels/annotations.jsonl", [row])
    manifest = refresh(bundle)
    raw = (bundle / "labels/annotations.jsonl").read_bytes()
    report = validate_dataset(manifest, strict=False)
    assert [(e.code, e.field) for e in report.errors] == [("DUPLICATE_ID", "document_relations")]
    assert (bundle / "labels/annotations.jsonl").read_bytes() == raw


def test_R1_pair_at_different_instants_or_in_different_submissions_is_allowed(bundle):
    first = records(bundle, "events/event_relations.jsonl")[0]
    later = {**first, "evidence_at": "2026-01-02T12:00:01Z", "relation": "uncertain"}
    a, b = probe(bundle, step_index=2), probe(bundle, "contract-probe-b", step_index=2)
    a["initial_label"]["document_relations"] = [first, later]
    b["initial_label"]["document_relations"] = [first]
    save(bundle, "labels/annotations.jsonl", [a, b])
    assert validate_dataset(refresh(bundle)).ok


def adjudication_probe(bundle, status):
    a, b = probe(bundle), probe(bundle, "contract-probe-b")
    save(bundle, "labels/annotations.jsonl", [a, b])
    label = dict(record_origin="synthetic", provenance_uri="DEV-01/README.md",
        timeline_id="DEV-01", step_id="D0", persona_version_id=a["persona_version_id"],
        event_id="d01:event:release", annotation_version="synthetic-fixture-v1", relevance=0,
        potential_value=0, novelty_to_persona=0, evidence_quality=0, graded_relevance=0,
        material_change="insufficient", tier="hold", supporting_doc_version_ids=["d01:a:1"],
        rationale="Temporary contract probe, not a human judgment.", uncertainty=["Probe only"],
        adjudication_status=status)
    save(bundle, "labels/gold.jsonl", [label])
    result = dict(adjudication_id="contract-probe", prior_annotation_ids=[a["annotation_id"],
        b["annotation_id"]], final_label=label, reason="Temporary contract probe",
        adjudicator_id="contract-probe-c", adjudicated_at="2026-10-20T01:00:00Z")
    save(bundle, "labels/adjudications.jsonl", [result])
    return refresh(bundle)


@pytest.mark.parametrize("status", ["adjudicated", "unresolved"])
def test_R2_resolved_and_unresolved_records_are_valid_but_not_human_confirmation(bundle, status):
    manifest = adjudication_probe(bundle, status)
    before = (bundle / "labels/gold.jsonl").read_bytes()
    report = validate_dataset(manifest, strict=False)
    assert report.ok, report.to_dict()
    assert "independent_annotation" in report.pending and "claim_semantic_support" in report.pending
    assert ("unresolved_adjudication" in report.pending) == (status == "unresolved")
    assert (bundle / "labels/gold.jsonl").read_bytes() == before


def test_R2_unresolved_still_requires_matching_stored_gold(bundle):
    adjudication_probe(bundle, "unresolved")
    gold = records(bundle, "labels/gold.jsonl")
    gold[0]["adjudication_status"] = "adjudicated"
    save(bundle, "labels/gold.jsonl", gold)
    report = validate_dataset(refresh(bundle), strict=False)
    assert any(e.code == "REFERENCE_NOT_FOUND" and e.field == "final_label" for e in report.errors)


def test_R3_help_is_available_without_local_scripts():
    result = subprocess.run([sys.executable, "-B", "-m", "evals.intelligence_v1.replay", "--help"],
                            capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr
    assert "--manifest-sha256" in result.stdout and "--dry-run" in result.stdout
    assert "--algo" not in result.stdout


def test_R3_export_is_pinned_deterministic_and_does_not_copy_reference_answers(bundle, tmp_path):
    manifest = refresh(bundle)
    pin = sha256_bytes(manifest.read_bytes())
    outputs = [tmp_path / "export-a", tmp_path / "export-b"]
    for out in outputs:
        result = cli(manifest, pin, out)
        assert result.returncode == 0, result.stderr + result.stdout
    def files(out):
        return {p.relative_to(out).as_posix(): p.read_bytes() for p in out.rglob("*") if p.is_file()}
    a, b = map(files, outputs)
    assert a == b
    visible = [json.loads(line) for line in a["visible_steps.jsonl"].splitlines()]
    assert [v["step_id"] for v in visible] == ["D0", "D1", "D3", "D4", "D5", "D8"]
    early = a["packets/D0/packet.json"]
    assert [d["doc_version_id"] for d in json.loads(early)["documents"]] == ["d01:a:1"]
    for forbidden in (b"verification_state", b"family_id", b"CORRECTION", b"TinyBench-3"):
        assert forbidden not in early
    assert all(not p.endswith(("gold.jsonl", "annotations.jsonl", "adjudications.jsonl",
                               "predictions.jsonl", "metrics.json")) for p in a)
    assert json.loads(a["run_metadata.json"])["manifest_sha256"] == pin


def test_R3_single_step_export_does_not_deliver_future_steps(bundle, tmp_path):
    manifest = refresh(bundle)
    out = tmp_path / "one"
    result = cli(manifest, sha256_bytes(manifest.read_bytes()), out, "--step", "D0")
    assert result.returncode == 0, result.stderr + result.stdout
    assert {p.name for p in (out / "packets").iterdir()} == {"D0"}
    assert len((out / "visible_steps.jsonl").read_bytes().splitlines()) == 1


@pytest.mark.parametrize("case,code", [("bad-pin", "MANIFEST_SHA_MISMATCH"),
                                      ("tamper", "SHA_MISMATCH")])
def test_R3_invalid_inputs_fail_before_creating_output(bundle, tmp_path, case, code):
    manifest = refresh(bundle)
    pin = sha256_bytes(manifest.read_bytes())
    if case == "bad-pin":
        pin = "0" * 64
    else:
        target = bundle / "versions/documents.jsonl"
        target.write_bytes(target.read_bytes() + b" ")
    out = tmp_path / "must-not-exist"
    result = cli(manifest, pin, out)
    assert result.returncode == 1
    assert code in result.stdout and "Traceback" not in result.stderr
    assert not out.exists()


def test_R3_does_not_overwrite_existing_output_or_accept_ranking_flags(bundle, tmp_path):
    manifest = refresh(bundle)
    out = tmp_path / "existing"
    out.mkdir()
    (out / "mine.txt").write_bytes(b"preserve")
    pin = sha256_bytes(manifest.read_bytes())
    result = cli(manifest, pin, out)
    assert result.returncode == 1 and "OUTPUT_EXISTS" in result.stdout
    assert list(out.iterdir()) == [out / "mine.txt"]
    rejected = cli(manifest, pin, tmp_path / "ranking", "--algo", "b0")
    assert rejected.returncode == 2 and not (tmp_path / "ranking").exists()


def test_R3_export_has_no_network_business_import_or_outside_data_access(bundle, tmp_path):
    manifest = refresh(bundle)
    pin = sha256_bytes(manifest.read_bytes())
    out = tmp_path / "audited-export"
    script = r'''
import os, sys
from pathlib import Path
from evals.intelligence_v1.replay import main
root, out = Path(sys.argv[1]).resolve(), Path(sys.argv[3]).resolve()
runtime = [Path(sys.prefix).resolve(), Path(sys.base_prefix).resolve()]
def guard(event, args):
    if event.startswith('socket.'):
        raise AssertionError('network attempted')
    if event == 'open' and isinstance(args[0], (str, bytes)):
        target = Path(args[0]).resolve()
        assert not any(p.casefold().startswith('.env') or p.casefold().endswith('.db')
                       for p in target.parts), 'sensitive data access'
        flags = args[2]
        if flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND):
            assert target.is_relative_to(out), 'outside write'
        else:
            code = (target.suffix in {'.py', '.pyc', '.pyd'}
                    and any(target.is_relative_to(p) for p in runtime))
            assert target.is_relative_to(root) or code, 'outside data read'
sys.addaudithook(guard)
status = main(['--manifest', str(root/'manifests/dataset_manifest.json'),
               '--manifest-sha256', sys.argv[2], '--timeline', 'DEV-01',
               '--dry-run', '--step', 'D0', '--out', str(out)])
assert not any(m.startswith('cfaw_news.') for m in sys.modules)
sys.exit(status)
'''
    result = subprocess.run([sys.executable, "-B", "-c", script, str(bundle), pin, str(out)],
                            capture_output=True, text=True, timeout=25)
    assert result.returncode == 0, result.stderr + result.stdout
