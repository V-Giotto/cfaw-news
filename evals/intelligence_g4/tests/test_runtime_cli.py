"""Exact-byte CLI artifacts and explicit rejected input; no external effects."""

import hashlib
import json
import os
import subprocess
import sys

import pytest

from .runtime_support import envelope, wire


@pytest.mark.parametrize("kind", ["synthetic", "real", "hold", "future", "old-config"])
def test_cli_stage_file_pins_and_failures(tmp_path, kind):
    value = envelope("real" if kind == "real" else "synthetic", body="" if kind == "hold" else
                     "Atlas Tool releases local agent tooling.")
    raw, _ = wire(value)
    parsed = json.loads(raw)
    if kind == "future":
        parsed["as_of"] = "2099-01-01T00:00:00Z"
    elif kind == "old-config":
        parsed["config"]["ranking_policy_sha256"] = "0" * 64
    if kind in {"future", "old-config"}:
        from evals.intelligence_g2.contracts import json_bytes
        raw = json_bytes(parsed)
    source, target = tmp_path / "input.json", tmp_path / "artifacts"
    source.write_bytes(raw)
    result = subprocess.run([sys.executable, "-B", "-m", "cfaw_news.intelligence.runtime",
        "--input", str(source), "--input-pin", hashlib.sha256(raw).hexdigest(), "--out", str(target)],
        capture_output=True, text=True, env={**os.environ}, timeout=60)
    payload = json.loads(result.stdout)
    if kind in {"future", "old-config"}:
        assert result.returncode == 1 and not target.exists()
        assert payload["code"] == ("G4_RUNTIME_FUTURE_INPUT" if kind == "future" else
                                   "G4_RUNTIME_CONFIG_PIN_MISMATCH")
        return
    assert result.returncode == 0, result.stdout + result.stderr
    manifest = json.loads((target / "manifest.json").read_bytes())
    for path, pin in manifest["files"].items():
        assert hashlib.sha256((target / path).read_bytes()).hexdigest() == pin
    result = json.loads((target / "result.json").read_bytes())
    assert result["publishable"] is False
    assert result["state"] == {"synthetic": "plan_ready", "real": "raw_news_only",
                               "hold": "evidence_not_ready"}[kind]
    observations = result["context"]["replay"]["observations"] if result["context"] is not None else ()
    for observation in observations:
        for candidate in observation["candidates"]:
            trace = candidate["trace"]
            assert hashlib.sha256((target / trace["path"]).read_bytes()).hexdigest() == trace["sha256"]
            stage = result
            for part in candidate["trace_pointer"].lstrip("/").split("/"):
                stage = stage[int(part)] if isinstance(stage, list) else stage[part]
            assert "replay_input" in stage
