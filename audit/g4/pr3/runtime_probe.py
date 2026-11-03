"""Authored local CLI executions, including exact rejected-input receipts.

Only this audit tool imports fixture authors; the runtime never does.
"""

import argparse
import hashlib
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from evals.intelligence_g2.contracts import json_bytes
from evals.intelligence_g4.tests.runtime_support import envelope, wire

ROOT = Path(__file__).resolve().parents[3]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default=".tmp/evals/g3/g4-pr3-20261102-001/cli-proof")
    args = parser.parse_args()
    area = (ROOT / args.out).resolve()
    assert area.is_relative_to(ROOT / ".tmp/evals/g3/g4-pr3-20261102-001")
    area.mkdir(exist_ok=False)
    executions = []
    for name in ("synthetic", "p1-experiment", "real-excerpt", "real-unknown", "hold", "future", "old-pin"):
        value = envelope("real" if name.startswith("real-") else "synthetic",
            rights="unknown" if name == "real-unknown" else None,
            body="" if name == "hold" else "Atlas Tool releases local agent tooling.")
        if name == "p1-experiment":
            value["config"].update(algorithm="p1", experiment="p1-explicit-development-v1")
        raw, pin = wire(value)
        if name in {"future", "old-pin"}:
            value = json.loads(raw)
            if name == "future":
                value["as_of"] = "2099-01-01T00:00:00Z"
            else:
                value["config"]["ranking_policy_sha256"] = "0" * 64
            raw = json_bytes(value)
            pin = hashlib.sha256(raw).hexdigest()
        folder = area / name
        folder.mkdir()
        path, output = folder / "input.json", folder / "output"
        path.write_bytes(raw)
        argv = [sys.executable, "-B", "-m", "cfaw_news.intelligence.runtime", "--input", str(path),
                "--input-pin", pin, "--out", str(output)]
        started, tick = datetime.now(timezone.utc).isoformat(), time.perf_counter()
        execution = subprocess.run(argv, cwd=ROOT, capture_output=True, timeout=60)
        (folder / "stdout.log").write_bytes(execution.stdout)
        (folder / "stderr.log").write_bytes(execution.stderr)
        payload = json.loads(execution.stdout)
        negative = name in {"future", "old-pin"}
        assert execution.returncode == (1 if negative else 0), execution.stderr
        assert payload["ok"] != negative
        if negative:
            assert not output.exists()
            assert payload["code"] == ("G4_RUNTIME_FUTURE_INPUT" if name == "future" else
                                       "G4_RUNTIME_CONFIG_PIN_MISMATCH")
        else:
            result = json.loads((output / "result.json").read_bytes())
            assert result["publishable"] is False
            assert result["state"] == ("raw_news_only" if name.startswith("real-") else
                                       "evidence_not_ready" if name == "hold" else "plan_ready")
            manifest = json.loads((output / "manifest.json").read_bytes())
            assert all(sha(output / p) == h for p, h in manifest["files"].items())
        record = dict(case=name, fixture_provenance="AI-authored development / real-shape mock; not live news",
            argv=argv, cwd=str(ROOT), started_at=started, elapsed_seconds=time.perf_counter() - tick,
            exit_code=execution.returncode, expected_exit_code=1 if negative else 0, response=payload,
            input_sha256=pin, files={p.relative_to(folder).as_posix(): sha(p)
                for p in folder.rglob("*") if p.is_file()})
        receipt = folder / "execution.json"
        receipt.write_bytes(json_bytes(record))
        executions.append(dict(path=receipt.relative_to(ROOT).as_posix(), sha256=sha(receipt)))
    (area / "proof.json").write_bytes(json_bytes(dict(status="PASS", executions=executions,
        real_news_collected=False, external_model_calls=0, user_database_writes=0)))
    print(json.dumps(dict(status="PASS", executions=len(executions), sha256=sha(area / "proof.json"))))


if __name__ == "__main__":
    main()
