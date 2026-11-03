"""Install both wheels into a temporary target and execute outside the repository."""

import hashlib
import json
import os
import subprocess
import sys

from scripts.build_g4_native import build, build_core

from .runtime_support import envelope, wire


def test_offline_wheels_outside_cwd_and_missing_native_refusal(tmp_path):
    wheels = tmp_path / "wheels"
    core, native = build_core(wheels), build(wheels)
    site = tmp_path / "site"
    temporary = tmp_path / "pip-temp"
    temporary.mkdir()
    install_env = {**os.environ, "TEMP": str(temporary), "TMP": str(temporary)}
    installed = subprocess.run([sys.executable, "-B", "-m", "pip", "install", "--no-index", "--no-deps",
        "--no-compile", "--target", str(site), str(core), str(native)], capture_output=True, text=True,
        env=install_env)
    assert installed.returncode == 0, installed.stdout + installed.stderr
    raw, pin = wire(envelope())
    source = tmp_path / "input.json"
    source.write_bytes(raw)
    output = tmp_path / "result.json"
    argv = [sys.executable, "-I", "-B", "-c", "import sys,pathlib;sys.path.insert(0,sys.argv[1]);"
        "from cfaw_news.intelligence.runtime import run;"
        "from evals.intelligence_g2.contracts import json_bytes;"
        "r=run(pathlib.Path(sys.argv[2]).read_bytes(),expected_sha256=sys.argv[3]);"
        "pathlib.Path(sys.argv[4]).write_bytes(json_bytes(r));print(r.state)",
        str(site), str(source), pin, str(output)]
    env = {**os.environ}
    env.pop("PYTHONPATH", None)
    result = subprocess.run(argv, cwd=tmp_path, env=env, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0 and result.stdout.strip() == "plan_ready", result.stderr
    assert json.loads(output.read_bytes())["publishable"] is False
    # Removing the exact native dependency cannot silently fall back to another code tree.
    native_package = site / "evals"
    detached = site / "native-detached"
    native_package.rename(detached)
    try:
        missing = subprocess.run(argv, cwd=tmp_path, env=env, capture_output=True, text=True, timeout=60)
        assert missing.returncode != 0 and "G4_NATIVE_DEPENDENCY_REQUIRED" in missing.stderr
    finally:
        detached.rename(native_package)
    # A present but modified dependency is also rejected before calculation.
    path = site / "evals/intelligence_g3/fact_signature.py"
    path.write_bytes(path.read_bytes() + b"\n# deliberate installed dependency corruption\n")
    failed = subprocess.run(argv, cwd=tmp_path, env=env, capture_output=True, text=True, timeout=60)
    assert failed.returncode != 0 and "G4_NATIVE_DEPENDENCY_MISMATCH" in failed.stderr
    proof = dict(core_sha256=hashlib.sha256(core.read_bytes()).hexdigest(),
                 native_sha256=hashlib.sha256(native.read_bytes()).hexdigest(),
                 input_sha256=pin, output_sha256=hashlib.sha256(output.read_bytes()).hexdigest(),
                 outside_repository_cwd=True, missing_native_dependency_rejected=True,
                 exact_installed_dependency_corruption_rejected=True)
    (tmp_path / "offline-proof.json").write_text(json.dumps(proof), encoding="utf-8")
