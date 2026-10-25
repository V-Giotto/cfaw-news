import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from evals.intelligence_g2.contracts import G2Error
from evals.intelligence_g2.replay import main, output_location
from evals.intelligence_v1.hashing import sha256_bytes

from .support import CONFIG, ROOT, assert_error, cli_args, copied_bundle, output_path


def invoke(args, *, seed="1"):
    return subprocess.run([sys.executable, "-B", "-m", "evals.intelligence_g2.replay", *args],
        cwd=ROOT, env={**os.environ, "PYTHONHASHSEED": seed}, capture_output=True,
        text=True, encoding="utf-8", timeout=40)


def test_G2_T04_cli_canonical_bytes_across_hash_seeds_and_manifest(capsys):
    outputs = [output_path(), output_path()]
    for out, seed in zip(outputs, ("1", "719"), strict=True):
        completed = invoke(cli_args(out), seed=seed)
        assert completed.returncode == 0, completed.stderr + completed.stdout
        summary = json.loads(completed.stdout)
        manifest = json.loads((out / "run_manifest.json").read_bytes())
        assert summary["run_manifest_sha256"] == sha256_bytes((out / "run_manifest.json").read_bytes())
        assert summary["trace_sha256"] == sha256_bytes((out / "trace.json").read_bytes())
        trace = json.loads((out / "trace.json").read_bytes())
        assert trace["run_manifest_sha256"] == summary["run_manifest_sha256"]
        assert trace["model_calls"] == trace["token_usage"] == trace["model_cost"] == 0
        assert trace["usage_reason"] == "not_called" and trace["model_id"] is None
        assert manifest["validation_scope"] == "pr1_contract_skeleton"
        assert len(manifest["dependency_lock_sha256"]) == 2
        for artifact in manifest["artifacts"]:
            raw = (out / artifact["path"]).read_bytes()
            assert artifact["sha256"] == sha256_bytes(raw)
            assert artifact["byte_count"] == len(raw)
            if artifact["record_count"] is not None:
                assert artifact["record_count"] == len(raw.splitlines())
            assert not raw.startswith(b"\xef\xbb\xbf") and b"\r" not in raw
            assert not raw or raw.endswith(b"\n")
        result = json.loads((out / "result.json").read_bytes())
        for name in ("events", "relations", "bundles", "items"):
            assert result[name] == [json.loads(line) for line in
                                    (out / (name + ".jsonl")).read_bytes().splitlines()]
        assert (out / "relations.jsonl").read_bytes() == b""
    for path in outputs[0].iterdir():
        if path.name != "trace.json":
            assert path.read_bytes() == (outputs[1] / path.name).read_bytes(), path.name
    assert main(cli_args(outputs[0])) == 1
    report = json.loads(capsys.readouterr().out)
    assert report["errors"][0]["code"] == "OUTPUT_EXISTS"


@pytest.mark.parametrize("target,code", [("manifest", "MANIFEST_SHA_MISMATCH"),
    ("documents", "SHA_MISMATCH"), ("config", "CONFIG_SHA_MISMATCH")])
def test_G2_T05_one_byte_tamper_never_refreshes_or_writes(tmp_path, capsys, target, code):
    root = copied_bundle(tmp_path)
    out = output_path()
    config = tmp_path / "config.json"
    config.write_bytes(CONFIG.read_bytes())
    args = cli_args(out, root, config=config)
    path = {"manifest": root / "manifests/dataset_manifest.json",
            "documents": root / "versions/documents.jsonl", "config": config}[target]
    path.write_bytes(path.read_bytes() + b" ")
    tampered = path.read_bytes()
    assert main(args) == 1
    report = json.loads(capsys.readouterr().out)
    assert report["errors"][0]["code"] == code
    assert path.read_bytes() == tampered
    assert not out.exists()


def test_G2_T01_future_candidate_rejected_before_pipeline_or_write(tmp_path, capsys, monkeypatch):
    from evals.intelligence_g2 import replay
    from evals.intelligence_g2.contracts import json_bytes

    from .support import refresh_copy, rows, save_rows

    root = copied_bundle(tmp_path)
    # Contradict the pinned step's as_of. The loader rejects the purported future candidate set.
    steps = rows(root, "timelines/steps.jsonl")
    step = next(s for s in steps if s["timeline_id"] == "DEV-01" and s["step_id"] == "D0")
    step["visible_doc_version_ids"].append("d01:a:2")
    save_rows(root, "timelines/steps.jsonl", steps)
    refresh_copy(root)
    calls = []
    monkeypatch.setattr(replay, "run_g2_offline", lambda **kwargs: calls.append(kwargs))
    out = output_path()
    assert main(cli_args(out, root)) == 1
    assert json.loads(capsys.readouterr().out)["errors"][0]["code"] == "VISIBLE_SET_MISMATCH"
    assert calls == [] and not out.exists()
    assert json_bytes({"ok": False}).endswith(b"\n")


def test_G2_T10_io_failure_never_publishes_partial_result(capsys, monkeypatch):
    out = output_path()
    original = Path.open

    def failing(self, *args, **kwargs):
        if self.name == "items.jsonl" and self.parent.name.startswith("." + out.name + ".staging-"):
            raise OSError("PRIVATE_ERROR_PAYLOAD_MUST_NOT_BE_PRINTED")
        return original(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", failing)
    assert main(cli_args(out)) == 1
    stdout = capsys.readouterr().out
    assert json.loads(stdout)["errors"][0]["code"] == "EXPORT_IO_ERROR"
    assert "PRIVATE_ERROR_PAYLOAD" not in stdout
    assert not out.exists()
    assert not list(out.parent.glob("." + out.name + ".staging-*"))


@pytest.mark.parametrize("target", [ROOT / "evals/intelligence_v1/rejected",
    ROOT / ".local/rejected", ROOT / "dev-diaries/rejected", ROOT / ".env/rejected",
    ROOT / ".tmp/evals/g2/../escaped", ROOT / ".tmp/evals/g2/test.db"])
def test_G2_T10_output_path_escape_is_rejected(target):
    with pytest.raises(G2Error) as caught:
        output_location(target)
    assert_error(caught, "OUTPUT_PATH_INVALID", "export", "path")


def test_G2_T10_reparse_output_ancestor_is_rejected(tmp_path, monkeypatch, request):
    from evals.intelligence_g2.replay import OUTPUT_BASE

    link = OUTPUT_BASE / "tests" / ("link-" + tmp_path.name)
    link.parent.mkdir(parents=True, exist_ok=True)
    # Junctions can be created without symlink privileges on Windows.
    native = True
    if os.name == "nt":
        result = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(tmp_path)],
                                capture_output=True, timeout=10)
        if result.returncode:
            # The sandbox can forbid junction creation. Still test the exact Windows flag path.
            import stat
            from types import SimpleNamespace

            native = False
            link.mkdir()
            original = Path.lstat

            def flagged(self, *args, **kwargs):
                info = original(self, *args, **kwargs)
                if self == link:
                    return SimpleNamespace(st_mode=info.st_mode,
                        st_file_attributes=stat.FILE_ATTRIBUTE_REPARSE_POINT)
                return info

            monkeypatch.setattr(Path, "lstat", flagged)
    else:
        link.symlink_to(tmp_path, target_is_directory=True)
    try:
        request.node.user_properties.append(("reparse_test_mode",
            "native_junction" if native else "synthetic_lstat_flag"))
        with pytest.raises(G2Error) as caught:
            output_location(link / "escape")
        assert_error(caught, "OUTPUT_PATH_INVALID", "export", "path")
    finally:
        if os.name == "nt":
            link.rmdir()  # The junction itself only; never recurse into its destination.
        else:
            link.unlink()


def test_G2_T10_missing_cli_arguments_exit_2():
    result = invoke([])
    assert result.returncode == 2
    assert "--manifest" in result.stderr


def test_G2_T05_config_rejects_duplicate_json_keys(tmp_path, capsys):
    config = tmp_path / "duplicate.json"
    config.write_bytes(b'{"max_quote_chars":160,"max_quote_chars":160}\n')
    out = output_path()
    assert main(cli_args(out, config=config)) == 1
    assert json.loads(capsys.readouterr().out)["errors"][0]["code"] == "INVALID_JSON"
    assert not out.exists()
