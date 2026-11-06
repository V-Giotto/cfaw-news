"""Seal this review repair separately; preserve both historical manifests/indexes."""

import argparse
import importlib.metadata
import json
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

from audit.g4.h09.proof import read
from audit.g4.h09_review.controls import source_changes
from audit.g4.h09_review.quarantine import RUN
from audit.g4.h09_review.test_control import REGISTRATION_PIN
from audit.g4.pr6.freeze import ROOT, sha
from audit.g4.pr6.seal import build_roots, pin, verify_roots, write_new

RELEASE = ROOT / "audit/G4_H09_REVIEW_FIX_MANIFEST.json"
REQUIRED = ("focused", "sidecar-capture", "sidecar-apply", "full", "collect", "g4", "legacy-replay",
            "prior-trees", "ruff", "baseline", "build", "schema", "controls", "diff")


def cases(path):
    counts = dict(tests=0, passed=0, failed=0, skipped=0)
    for item in ET.parse(path).getroot().iter("testcase"):
        counts["tests"] += 1
        key = "failed" if item.find("failure") is not None or item.find("error") is not None else "skipped" if item.find("skipped") is not None else "passed"
        counts[key] += 1
    return counts


def receipts():
    commands = {p.stem.removesuffix(".command"): read(p) for p in RUN.glob("*.command.json")}
    assert all(commands[n]["exit_code"] == 0 for n in REQUIRED)
    assert commands["red"]["exit_code"] == commands["original-profile-refusal"]["exit_code"] == 1
    assert all(sha(ROOT / r["log"]) == r["log_sha256"] for r in commands.values())
    full, g4 = cases(RUN / "full.xml"), cases(RUN / "g4.xml")
    assert full == dict(tests=1754, passed=1753, failed=0, skipped=1)
    assert g4 == dict(tests=350, passed=350, failed=0, skipped=0)
    assert cases(RUN / "red.xml")["failed"] == 6
    assert cases(RUN / "original-profile-refusal.xml")["failed"] == 1
    assert read(RUN / "sidecar-capture.json")["verification"]["status"] == "FAIL_REPRODUCED"
    assert read(RUN / "sidecar-disposition.json")["original_indexes_unchanged"]
    legacy = read(RUN / "legacy-replay/result.json")
    assert legacy["original_input_directory_unchanged"] and not legacy["sqlite_opened_original"]
    preservation = read(RUN / "legacy-replay/input-preservation.json")
    assert preservation["before"] == preservation["after"]
    assert read(RUN / "control-verification.json")["status"] == "PASS_CURRENT_G4_AMENDED_PROFILE"
    return dict(commands=commands, full=full, g4=g4, red=cases(RUN / "red.xml"),
                original_profile_refusal="EXPECTED_NOT_PASS", browser="not_rerun_for_restore_and_test_only_repair")


def prior_roots():
    result, seals = {}, {}
    for name, key in (("audit/G4_RELEASE_MANIFEST.json", "index_roots"), ("audit/G4_H09_REPAIR_MANIFEST.json", "roots")):
        path = ROOT / name
        value = read(path)
        expected = read(RUN / "prior-tree-verification.json")["prior"][name]["seal"]
        assert pin(path) == expected
        assert not set(result) & set(value[key])
        result.update(value[key])
        seals[name] = expected
    return result, seals


def snapshot():
    assert not subprocess.check_output(["git", "diff", "--cached", "--name-only"], cwd=ROOT, text=True).strip()
    assert "/dev-diaries/" in (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    names = subprocess.check_output(["git", "ls-files", "--cached", "--others", "--exclude-standard"], cwd=ROOT, text=True).splitlines()
    names = sorted({n for n in names if (ROOT / n).is_file() and n != RELEASE.relative_to(ROOT).as_posix()
                    and not n.startswith(("dev-diaries/", ".tmp/", ".local/", ".venv/", "frontend/node_modules/", "frontend/dist/"))})
    assert not any(n.endswith((".db", ".sqlite", ".sqlite3")) or n == ".env" or n.endswith("/.env") for n in names)
    dest = RUN / "source-snapshot"
    dest.mkdir(exist_ok=False)
    files = {}
    for name in names:
        path = dest / name
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, path)
        files[name] = sha(path)
        assert files[name] == sha(ROOT / name)
    return files


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    if args.verify_only:
        value = read(RELEASE)
        assert all(sha(ROOT / n) == h for n, h in value["source_files_sha256"].items())
        print(json.dumps(verify_roots({**value["roots"], **value["prior_roots"]})))
        return
    assert not RELEASE.exists()
    results = receipts()
    changes = source_changes()
    prior, seals = prior_roots()
    packages = sorted({(d.metadata["Name"], d.version) for d in importlib.metadata.distributions()})
    assert [list(d) for d in packages] == read(ROOT / "audit/g4/pr6/ENTRY_FREEZE.json")["python_distributions"]
    write_new(RUN / "dependencies.json", dict(python=sys.version, python_executable=pin(Path(sys.executable)), packages=packages,
        node=subprocess.check_output(["node", "--version"], text=True).strip(),
        files={n: pin(ROOT / n) for n in ("pyproject.toml", "frontend/package.json", "frontend/package-lock.json")}))
    write_new(RUN / "seed-baseline.json", read(ROOT / ".local/evals/baseline.json"))
    write_new(RUN / "results.json", dict(status="PASS_LOCAL_REPAIR_PENDING_INDEPENDENT_REVIEW", **results, source=changes))
    files = snapshot()
    folders = [RUN, *sorted((ROOT / ".tmp/evals/g3").glob("h09-r2-*"))]
    roots = build_roots(folders)
    # Verify all current and historical references immediately before issuing this new seal.
    assert not set(roots) & set(prior)
    verification = verify_roots({**roots, **prior})
    write_new(RELEASE, dict(revision="g4-h09-review-fix-release-v1", created_at=datetime.now(timezone.utc).isoformat(),
        source_files_sha256=files, roots=roots, prior_roots=prior, prior_seals=seals, recursive_verification=verification,
        result=dict(path=(RUN / "results.json").relative_to(ROOT).as_posix(), **pin(RUN / "results.json")),
        control_profile="g4-exact-retry-amendment-v1", amendment_sha256=REGISTRATION_PIN,
        original_unamended_g3_profile="REFUSED_AUTHORIZED_SOURCE_DELTA_NOT_PASS",
        frozen_g1_g2_g3_packages_and_eval_tests_unchanged=True,
        authorized_legacy_test_source_amendment=["tests/test_workflow.py"],
        scope="offline SQLite input isolation, disclosed sidecar quarantine, exact-payload test repair and explicit G4 control amendment",
        findings=dict(input_sidecars="FIXED_SELF_TEST_PENDING_REVIEW", exact_retry_clock="FIXED_SELF_TEST_PENDING_REVIEW"),
        gates=dict(H05=dict(status="PASS_LOCAL_REPAIR", artifacts=["evals/intelligence_g4/tests/test_restore_input_isolation.py", (RUN / "prior-tree-verification.json").relative_to(ROOT).as_posix()], limit="isolated QA databases only"),
                   H10=dict(status="PASS_CURRENT_G4_AMENDED_PROFILE", artifacts=[(RUN / "control-verification.json").relative_to(ROOT).as_posix(), "audit/g4/h09_review/TEST_AMENDMENT.json"], limit="original unamended G3 source profile refuses this authorized test change; no research reacceptance"),
                   H12=dict(status="PASS_WITH_OPEN_GATES", artifacts=["audit/g4/h09_review/REVIEW_FIXES.md"], limit="historical tree preservation overclaim withdrawn; evidence and original failures retained"),
                   H00=dict(status="PENDING_REVIEW_AND_OWNER_APPROVAL", artifacts=["docs/G4_ACCEPTANCE.md"], limit="implementation self-tests do not approve Beta")),
        other_gates=dict(source="audit/G4_H09_REPAIR_MANIFEST.json:gates and docs/G4_ACCEPTANCE.md",
                         evidence_scope="historical carry-forward; no new browser, live-network, human or algorithm-utility acceptance"),
        tracks=dict(g4_development="CONDITIONAL_PENDING_REVIEW", g4_beta_utility="OFFLINE_REJECTION_PILOT_PASSED_BETA_PENDING", g4_research_optional="NOT_EVALUATED"),
        external_network_smoke="not_evaluated", browser="not_rerun; prior browser evidence remains historical",
        original_user_database_used=False, git_writes=False, public_deployment=False, self_hash="excluded to avoid circularity"))
    print(json.dumps(dict(status="SEALED_AFTER_ALL_REFERENCE_VERIFICATION", seal_sha256=sha(RELEASE), verification=verification)))


if __name__ == "__main__":
    main()
