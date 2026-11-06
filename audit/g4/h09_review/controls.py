"""Validate actual amended execution, exact JUnit and narrowly authorized changes."""

from audit.g4.h09.proof import read
from audit.g4.h09_review.quarantine import RUN
from audit.g4.h09_review.test_control import (
    REGISTRATION,
    REGISTRATION_PIN,
    verify_execution,
    verify_inventory,
)
from audit.g4.pr6.freeze import ROOT, sha
from audit.g4.pr6.seal import write_new
from evals.intelligence_g3.junit_inventory import verify_junit

ALLOWED = {"tests/test_workflow.py", "backend/cfaw_news/intelligence/migrate.py",
           "audit/g4/h09/proof.py", "audit/g4/h09/legacy_replay.py", "audit/g4/h09/REPAIR_REPORT.md",
           "docs/G4_ACCEPTANCE.md", "docs/G4_G5_HANDOFF.md", "docs/G4_BETA_USER_GUIDE.md"}
FROZEN = ("evals/intelligence_v1/", "evals/intelligence_g2/", "evals/intelligence_g3/", "tests/evals/", "data/archive/")


def source_changes():
    entry = read(RUN / "entry.json")["files"]
    changes = {n: dict(before=h, after=sha(ROOT / n)) for n, h in entry.items() if sha(ROOT / n) != h}
    assert set(changes) <= ALLOWED, changes
    frozen = {n: h for n, h in entry.items() if n.startswith(FROZEN)}
    assert frozen and all(sha(ROOT / n) == h for n, h in frozen.items())
    amendment = read(REGISTRATION)
    expected = amendment["changes"]["tests/test_workflow.py"]
    assert changes["tests/test_workflow.py"] == dict(before=expected["before_sha256"], after=expected["after_sha256"])
    return dict(changes=changes, frozen_unchanged=len(frozen), amendment_sha256=REGISTRATION_PIN)


def control_evidence():
    inventory = read(RUN / "inventory.json")
    for name, mode in (("full", "full"), ("collect", "collect")):
        record = read(RUN / (name + "-control.json"))
        base = RUN / (name + "-control.frozen-runner.json")
        assert sha(base) == record["frozen_runner_receipt_sha256"]
        assert read(base) == record["frozen_runner"]
        kwargs = dict(inventory=str(RUN / "inventory.json")) if mode == "collect" else dict(
            junit=str(RUN / "full.xml"), basetemp=str(ROOT / ".tmp/evals/g3/h09-r2-full"))
        verify_execution(record, mode=mode, **kwargs)
    registered = verify_inventory(inventory)
    junit = verify_junit(registered, RUN / "full.xml")
    assert read(RUN / "original-profile-refusal.command.json")["exit_code"] == 1
    assert "G3_TEST_INVENTORY_INVALID" in (RUN / "original-profile-refusal.log").read_text(encoding="utf-8")
    return dict(status="PASS_CURRENT_G4_AMENDED_PROFILE", profile="g4-exact-retry-amendment-v1",
        junit=junit, nodes=len(inventory["nodes"]), g3_nodes=sum(n.startswith("tests/evals/g3/") for n in inventory["nodes"]),
        original_unamended_profile="REFUSED_AUTHORIZED_SOURCE_DELTA_EXPECTED_NOT_PASS",
        required_nodes_and_skip_exemptions_changed=False, frozen_g3_files_changed=False,
        application="explicit in-memory required-source registration only; frozen runner, plugin allowlist, argv and JUnit rules retained",
        matrix_2574="not_evaluated")


def main():
    write_new(RUN / "control-verification.json", control_evidence())
    write_new(RUN / "source-verification.json", source_changes())
    print("PASS: amended G4 control receipts/JUnit and only authorized source changes; original profile refusal retained")


if __name__ == "__main__":
    main()
