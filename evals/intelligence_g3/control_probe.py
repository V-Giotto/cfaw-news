"""Real fixed-pin regression: valid acceptance, then an unapproved root hook.

Run only in a quiescent workspace. No prior artifact is modified. The temporary
hook is created exclusively, never imported, and removed only if still ours.
"""

import argparse
import sys

from evals.intelligence_g2.contracts import digest, read_json
from evals.intelligence_v1.exceptions import ContractError

from .artifacts import command, fresh, release, seal, write
from .contracts import ROOT, fail


def probe(*, run, run_pin, evaluation, evaluation_pin, checks, checks_pin, out):
    before = release()
    output = fresh(out)
    hook = ROOT / "conftest.py"
    marker = output / "HOOK_MUST_NOT_EXECUTE"
    payload = ("from pathlib import Path\n" + f"Path({str(marker)!r}).write_text('executed')\n"
               + "def pytest_pyfunc_call(pyfuncitem):\n    return True\n").encode("utf-8")
    if hook.exists():
        fail("G3_TEST_CONTROL_UNAPPROVED", "probe_requires_absent_root_conftest")
    common = [sys.executable, "-B", "-m", "evals.intelligence_g3.acceptance",
              "--run", str(run), "--run-pin", run_pin, "--evaluation", str(evaluation),
              "--evaluation-pin", evaluation_pin, "--checks", str(checks), "--checks-pin", checks_pin]
    # This is a real positive execution using the same three supplied trusted pins.
    command(output, "baseline", [*common, "--out", str(output / "baseline-acceptance")])
    baseline = read_json((output / "baseline.log").read_bytes().splitlines()[-1])
    assert baseline["overall_status"] == "PASS"
    with hook.open("xb") as stream:
        stream.write(payload)
    try:
        for name, argv in (
            ("fixed-pins-with-hook", [*common, "--out", str(output / "must-not-pass")]),
            ("runner-with-hook", [sys.executable, "-B", "-m", "evals.intelligence_g3.pytest_runner",
                "--mode", "collect", "--inventory", str(output / "must-not-collect.json"),
                "--control-record", str(output / "must-not-run.json")]),
        ):
            try:
                command(output, name, argv)
            except ContractError:
                record = read_json((output / (name + ".command.json")).read_bytes())
                if record["exit_code"] != 1:
                    raise AssertionError("Unexpected rejection exit code") from None
                assert "G3_TEST_CONTROL_UNAPPROVED" in (output / record["log"]).read_text("utf-8")
            else:
                raise AssertionError("Unapproved root hook did not block " + name)
        assert not marker.exists()
        assert not (output / "must-not-pass").exists()
    finally:
        if hook.read_bytes() != payload:
            fail("G3_TEST_CONTROL_CHANGED", "probe_hook_changed_concurrently")
        hook.unlink()
    after = release()
    if after != before:
        fail("G3_SOURCE_MISMATCH", "probe_restore")
    result = dict(revision="g3-fixed-pin-control-probe-v1", actual_baseline_exit=0,
        actual_hook_acceptance_exit=1, actual_hook_runner_exit=1, hook_executed=False,
        trusted_pins_unchanged=dict(prediction=run_pin, evaluation=evaluation_pin, checks=checks_pin),
        baseline_acceptance_pin=baseline["acceptance_pin"], source_sha256_before=digest(before),
        source_sha256_after=digest(after), source_restored=True,
        negative_acceptance_artifact_created=False)
    write(output, "control_probe.json", result)
    pin = seal(output, "fixed_pin_control_probe", source_sha256=digest(before))
    print(pin, flush=True)
    return result, pin


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("run", "run-pin", "evaluation", "evaluation-pin", "checks", "checks-pin", "out"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args(argv)
    probe(**vars(args))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
