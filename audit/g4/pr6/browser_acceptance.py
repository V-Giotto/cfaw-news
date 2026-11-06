"""Record effective browser targets, fixture pins, service config and full lifecycles."""

import argparse
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone

from audit.g4.pr6.freeze import ROOT, sha
from audit.g4.pr6.seal import write_new

RUN = ROOT / ".tmp/evals/g3/g4-pr6-review-fix-20261105-001"
MODULES = "C:/Users/Administrator/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules"
CONTROL = dict(PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1", PYTHONHASHSEED="1",
               PYTHONPATH=str(ROOT / "backend"), PYTHONNOUSERSITE="1", PYTEST_DISABLE_PLUGIN_AUTOLOAD="1")


def now():
    return datetime.now(timezone.utc).isoformat()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("red", "green"), required=True)
    args = parser.parse_args()
    out = RUN / ("browser-" + args.phase)
    out.mkdir(exist_ok=False)
    env = {k: v for k, v in os.environ.items() if not k.startswith(("CFAW_PR5_", "CFAW_PR6_", "CFAW_QA_"))}
    env.update(CONTROL)
    services = []
    result_code = 1

    def start(name, port, argv):
        with socket.socket() as sock:
            assert sock.connect_ex(("127.0.0.1", port)) != 0, "QA port already occupied"
        log = out / (name + ".service.log")
        stream = log.open("xb")
        record = dict(argv=argv, cwd=str(ROOT), environment=CONTROL, started_at=now(),
                      url=f"http://127.0.0.1:{port}", config=str(out / (name + ".config.json")))
        process = subprocess.Popen(argv, cwd=ROOT, env=env, stdin=subprocess.PIPE, stdout=stream, stderr=subprocess.STDOUT)
        record["pid"] = process.pid
        services.append((name, process, stream, record, log))
        deadline = time.monotonic() + 35
        while True:
            assert process.poll() is None, name + " exited before readiness"
            try:
                with urllib.request.urlopen(record["url"], timeout=1) as response:
                    assert response.status == 200
                record.update(ready_at=now(), ready_http_status=200)
                break
            except (OSError, TimeoutError):
                assert time.monotonic() < deadline, name + " readiness timeout"
                time.sleep(0.1)

    def browser(name, script, target, fixture_folder):
        effective = {**CONTROL, "CFAW_PR5_OUT": str(fixture_folder), "CFAW_PR5_URL": target,
                     "CFAW_QA_BOUNDARY_URL": "http://127.0.0.1:5175/tests/boundary.html",
                     "CFAW_PR6_RUN": str(RUN), "CFAW_PR6_PILOT": "pilot-native",
                     "CFAW_PR6_URL": "http://127.0.0.1:8136"}
        fixture = fixture_folder / "fixtures.json"
        argv = ["node", str(ROOT / "audit/g4/pr6" / script), MODULES]
        log = out / (name + ".log")
        started, timer = now(), time.perf_counter()
        with log.open("xb") as stream:
            process = subprocess.run(argv, cwd=ROOT, env={**env, **effective}, stdout=stream, stderr=subprocess.STDOUT)
        write_new(out / (name + ".command.json"), dict(argv=argv, cwd=str(ROOT), environment=effective,
            started_at=started, finished_at=now(), elapsed_seconds=time.perf_counter() - timer,
            exit_code=process.returncode, log=str(log.relative_to(ROOT)), log_sha256=sha(log),
            fixtures=dict(path=str(fixture), sha256=sha(fixture)),
            active_services=[dict(name=n, pid=p.pid, url=r["url"], config=r["config"],
                                 config_sha256=sha(ROOT / r["config"])) for n, p, _, r, _ in services]))
        return process.returncode

    try:
        config_out = out / "contract.config.json"
        start("contract", 8135, [sys.executable, "-m", "audit.g4.pr6.qa_server", "--kind", "contract",
            "--folder", str(out / "contract-data"), "--port", "8135", "--config-out", str(config_out)])
        start("development", 5175, ["node", str(ROOT / "audit/g4/pr6/dev_server.mjs"),
            str(ROOT / "frontend"), "5175", "http://127.0.0.1:8135", str(out / "development.config.json")])
        focus = out / "focus"
        focus.mkdir()
        shutil.copyfile(RUN / "browser-contracts-native/fixtures.json", focus / "fixtures.json")
        code = browser("strict-focus", "focus.cjs", "http://127.0.0.1:5175", focus)
        if args.phase == "red":
            result_code = code
            assert code == 1, "expected original StrictMode failure must be reproduced before fixing"
        else:
            assert code == 0, "StrictMode focus failed"
            assert browser("contracts", "browser_contracts.cjs", "http://127.0.0.1:8135", RUN / "browser-contracts-native") == 0
            start("pilot", 8136, [sys.executable, "-m", "audit.g4.pr6.qa_server", "--kind", "pilot",
                "--folder", str(RUN / "pilot-native"), "--port", "8136", "--qa-delay", "2",
                "--config-out", str(out / "pilot.config.json")])
            assert browser("pilot", "browser.cjs", "http://127.0.0.1:8136", RUN / "browser-contracts-native") == 0
            result_code = 0
    finally:
        exits = []
        for name, process, stream, record, log in reversed(services):
            record["stop_requested_at"] = now()
            record["stop_method"] = "stdin STOP; graceful application/server close"
            if process.poll() is None:
                process.stdin.write(b"STOP\n")
                process.stdin.flush()
            try:
                code = process.wait(timeout=25)
            except subprocess.TimeoutExpired:
                process.terminate()
                code = process.wait(timeout=10)
                record["stop_method"] = "forced terminate after graceful timeout; NOT PASS"
            stream.close()
            record.update(finished_at=now(), exit_code=code, log=str(log.relative_to(ROOT)), log_sha256=sha(log))
            config_file = ROOT / record["config"]
            if config_file.exists():
                record["config_sha256"] = sha(config_file)
            write_new(out / (name + ".service.json"), record)
            exits.append(code)
        write_new(out / "lifecycle.json", dict(status="PASS" if all(c == 0 for c in exits) else "FAIL",
            phase=args.phase, browser_exit_code=result_code, service_exit_codes=exits,
            effective_targets_recorded=True, production_database_used=False, external_network_smoke="not_evaluated"))
        assert all(c == 0 for c in exits), exits
    return result_code


if __name__ == "__main__":
    raise SystemExit(main())
