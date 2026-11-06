"""Explicit G4 test amendment; frozen G3 files and historical credentials stay unchanged.

Only this entry point installs an in-memory required-source registration for the
one authorized workflow test edit. It delegates all nodes, skip rules, argv,
plugin checks and JUnit checks to the frozen runner. It is a new control profile,
not evidence that the original unamended G3 source registry accepts the edit.
"""

import argparse
import copy
import json
from collections import Counter
from contextlib import contextmanager
from pathlib import Path

from audit.g4.pr6.freeze import ROOT, sha
from audit.g4.pr6.seal import write_new
from evals.intelligence_g2.pr6.junit_inventory import test_sources as current_sources
from evals.intelligence_g3 import junit_inventory as registry
from evals.intelligence_g3 import pytest_runner as runner

REGISTRATION = ROOT / "audit/g4/h09_review/TEST_AMENDMENT.json"
REGISTRATION_PIN = "852acf44ca74dfdd90559f8c633d6f8685c3ab211c75e847455eeb80a487df35"
ORIGINAL_REQUIREMENTS = registry.requirements


def required():
    assert sha(REGISTRATION) == REGISTRATION_PIN, "G4_TEST_AMENDMENT_PIN_MISMATCH"
    amendment = json.loads(REGISTRATION.read_text(encoding="utf-8"))
    assert set(amendment["changes"]) == {"tests/test_workflow.py"}
    value = copy.deepcopy(ORIGINAL_REQUIREMENTS())  # Still verifies every frozen manifest pin.
    for name, change in amendment["changes"].items():
        assert value["test_source_sha256"][name] == change["before_sha256"]
        assert sha(ROOT / name) == change["after_sha256"], "G4_TEST_AMENDMENT_SOURCE_MISMATCH"
        value["test_source_sha256"][name] = change["after_sha256"]
    assert value["test_source_sha256"] == current_sources(), "G4_UNREGISTERED_TEST_CHANGE"
    return value


def profile_snapshot():
    value = required()
    return dict(profile="g4-exact-retry-amendment-v1", amendment_sha256=REGISTRATION_PIN,
        adapter_sha256=sha(Path(__file__)), test_source_sha256=value["test_source_sha256"])


@contextmanager
def installed():
    assert registry.requirements is ORIGINAL_REQUIREMENTS, "G4_PROFILE_ALREADY_REPLACED"
    required()
    registry.requirements = required
    try:
        yield
        assert registry.requirements is required, "G4_PROFILE_CHANGED_DURING_TESTS"
    finally:
        registry.requirements = ORIGINAL_REQUIREMENTS


def verify_inventory(inventory):
    value = required()
    assert Counter(inventory["nodes"]) == Counter(value["nodes"]), "G4_TEST_NODES_MISMATCH"
    assert len(inventory["nodes"]) == len(set(inventory["nodes"])), "G4_DUPLICATE_TEST_NODE"
    assert inventory["test_source_sha256"] == value["test_source_sha256"], "G4_TEST_SOURCE_MISMATCH"
    return value


def verify_execution(record, *, mode, inventory=None, junit=None, basetemp=None):
    assert record["revision"] == "g4-amended-pytest-execution-v1"
    assert record["before_amendment"] == record["after_amendment"] == profile_snapshot()
    runner.verify_execution(record["frozen_runner"], mode=mode, inventory=inventory, junit=junit, basetemp=basetemp)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("collect", "full", "g3"), required=True)
    parser.add_argument("--inventory")
    parser.add_argument("--junit")
    parser.add_argument("--basetemp")
    parser.add_argument("--control-record", required=True)
    args = parser.parse_args()
    target = Path(args.control_record).resolve()
    assert target.is_relative_to(ROOT / ".tmp/evals/g3") and not target.exists()
    base = target.with_suffix(".frozen-runner.json")
    assert not base.exists()
    before = profile_snapshot()
    argv = ["--mode", args.mode, "--control-record", str(base)]
    for key in ("inventory", "junit", "basetemp"):
        if value := getattr(args, key):
            argv.extend(["--" + key, value])
    with installed():
        code = runner.main(argv)
    after = profile_snapshot()
    assert before == after
    write_new(target, dict(revision="g4-amended-pytest-execution-v1", before_amendment=before,
        after_amendment=after, frozen_runner=json.loads(base.read_text(encoding="utf-8")),
        frozen_runner_receipt_sha256=sha(base), original_profile_claimed=False))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
