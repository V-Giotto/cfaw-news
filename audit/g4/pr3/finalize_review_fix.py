"""Seal this review fix without changing prior reports, manifests or native assets."""

import argparse
import hashlib
import json
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

from cfaw_news.intelligence.native import ENGINE_PIN, verify
from cfaw_news.intelligence.runtime_contracts import (
    FACT_PIN,
    RANK_PIN,
    ExplicitBudget,
    RuntimeConfig,
)

from evals.intelligence_g2.contracts import data, digest, json_bytes
from evals.intelligence_g2.pr6.junit_inventory import verify_junit
from evals.intelligence_g3.junit_inventory import verify_inventory
from evals.intelligence_g3.pytest_runner import verify_execution

ROOT = Path(__file__).resolve().parents[3]
AREA = ROOT / ".tmp/evals/g3/g4-pr3-review-fix-20261102-001"
DELIVERY = ROOT / "audit/g4/pr3"
CHANGED = {"backend/cfaw_news/intelligence/" + p + ".py" for p in (
    "g2_adapter", "g3_adapter", "runtime", "runtime_contracts")}
CHANGED |= {"evals/intelligence_g4/tests/test_runtime_" + p + ".py" for p in ("bridge", "cli", "ledger")}
MANIFEST = ROOT / "evals/intelligence_g4/manifests/pr3_review_required_tests.json"


def read(path):
    return json.loads(path.read_bytes())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    with path.open("xb") as stream:
        stream.write(json_bytes(value))


def source():
    paths = list((ROOT / "backend/cfaw_news/intelligence").rglob("*.py"))
    paths += list((ROOT / "evals/intelligence_g4/tests").glob("*.py"))
    paths += list((ROOT / "evals/intelligence_g4/schema/pr3_review_fix").glob("*.json"))
    paths += [MANIFEST, ROOT / "scripts/build_g4_native.py", DELIVERY / "review_fix_probe.py",
              DELIVERY / "finalize_review_fix.py"]
    return {p.relative_to(ROOT).as_posix(): sha(p) for p in sorted(paths)}


def node_ids(xml):
    return sorted(c.get("classname").replace(".", "/") + ".py::" + c.get("name")
                  for c in ET.parse(xml).iter("testcase"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare", action="store_true")
    args = parser.parse_args()
    entry = read(AREA / "entry.json")
    manifests = [ROOT / "evals/intelligence_g4/manifests" / p for p in (
        "pr1_required_tests.json", "pr1_review_required_tests.json", "pr2_required_tests.json",
        "pr2_path_review_required_tests.json", "pr3_required_tests.json")]
    parents = {p.relative_to(ROOT).as_posix(): sha(p) for p in manifests}
    previous = [n for p in manifests for n in read(p)["nodes"]]
    actual = node_ids(AREA / "g4-final.xml")
    added = sorted(set(actual) - set(previous))
    assert len(previous) == 215 and len(added) == 22 and len(actual) == len(set(actual)) == 237
    test_changes = sorted(p for p in CHANGED if p.startswith("evals/"))
    if args.prepare:
        write(MANIFEST, dict(revision="g4-pr3-review-required-tests-v1", parent_manifests=parents,
            nodes=added, test_source_sha256={"evals/intelligence_g4/tests/test_pr3_review_fixes.py":
                sha(ROOT / "evals/intelligence_g4/tests/test_pr3_review_fixes.py")},
            reviewed_test_source_replacements={p: dict(before=entry["files"][p], after=sha(ROOT / p))
                                               for p in test_changes}))
        write(AREA / "final-source.json", source())
        print(json.dumps(dict(registered_nodes=len(added), source_sha256=digest(source()))))
        return
    assert subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip() == entry["head"]
    assert not subprocess.check_output(["git", "diff", "--cached", "--name-only"], cwd=ROOT)
    changed = {p for p, pin in entry["files"].items() if sha(ROOT / p) != pin}
    assert changed == CHANGED, changed
    assert all(sha(ROOT / ".tmp/evals/g3/g4-pr3-review-20261102-001" / p) == pin
               for p, pin in entry["review_evidence"].items())
    assert source() == read(AREA / "final-source.json")
    manifest = read(MANIFEST)
    assert manifest["parent_manifests"] == parents and manifest["nodes"] == added
    for path in manifests:
        for p, pin in read(path)["test_source_sha256"].items():
            replacement = manifest["reviewed_test_source_replacements"].get(p)
            assert sha(ROOT / p) == (replacement["after"] if replacement else pin)
            if replacement:
                assert replacement["before"] == pin
    assert all(sha(ROOT / p) == pin for p, pin in manifest["test_source_sha256"].items())
    cases = list(ET.parse(AREA / "g4-final.xml").iter("testcase"))
    assert not any(c.find(t) is not None for c in cases for t in ("failure", "error", "skipped"))
    required = verify_inventory(read(AREA / "node_inventory.json"))
    full = verify_junit(required, AREA / "full.xml")
    for mode in ("collect", "full"):
        kw = dict(inventory=str(AREA / "node_inventory.json")) if mode == "collect" else dict(
            junit=str(AREA / "full.xml"), basetemp=str(ROOT / ".tmp/evals/g3/g4-pr3-fix-full-temp-20261102-001"))
        verify_execution(read(AREA / (mode + ".control.json")), mode=mode, **kw)
    commands = {p.stem.removesuffix(".command"): read(p) for p in AREA.glob("*.command.json")}
    for name, row in commands.items():
        assert sha(ROOT / row["log"]) == row["log_sha256"]
        assert row["exit_code"] == (1 if name in {"red", "green-01", "proof"} else 0), name
    assert {"full", "g4-final", "ruff-final", "schema-check", "proof-final", "baseline", "build"} <= set(commands)
    proof_path = AREA / "proof-final/proof.json"
    proof = read(proof_path)
    assert proof["status"] == "PASS" and len(proof["receipts"]) == 13
    for receipt in proof["receipts"]:
        path = ROOT / receipt["path"]
        assert sha(path) == receipt["sha256"]
        value = read(path)
        if "groups_after" in value:
            assert value["groups_after"] == 0 and value["inherited_request_control"] and value["triggered"]
        else:
            assert value["exit_code"] == 0
            assert all(sha(path.parent / p) == pin for p, pin in value["files"].items())
    verify()
    old = read(DELIVERY / "BASELINE.json")
    assert old["native_engine_sha256"] == ENGINE_PIN and old["fact_signature_policy_sha256"] == FACT_PIN
    assert old["ranking_policy_sha256"] != RANK_PIN
    config = RuntimeConfig(budget=ExplicitBudget(profile="focus70-radar30-v1"))
    install = list((AREA / "g4-final-temp").rglob("offline-proof.json"))
    assert len(install) == 1
    install_proof = read(install[0])
    assert all(install_proof[p] for p in ("outside_repository_cwd", "missing_native_dependency_rejected",
                                         "exact_installed_dependency_corruption_rejected"))
    result = dict(revision="g4-pr3-review-fix-v1", status="PASS_SCOPE_PENDING_INDEPENDENT_REREVIEW",
        head=entry["head"], source=dict(files=source(), sha256=digest(source())),
        policy=dict(revision="g4-runtime-ranking-policy-v2", sha256=RANK_PIN, previous_sha256=old["ranking_policy_sha256"],
                    native_engine_sha256=ENGINE_PIN, fact_signature_policy_sha256=FACT_PIN),
        config=dict(value=data(config), sha256=digest(config)),
        results=dict(g4=dict(passed=237, skipped=0, added=22), full=full, ruff="PASS", schema="PASS",
                     baseline="PASS", frontend_build="PASS", controls=dict(internal_faults=8, groups_after_fault=0)),
        proof=dict(path=proof_path.relative_to(ROOT).as_posix(), sha256=sha(proof_path)),
        offline_install=dict(path=install[0].relative_to(ROOT).as_posix(), sha256=sha(install[0]), value=install_proof),
        commands=commands, preservation=dict(entry_files=len(entry["files"]), changed_allowed=sorted(changed),
            review_evidence_unchanged=len(entry["review_evidence"]), prior_reports_schemas_manifests_unchanged=True),
        findings=dict(material_kind="FIXED_PENDING_REREVIEW", persona_continuity="FIXED_BY_EXPLICIT_BLOCK_PENDING_REREVIEW",
                      internal_control="FIXED_PENDING_REREVIEW"),
        limitations=dict(historical_persona="NOT_IMPLEMENTED", real_focus_radar="BLOCKED_EVIDENCE_QUALIFICATION",
                         excerpt_only_feed_summary="NATIVE_RIGHTS_REJECTED"),
        git_writes=0, user_database_writes=0, external_model_calls=0, live_news_network_calls=0,
        independent_rereview="PENDING", next_pr_authorized=False)
    write(DELIVERY / "REVIEW_FIX_BASELINE.json", result)
    print(json.dumps(dict(status=result["status"], sha256=sha(DELIVERY / "REVIEW_FIX_BASELINE.json"),
                          source_sha256=result["source"]["sha256"])))


if __name__ == "__main__":
    main()
