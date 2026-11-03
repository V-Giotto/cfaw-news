"""Seal actual PR4 receipts, additive inventory and preserved upstream bytes; no Git writes."""

import argparse
import hashlib
import json
import sqlite3
import subprocess
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import sqlalchemy
from cfaw_news.config import Settings
from cfaw_news.intelligence.history_store import MIGRATION
from cfaw_news.intelligence.native import ENGINE_PIN, verify
from cfaw_news.intelligence.runtime_contracts import FACT_PIN, RANK_PIN

from evals.intelligence_g2.contracts import digest, json_bytes
from evals.intelligence_g2.pr6.junit_inventory import verify_junit
from evals.intelligence_g3.junit_inventory import verify_inventory
from evals.intelligence_g3.pytest_runner import verify_execution

ROOT = Path(__file__).resolve().parents[3]
AREA = ROOT / ".tmp/evals/g3/g4-pr4-20261102-001"
DELIVERY = ROOT / "audit/g4/pr4"
MANIFEST = ROOT / "evals/intelligence_g4/manifests/pr4_required_tests.json"
PARENTS = ("pr1_required_tests.json", "pr1_review_required_tests.json", "pr2_required_tests.json",
           "pr2_path_review_required_tests.json", "pr3_required_tests.json", "pr3_review_required_tests.json")
TESTS = ("persistence_support.py", "test_history_db.py", "test_persistence_migration.py",
         "test_intelligence_api.py", "test_publication_races.py", "test_persistence_boundaries.py")
CHANGED = {"backend/cfaw_news/main.py", "backend/cfaw_news/config.py", "backend/cfaw_news/intelligence/runtime.py"}
FAILED = {"history-01": 1, "api-01": 1, "api-02": 1, "api-03": 1, "races-01": 1}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_bytes())


def write(path, value):
    with path.open("xb") as stream:
        stream.write(json_bytes(value))


def files(paths):
    return {p.relative_to(ROOT).as_posix(): sha(p) for p in sorted(set(paths))}


def source_files():
    paths = list((ROOT / "backend/cfaw_news/intelligence").rglob("*.py"))
    paths += [ROOT / p for p in CHANGED]
    paths += list((ROOT / "evals/intelligence_g4/tests").glob("*.py"))
    paths += list((ROOT / "evals/intelligence_g4/schema/pr4").glob("*.json"))
    paths += [ROOT / "docs/adr/G4_PERSISTENCE_V1.md", MANIFEST]
    paths += list(DELIVERY.glob("*.py"))
    return files(paths)


def nodes(path):
    return sorted(c.get("classname").replace(".", "/") + ".py::" + c.get("name")
                  for c in ET.parse(path).iter("testcase"))


def counts(path):
    cases = list(ET.parse(path).iter("testcase"))
    values = {tag: sum(c.find(tag) is not None for c in cases) for tag in ("failure", "error", "skipped")}
    return dict(nodes=len(cases), passed=len(cases) - sum(values.values()), **values)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare", action="store_true")
    args = parser.parse_args()
    parents = {"evals/intelligence_g4/manifests/" + p: sha(ROOT / "evals/intelligence_g4/manifests" / p)
               for p in PARENTS}
    previous = sorted(n for p in parents for n in read(ROOT / p)["nodes"])
    current = nodes(AREA / "g4-seal.xml")
    assert len(set(previous)) == len(previous) == 237
    assert len(set(current)) == len(current) == 293
    additional = sorted(set(current) - set(previous))
    assert len(additional) == 56 and set(previous) <= set(current)
    if args.prepare:
        write(MANIFEST, dict(revision="g4-pr4-required-tests-v1", parent_manifests=parents,
            nodes=additional, test_source_sha256=files(ROOT / "evals/intelligence_g4/tests" / p for p in TESTS)))
        write(AREA / "final-source.json", source_files())
        with (DELIVERY / "SCHEMA.sql").open("x", encoding="utf-8", newline="\n") as stream:
            stream.write("-- Generated 002_g4_briefings_v1; exact schema/source pins are in BASELINE.json.\n")
            stream.write(";\n".join(MIGRATION.statements()) + ";\n")
        print("PASS: 56 additive nodes, source snapshot and explicit DDL registered")
        return
    entry = read(AREA / "entry.json")
    assert subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip() == entry["head"]
    assert subprocess.check_output(["git", "branch", "--show-current"], cwd=ROOT, text=True).strip() == entry["branch"]
    assert not subprocess.check_output(["git", "diff", "--cached", "--name-only"], cwd=ROOT)
    changed = {p for p, pin in entry["files"].items() if sha(ROOT / p) != pin}
    assert changed == CHANGED
    assert all(sha(AREA / "source-before" / p) == entry["files"][p] for p in CHANGED)
    assert source_files() == read(AREA / "final-source.json")
    manifest = read(MANIFEST)
    assert manifest["nodes"] == additional and manifest["parent_manifests"] == parents
    assert all(sha(ROOT / p) == pin for p, pin in manifest["test_source_sha256"].items())
    assert counts(AREA / "g4-seal.xml") == dict(nodes=293, passed=293, failure=0, error=0, skipped=0)
    inventory = verify_inventory(read(AREA / "node_inventory.json"))
    full = verify_junit(inventory, AREA / "full.xml")
    for mode in ("collect", "full"):
        kw = dict(inventory=str(AREA / "node_inventory.json")) if mode == "collect" else dict(
            junit=str(AREA / "full.xml"), basetemp=str(ROOT / ".tmp/evals/g3/g4-pr4-full-temp-20261102-001"))
        verify_execution(read(AREA / (mode + ".control.json")), mode=mode, **kw)
    # All commands before this sealing call; never overwrite or relabel failed iterations.
    records = {p.name.removesuffix(".command.json"): read(p) for p in AREA.glob("*.command.json")}
    for name, record in records.items():
        assert record["exit_code"] == FAILED.get(name, 0), name
        assert sha(ROOT / record["log"]) == record["log_sha256"], name
    assert {"g4-seal", "full", "collect", "schema-seal", "ruff-seal", "baseline", "frontend-build",
            "local-proof-final", "prepare-seal"} <= set(records)
    proof_path = AREA / "proof-final/proof.json"
    proof = read(proof_path)
    assert proof["status"] == "PASS" and digest(proof["files"]) == proof["aggregate_sha256"]
    assert all(sha(ROOT / p) == pin for p, pin in proof["files"].items())
    api = read(AREA / "proof-final/api/proof.json")
    assert api["state"] == "raw_news_only" and api["deliveries"] == 0 and api["full_archive"] == 1
    runtime = read(AREA / "proof-final/api/runtime-output.json")
    for candidate in runtime["context"]["replay"]["candidates"]:
        trace = candidate["trace"]
        assert sha(AREA / "proof-final/api" / trace["path"]) == trace["sha256"]
    install_paths = list((ROOT / ".tmp/evals/g3/g4-pr4-seal-temp-20261102-001").rglob("offline-proof.json"))
    assert len(install_paths) == 1
    install = read(install_paths[0])
    assert all(install[k] for k in ("outside_repository_cwd", "missing_native_dependency_rejected",
                                   "exact_installed_dependency_corruption_rejected"))
    wheels = sorted((install_paths[0].parent / "wheels").glob("cfaw_news-*.whl"))
    assert len(wheels) == 1
    with zipfile.ZipFile(wheels[0]) as archive:
        for path, pin in source_files().items():
            if path.startswith("backend/"):
                assert hashlib.sha256(archive.read(path.removeprefix("backend/"))).hexdigest() == pin, path
    verify()
    cases = list(ET.parse(AREA / "full.xml").iter("testcase"))
    g3 = sum(c.get("classname").startswith("tests.evals.g3.") for c in cases)
    assert g3 == 630
    defaults = {k: v.default for k, v in Settings.model_fields.items() if k.startswith("intelligence_")}
    sources = source_files()
    summary = dict(revision="g4-pr4-baseline-v1", head=entry["head"], branch=entry["branch"],
        status="PASS_LOCAL_SCOPE_PENDING_INDEPENDENT_REVIEW", source=dict(files=sources, sha256=digest(sources)),
        schema_sha256=files((ROOT / "evals/intelligence_g4/schema/pr4").glob("*.json")),
        migration=dict(revision=MIGRATION.REVISION, source_sha256=MIGRATION.source_sha256(),
                       schema_sha256=MIGRATION.schema_sha256(), ddl_sha256=sha(DELIVERY / "SCHEMA.sql")),
        versions=dict(sqlite=sqlite3.sqlite_version, sqlalchemy=sqlalchemy.__version__),
        native_engine_sha256=ENGINE_PIN, ranking_policy_sha256=RANK_PIN, fact_signature_policy_sha256=FACT_PIN,
        configuration=dict(defaults=defaults, sha256=digest(defaults), enabled_by_default=False),
        results=dict(g4=counts(AREA / "g4-seal.xml"), additive_required_nodes=56, legacy_full=full,
            g3_nodes_in_full=g3, fact_signature_nodes_in_full=sum(
                c.get("classname").startswith("tests.evals.g3.test_fact_signature") for c in cases),
            ruff="PASS", schema_artifacts=18, baseline="PASS", frontend_build="PASS"),
        commands=records, expected_failed_iterations=FAILED,
        preservation=dict(entry_files=len(entry["files"]), changed_entry_files=sorted(changed),
            source_before_sha256={p: entry["files"][p] for p in sorted(changed)},
            frozen_g1_g2_g3_unchanged=True, previous_reports_manifests_schema_unchanged=True,
            legacy_database_service_react_unchanged=True, git_writes=0),
        proof=dict(path=proof_path.relative_to(ROOT).as_posix(), sha256=sha(proof_path),
                   input_sha256=api["runtime_input_sha256"], output_sha256=api["runtime_output_sha256"]),
        offline_install_proof=dict(path=install_paths[0].relative_to(ROOT).as_posix(), sha256=sha(install_paths[0]), **install),
        upstream_review=dict(path="audit/g4/pr3/RE_REVIEW.md", sha256=sha(ROOT / "audit/g4/pr3/RE_REVIEW.md"),
                             historical_not_pr4_tests=True),
        operational_limits=dict(history_scoring="NOT_APPLIED_PR3_V2", real_focus_radar="BLOCKED_EVIDENCE_INDEPENDENCE_UNKNOWN",
            historical_persona_continuity="BLOCKED_WHEN_NATIVE_HISTORY_MISSING", automatic_rebase=False,
            rollback_database_and_checkpoint_together_detected=False, hardware_power_cut_tested=False),
        external_news_network_calls=0, external_model_calls=0, user_database_writes=0,
        browser_e2e="NOT_EVALUATED_NO_REACT_CHANGE", independent_review="PENDING", next_pr_authorized=False)
    write(DELIVERY / "BASELINE.json", summary)
    print(json.dumps(dict(status=summary["status"], source_sha256=summary["source"]["sha256"],
        baseline_sha256=sha(DELIVERY / "BASELINE.json"), results=summary["results"])))


if __name__ == "__main__":
    main()
