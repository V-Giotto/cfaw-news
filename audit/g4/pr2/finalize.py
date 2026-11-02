"""Verify PR2 receipts; never modifies upstream source, baseline or test pins."""

import hashlib
import json
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

from cfaw_news.intelligence.contracts import canonical, digest
from cfaw_news.intelligence.migrate import MIGRATION

from evals.intelligence_g2.pr6.junit_inventory import verify_junit
from evals.intelligence_g3.junit_inventory import verify_inventory
from evals.intelligence_g3.pytest_runner import verify_execution

ROOT = Path(__file__).resolve().parents[3]
AREA = ROOT / ".tmp/evals/g3/g4-pr2-20261102-001"
DELIVERY = ROOT / "audit/g4/pr2"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_bytes())


def suite(path):
    cases = list(ET.parse(path).iter("testcase"))
    counts = {tag: sum(c.find(tag) is not None for c in cases)
              for tag in ("failure", "error", "skipped")}
    counts.update(nodes=len(cases), passed=len(cases) - sum(counts.values()))
    return counts


def code_files():
    files = [p for p in (ROOT / "backend/cfaw_news/intelligence").rglob("*.py")]
    files += [ROOT / p for p in ("backend/cfaw_news/ingestion.py",
        "evals/intelligence_g4/tests/test_capture.py", "evals/intelligence_g4/tests/test_migration.py",
        "evals/intelligence_g4/manifests/pr2_required_tests.json", "data/g4_source_policies.json")]
    files += list((ROOT / "evals/intelligence_g4/schema/pr2").glob("*.json"))
    return {p.relative_to(ROOT).as_posix(): sha(p) for p in sorted(files)}


def main():
    entry = read(AREA / "entry.json")
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    assert head == entry["head"]
    assert subprocess.check_output(["git", "branch", "--show-current"], cwd=ROOT,
                                   text=True).strip() == entry["branch"]
    changed = [p for p, pin in entry["files"].items() if sha(ROOT / p) != pin]
    assert changed == ["backend/cfaw_news/ingestion.py"], changed
    upstream = read(ROOT / "audit/g4/pr1/REVIEW_FIX_RELEASE_MANIFEST.json")
    assert all(sha(ROOT / p) == pin for p, pin in upstream["files"].items())
    assert code_files() == read(AREA / "final-source-before.json")
    commands = {p.stem.removesuffix(".command"): read(p) for p in AREA.glob("*.command.json")}
    assert all(sha(ROOT / c["log"]) == c["log_sha256"] for c in commands.values())
    failed_expected = {"ruff-01", "ruff-03"}
    for name, record in commands.items():
        assert record["exit_code"] == (1 if name in failed_expected else 0), name
    required = {"collect", "full", "g4-release", "ruff-release", "schemas-release",
                "schemas-pr1", "baseline", "frontend-build", "storage-proof-release"}
    assert required <= set(commands)
    inventory = verify_inventory(read(AREA / "node_inventory.json"))
    full = verify_junit(inventory, AREA / "full.xml")
    for mode in ("collect", "full"):
        kw = dict(inventory=str(AREA / "node_inventory.json")) if mode == "collect" else dict(
            junit=str(AREA / "full.xml"), basetemp=str(ROOT / ".tmp/evals/g3/g4-pr2-full-temp-20261102-001"))
        verify_execution(read(AREA / (mode + ".control.json")), mode=mode, **kw)
    g4 = suite(AREA / "g4-release.xml")
    assert not (g4["failure"] or g4["error"] or g4["skipped"])
    manifests = [ROOT / "evals/intelligence_g4/manifests" / name for name in (
        "pr1_required_tests.json", "pr1_review_required_tests.json", "pr2_required_tests.json")]
    required_nodes = sorted(n for p in manifests for n in read(p)["nodes"])
    cases = list(ET.parse(AREA / "g4-release.xml").iter("testcase"))
    nodes = sorted(c.get("classname").replace(".", "/") + ".py::" + c.get("name") for c in cases)
    assert nodes == required_nodes and len(nodes) == len(set(nodes))
    for manifest in manifests:
        assert all(sha(ROOT / p) == pin for p, pin in read(manifest)["test_source_sha256"].items())
    pr2 = read(manifests[-1])
    assert all(sha(ROOT / p) == pin for p, pin in pr2["parent_manifests"].items())
    proof = read(AREA / "storage-proof-release/proof.json")
    assert proof["status"] == "PASS" and len(proof["commands"]) == 4
    assert proof["legacy_before_sha256"] == proof["legacy_after_sha256"]
    assert proof["g4_before_rollback_sha256"] == proof["g4_after_restore_sha256"]
    for c in proof["commands"]:
        assert c["exit_code"] == 0
        assert sha(ROOT / c["log"]) == c["log_sha256"]
        assert sha(ROOT / c["receipt"]) == c["receipt_sha256"]
        receipt = read(ROOT / c["receipt"])
        if "migration_sha256" in receipt:
            assert receipt["migration_sha256"] == MIGRATION.source_sha256()
            assert receipt["schema_sha256"] == MIGRATION.schema_sha256()
    historical = read(AREA / "upstream-check.json")
    assert all(sha(ROOT / c["log"]) == c["log_sha256"]
               for c in historical["commands"].values())
    code = code_files()
    tools = {p.relative_to(ROOT).as_posix(): sha(p) for p in DELIVERY.glob("*.py")}
    result = dict(revision="g4-pr2-baseline-v1", status="PASS_PR2_SCOPE_PENDING_INDEPENDENT_REVIEW",
        head=head, branch=entry["branch"], source=dict(files=code, sha256=digest(code)),
        audit_tools=tools, configuration_sha256=sha(ROOT / "data/g4_source_policies.json"),
        migration=dict(revision=MIGRATION.REVISION, source_sha256=MIGRATION.source_sha256(),
                       schema_sha256=MIGRATION.schema_sha256()),
        results=dict(g4=g4, full=full, ruff="PASS", schema="PASS", baseline="PASS", build="PASS"),
        commands=commands, interrupted_run=read(AREA / "interrupted-run.json"),
        upstream=dict(review_reference_sha256=sha(DELIVERY / "UPSTREAM_REVIEW.json"),
                      historical_receipts=historical, prior_release_sha256=sha(
                          ROOT / "audit/g4/pr1/REVIEW_FIX_RELEASE_MANIFEST.json")),
        preservation=dict(entry_files=len(entry["files"]), changed_authorized=changed,
                          upstream_release_files_unchanged=len(upstream["files"]),
                          frozen_g1_g2_g3_tests_and_schemas_unchanged=True),
        storage_proof=dict(path=str((AREA / "storage-proof-release/proof.json").relative_to(ROOT)),
                           sha256=sha(AREA / "storage-proof-release/proof.json"),
                           legacy_sha256=proof["legacy_before_sha256"],
                           ledger_sha256=proof["g4_before_rollback_sha256"],
                           backup_sha256=proof["restored_backup_sha256"]),
        user_database_migrated=False, live_network_calls=0, external_model_calls=0,
        runtime_g2_g3_generation=False, g4_pr3_authorized=False)
    with (DELIVERY / "BASELINE.json").open("xb") as stream:
        stream.write(canonical(result))
    print(json.dumps(dict(status=result["status"], baseline_sha256=sha(DELIVERY / "BASELINE.json"),
                          source_sha256=result["source"]["sha256"], results=result["results"])))


if __name__ == "__main__":
    main()
