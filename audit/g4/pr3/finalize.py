"""Verify current PR3 receipts and pins, preserving every upstream tracked byte."""

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
AREA = ROOT / ".tmp/evals/g3/g4-pr3-20261102-001"
DELIVERY = ROOT / "audit/g4/pr3"
PARENTS = ("pr1_required_tests.json", "pr1_review_required_tests.json", "pr2_required_tests.json",
           "pr2_path_review_required_tests.json")
TESTS = ("runtime_support.py", "test_runtime_bridge.py", "test_runtime_identity.py",
         "test_runtime_equivalence.py", "test_runtime_ledger.py", "test_runtime_cli.py", "test_offline_install.py")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_bytes())


def write(path, value):
    with path.open("xb") as stream:
        stream.write(json_bytes(value))


def nodes(path):
    return sorted(c.get("classname").replace(".", "/") + ".py::" + c.get("name")
                  for c in ET.parse(path).iter("testcase"))


def counts(path):
    cases = list(ET.parse(path).iter("testcase"))
    values = {tag: sum(c.find(tag) is not None for c in cases) for tag in ("failure", "error", "skipped")}
    return dict(nodes=len(cases), passed=len(cases) - sum(values.values()), **values)


def source_files():
    files = [ROOT / "backend/cfaw_news/intelligence" / (name + ".py") for name in (
        "native", "native_lock", "g2_adapter", "g3_adapter", "runtime", "runtime_contracts", "runtime_schema")]
    files += [ROOT / "evals/intelligence_g4/tests" / name for name in TESTS]
    files += [ROOT / "scripts/build_g4_native.py", ROOT / "evals/intelligence_g4/manifests/pr3_required_tests.json"]
    files += sorted((ROOT / "evals/intelligence_g4/schema/pr3").glob("*.json"))
    files += sorted(DELIVERY.glob("*.py"))
    return {p.relative_to(ROOT).as_posix(): sha(p) for p in sorted(files)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--iteration", choices=("01", "02"), default="02")
    args = parser.parse_args()
    label = "g4-final" if args.iteration == "01" else "g4-final-02"
    seal = AREA / ("final-source-before.json" if args.iteration == "01" else "final-source-before-02.json")
    manifest_path = ROOT / "evals/intelligence_g4/manifests/pr3_required_tests.json"
    parents = {"evals/intelligence_g4/manifests/" + p: sha(ROOT / "evals/intelligence_g4/manifests" / p)
               for p in PARENTS}
    if args.prepare:
        previous = {n for p in parents for n in read(ROOT / p)["nodes"]}
        current = sorted(set(nodes(AREA / "g4-01.xml")) - previous)
        if args.iteration == "02":
            current.append("evals/intelligence_g4/tests/test_runtime_identity.py::"
                           "test_future_cutoff_rejected_by_direct_envelope_json_import")
        assert len(previous) == 164 and len(current) == (50 if args.iteration == "01" else 51)
        payload = dict(revision="g4-pr3-required-tests-v1", parent_manifests=parents,
            nodes=current, test_source_sha256={"evals/intelligence_g4/tests/" + p:
                sha(ROOT / "evals/intelligence_g4/tests" / p) for p in TESTS},
            native_equivalence_test_dependencies={p: sha(ROOT / p) for p in (
                "tests/evals/g3/history_support.py", "tests/evals/g3/ranking_support.py")})
        if manifest_path.exists():
            write(AREA / "pr3-required-tests-seal-01.json", read(manifest_path))
            manifest_path.write_bytes(json_bytes(payload))
        else:
            write(manifest_path, payload)
        write(seal, source_files())
        print(f"PR3: {len(current)} additive required nodes and final source snapshot registered")
        return
    entry = read(AREA / "entry.json")
    assert subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip() == entry["head"]
    assert subprocess.check_output(["git", "branch", "--show-current"], cwd=ROOT, text=True).strip() == entry["branch"]
    assert not subprocess.check_output(["git", "diff", "--cached", "--name-only"], cwd=ROOT)
    assert all(sha(ROOT / p) == pin for p, pin in entry["files"].items())
    assert source_files() == read(seal)
    assert all(sha(ROOT / p) == pin for p, pin in parents.items())
    manifest = read(manifest_path)
    assert manifest["parent_manifests"] == parents
    assert all(sha(ROOT / p) == pin for p, pin in manifest["test_source_sha256"].items())
    assert all(sha(ROOT / p) == pin for p, pin in manifest["native_equivalence_test_dependencies"].items())
    expected = sorted(manifest["nodes"] + [n for p in parents for n in read(ROOT / p)["nodes"]])
    assert nodes(AREA / (label + ".xml")) == expected and len(set(expected)) == 164 + len(manifest["nodes"])
    g4 = counts(AREA / (label + ".xml"))
    assert g4["passed"] == len(expected) and not any(g4[t] for t in ("failure", "error", "skipped"))
    inventory = verify_inventory(read(AREA / "node_inventory.json"))
    full = verify_junit(inventory, AREA / "full.xml")
    for mode in ("collect", "full"):
        kw = dict(inventory=str(AREA / "node_inventory.json")) if mode == "collect" else dict(
            junit=str(AREA / "full.xml"), basetemp=str(ROOT / ".tmp/evals/g3/g4-pr3-full-temp-20261102-001"))
        verify_execution(read(AREA / ("collect.control.json" if mode == "collect" else "full.control.json")),
                         mode=mode, **kw)
    records = {p.stem.removesuffix(".command"): read(p) for p in AREA.glob("*.command.json")}
    known_failures = {"runtime-01": 1, "runtime-02": 1, "runtime-03": 1, "runtime-05": 1,
                      "equivalence-install-01": 1, "ruff-01": 1, "schema-pr2": 2}
    for name, record in records.items():
        assert record["exit_code"] == known_failures.get(name, 0), name
        assert sha(ROOT / record["log"]) == record["log_sha256"]
    assert {label, "full", "ruff-final", "schema-pr3", "schema-pr1", "schema-pr2-corrected",
            "baseline", "frontend-build", "cli-proof-final"} <= set(records)
    proof_path = AREA / ("cli-proof-final/proof.json" if args.iteration == "01" else "cli-proof-final-02/proof.json")
    proof = read(proof_path)
    assert proof["status"] == "PASS" and len(proof["executions"]) == 7
    for item in proof["executions"]:
        receipt = ROOT / item["path"]
        assert sha(receipt) == item["sha256"]
        row = read(receipt)
        assert row["exit_code"] == row["expected_exit_code"]
        assert all(sha(receipt.parent / p) == pin for p, pin in row["files"].items())
    installs = list((AREA / (label + "-temp")).rglob("offline-proof.json"))
    assert len(installs) == 1
    install = read(installs[0])
    assert install["outside_repository_cwd"] and install["missing_native_dependency_rejected"]
    assert install["exact_installed_dependency_corruption_rejected"]
    verify()
    config = RuntimeConfig(budget=ExplicitBudget(profile="focus70-radar30-v1"))
    sources = source_files()
    cases = list(ET.parse(AREA / "full.xml").iter("testcase"))
    g3_count = sum(c.get("classname").startswith("tests.evals.g3.") for c in cases)
    fact_count = sum(c.get("classname").startswith("tests.evals.g3.test_fact_signature") for c in cases)
    assert g3_count == 630
    result = dict(revision="g4-pr3-baseline-v1", head=entry["head"], branch=entry["branch"],
        status="PASS_LOCAL_SCOPE_PENDING_INDEPENDENT_REVIEW", real_recommendations="BLOCKED_EVIDENCE_INDEPENDENCE_UNKNOWN",
        source=dict(files=sources, sha256=digest(sources)),
        schema_sha256={p.relative_to(ROOT).as_posix(): sha(p) for p in
                       sorted((ROOT / "evals/intelligence_g4/schema/pr3").glob("*.json"))},
        native_engine_sha256=ENGINE_PIN, ranking_policy_sha256=RANK_PIN, fact_signature_policy_sha256=FACT_PIN,
        development_config=dict(value=data(config), sha256=digest(config)),
        results=dict(g4=g4, full=full, g3_nodes_in_full=g3_count, fact_signature_nodes_in_full=fact_count,
                     ruff="PASS", schema="PASS", baseline="PASS", frontend_build="PASS"),
        commands=records, expected_failed_iterations=known_failures,
        preservation=dict(entry_tracked_files=len(entry["files"]), changed_entry_files=[],
            frozen_g1_g2_g3_unchanged=True, previous_g4_assets_unchanged=True, git_writes=0),
        cli_proof=dict(path=proof_path.relative_to(ROOT).as_posix(), sha256=sha(proof_path)),
        offline_install_proof=dict(path=installs[0].relative_to(ROOT).as_posix(), sha256=sha(installs[0]), **install),
        historical_upstream_review=dict(path="audit/g4/pr2/RE_REVIEW.md", sha256=sha(ROOT / "audit/g4/pr2/RE_REVIEW.md")),
        live_news_network_calls=0, external_model_calls=0, user_database_writes=0,
        production_history="NOT_IMPLEMENTED_PR4", browser_e2e="NOT_EVALUATED_NO_FRONTEND_CHANGE",
        independent_review="PENDING", administrator_acceptance="PENDING", next_pr_authorized=False)
    write(DELIVERY / "BASELINE.json", result)
    print(json.dumps(dict(status=result["status"], source_sha256=result["source"]["sha256"],
                          baseline_sha256=sha(DELIVERY / "BASELINE.json"), results=result["results"])))


if __name__ == "__main__":
    main()
