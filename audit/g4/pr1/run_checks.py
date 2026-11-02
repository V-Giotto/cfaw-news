"""Capture one actual local process, preserving nonzero exits and exact stdout/stderr."""

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--cwd", choices=("root", "frontend"), default="root")
    parser.add_argument("argv", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    out = (ROOT / args.out).resolve()
    if (not out.is_relative_to(ROOT / ".tmp/evals/g3")
            or re.fullmatch(r"[a-z0-9-]+", args.name) is None):
        parser.error("fresh named records must be under the local G3 artifact area")
    argv = args.argv[1:] if args.argv[:1] == ["--"] else args.argv
    if not argv:
        parser.error("a command is required")
    if argv[0] == "python":
        argv[0] = sys.executable
    cwd = ROOT / "frontend" if args.cwd == "frontend" else ROOT
    environment = dict(PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1", PYTHONHASHSEED="1",
        PYTHONPATH=str(ROOT / "backend"), PYTHONNOUSERSITE="1", PYTEST_DISABLE_PLUGIN_AUTOLOAD="1")
    out.mkdir(parents=True, exist_ok=True)
    log = out / (args.name + ".log")
    record = out / (args.name + ".command.json")
    if record.exists():
        parser.error("record already exists")
    started = datetime.now(timezone.utc).isoformat()
    timer = time.perf_counter()
    with log.open("xb") as stream:
        process = subprocess.run(argv, cwd=cwd, env={**os.environ, **environment},
                                 stdout=stream, stderr=subprocess.STDOUT)
    value = dict(argv=argv, cwd=str(cwd), environment=environment, started_at=started,
        finished_at=datetime.now(timezone.utc).isoformat(),
        elapsed_seconds=time.perf_counter() - timer, exit_code=process.returncode,
        log=log.relative_to(ROOT).as_posix(), log_sha256=hashlib.sha256(log.read_bytes()).hexdigest())
    with record.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, sort_keys=True, indent=2)
        stream.write("\n")
    print(json.dumps(value))
    return process.returncode


if __name__ == "__main__":
    raise SystemExit(main())
