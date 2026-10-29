"""Fresh, sealed local artifacts and actual process records. No self-issued trust pin."""

import os
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from evals.intelligence_g2.contracts import json_bytes, read_json
from evals.intelligence_g2.replay import safe_path
from evals.intelligence_v1.hashing import sha256_bytes

from .contracts import PACKAGE, ROOT, fail
from .history_contracts import parse_history
from .pr5_contracts import Campaign

OUTPUT_BASE = ROOT / ".tmp/evals/g3"


def relative(name):
    path = Path(name)
    if (path.anchor or ".." in path.parts or "\\" in str(name)
            or ":" in str(name) or not path.parts):
        fail("G3_PATH_INVALID", "relative_artifact")
    return path


def pinned(path, pin, root):
    path = safe_path(path, areas=(root,), code="G3_PATH_INVALID")
    raw = path.read_bytes()
    if sha256_bytes(raw) != pin:
        fail("G3_SHA_MISMATCH", "pinned_file")
    return raw


def fresh(out):
    path = safe_path(out, areas=(OUTPUT_BASE,), code="G3_PATH_INVALID")
    if path == OUTPUT_BASE or path.exists():
        fail("G3_OUTPUT_EXISTS", "fresh_output")
    path.mkdir(parents=True, exist_ok=False)
    return path


def write(root, name, value):
    path = root / relative(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(value if isinstance(value, bytes) else json_bytes(value))


def load_campaign(path, pin):
    raw = pinned(path, pin, PACKAGE / "manifests")
    value = parse_history(Campaign, read_json(raw))
    # Input pins come from a separately trusted campaign. Reference bytes are
    # deliberately not read here: prediction has no reference-loader dependency.
    for case in value.cases:
        pinned(PACKAGE / relative(case.input.path), case.input.sha256, PACKAGE / "fixtures/pr5")
    return value


def release():
    from .pytest_control import snapshot

    test_control = snapshot()
    files = []
    files += list(ROOT.glob("*.py"))
    for base in ("backend", "evals", "tests", "frontend/src", "scripts"):
        files += [p for p in (ROOT / base).rglob("*") if p.is_file()
                  and "__pycache__" not in p.parts and p.suffix in
                  {".py", ".json", ".jsonl", ".ts", ".tsx", ".css", ".txt", ".ps1"}]
    files += [p for p in (ROOT / "frontend").glob("*") if p.is_file()
              and p.suffix in {".json", ".ts", ".js", ".mjs"}]
    files += [ROOT / p for p in ("pyproject.toml", "requirements.lock", "frontend/package.json",
              "frontend/package-lock.json", ".github/workflows/ci.yml", ".gitignore", ".gitattributes")]
    hashes = {p.relative_to(ROOT).as_posix(): sha256_bytes(p.read_bytes()) for p in sorted(set(files))}
    return dict(schema_revision="g3-pr5-working-tree-v2", files=hashes, test_control=test_control,
                anchor_commit=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                                      text=True).strip(),
                source_state="working_tree_exact_bytes_not_a_new_commit",
                python=platform.python_version(), platform=sys.platform)


def seal(root, role, **binding):
    files = {p.relative_to(root).as_posix(): sha256_bytes(p.read_bytes())
             for p in sorted(root.rglob("*")) if p.is_file()}
    value = dict(schema_revision="g3-pr5-artifacts-v1", role=role, files=files, **binding)
    write(root, "artifact_manifest.json", value)
    return sha256_bytes(json_bytes(value))


def sealed(root, pin, role):
    root = safe_path(root, areas=(OUTPUT_BASE,), code="G3_PATH_INVALID")
    value = read_json(pinned(root / "artifact_manifest.json", pin, root))
    actual = {p.relative_to(root).as_posix() for p in root.rglob("*")
              if p.is_file() and p != root / "artifact_manifest.json"}
    if (value.get("role") != role or actual != set(value["files"])
            or value.get("schema_revision") != "g3-pr5-artifacts-v1"):
        fail("G3_ARTIFACT_INVALID", "role_or_complete_file_set")
    for name, sha in value["files"].items():
        pinned(root / relative(name), sha, root)
    return value


def command(root, name, argv, *, cwd=ROOT, seed="1", timeout=3600):
    from .pytest_control import command_environment

    argv = [str(a) for a in argv]
    environment = command_environment(seed)
    start, timer = datetime.now(timezone.utc).isoformat(), time.perf_counter()
    log = root / (name + ".log")
    with log.open("xb") as stream:
        try:
            process = subprocess.run(argv, cwd=cwd, env={**os.environ, **environment},
                                     stdout=stream, stderr=subprocess.STDOUT, timeout=timeout)
            code = process.returncode
        except subprocess.TimeoutExpired:
            code = 124
    result = dict(name=name, argv=argv, cwd=str(cwd), environment=environment, started_at=start,
                  finished_at=datetime.now(timezone.utc).isoformat(), exit_code=code,
                  elapsed_seconds=time.perf_counter() - timer, log=log.name,
                  log_sha256=sha256_bytes(log.read_bytes()))
    write(root, name + ".command.json", result)
    if code:
        fail("G3_COMMAND_FAILED", name)
    return result


def verify_command(root, name, argv, *, cwd=ROOT, seed="1"):
    from .pytest_control import command_environment

    record = read_json((root / (name + ".command.json")).read_bytes())
    start, end = (datetime.fromisoformat(record[k]) for k in ("started_at", "finished_at"))
    expected_env = command_environment(seed)
    if (record["name"] != name or record["argv"] != [str(a) for a in argv]
            or record["cwd"] != str(cwd) or record["environment"] != expected_env
            or record["exit_code"] != 0 or record["log"] != name + ".log"
            or start.tzinfo is None or end.tzinfo is None or end < start
            or record["elapsed_seconds"] < 0):
        fail("G3_CHECK_EVIDENCE_MISMATCH", name)
    pinned(root / relative(record["log"]), record["log_sha256"], root)
    return record
