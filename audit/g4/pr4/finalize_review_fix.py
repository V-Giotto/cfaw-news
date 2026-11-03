"""Append-only PR4 repair evidence; frozen upstream tests/reports remain historical."""

import argparse
import json
import subprocess
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

from cfaw_news.intelligence.history_store import MIGRATION
from cfaw_news.intelligence.native import ENGINE_PIN, verify
from cfaw_news.intelligence.runtime_contracts import FACT_PIN, RANK_PIN

from audit.g4.pr4.finalize import counts, nodes, read, sha, write
from evals.intelligence_g2.contracts import digest
from evals.intelligence_g2.pr6.junit_inventory import verify_junit
from evals.intelligence_g3.junit_inventory import verify_inventory
from evals.intelligence_g3.pytest_runner import verify_execution

ROOT = Path(__file__).resolve().parents[3]
AREA = ROOT / ".tmp/evals/g3/g4-pr4-fix-20261102-001"
DELIVERY = ROOT / "audit/g4/pr4"
MANIFEST = ROOT / "evals/intelligence_g4/manifests/pr4_review_required_tests.json"
PARENTS = ("pr1_required_tests.json", "pr1_review_required_tests.json", "pr2_required_tests.json",
           "pr2_path_review_required_tests.json", "pr3_required_tests.json", "pr3_review_required_tests.json",
           "pr4_required_tests.json")
CHANGED = {"backend/cfaw_news/intelligence/" + p + ".py" for p in
           ("history_store", "checkpoint", "service", "persistence_migrate", "persistence_schema")}
FAILED = {"review-fixes-01": 1, "review-fixes-03": 1}


def files(paths):
    return {p.relative_to(ROOT).as_posix(): sha(p) for p in sorted(set(paths))}


def source_files():
    paths = [ROOT / p for p in CHANGED]
    paths += [ROOT / "backend/cfaw_news/intelligence/corpus_trust.py",
              ROOT / "evals/intelligence_g4/tests/test_pr4_review_fixes.py",
              ROOT / "docs/adr/G4_PERSISTENCE_REVIEW_FIX.md", MANIFEST,
              DELIVERY / "finalize_review_fix.py", DELIVERY / "review_fix_probe.py"]
    paths += list((ROOT / "evals/intelligence_g4/schema/pr4_review_fix").glob("*.json"))
    return files(paths)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare", action="store_true")
    args = parser.parse_args()
    parents = {"evals/intelligence_g4/manifests/" + p: sha(ROOT / "evals/intelligence_g4/manifests" / p)
               for p in PARENTS}
    previous = sorted(n for p in parents for n in read(ROOT / p)["nodes"])
    assert len(previous) == len(set(previous)) == 293
    current = nodes(AREA / "g4-final-03.xml")
    additional = sorted(set(current) - set(previous))
    assert len(current) == len(set(current)) == 316 and len(additional) == 23
    assert set(previous) <= set(current)
    if args.prepare:
        write(MANIFEST, dict(revision="g4-pr4-review-required-tests-v1", parent_manifests=parents,
            nodes=additional, test_source_sha256=files([ROOT / "evals/intelligence_g4/tests/test_pr4_review_fixes.py"])))
        write(AREA / "final-source.json", source_files())
        print("PASS: previous 293 nodes unchanged; 23 additive review nodes and repair source snapshot")
        return
    entry = read(AREA / "entry.json")
    assert subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip() == entry["head"]
    assert subprocess.check_output(["git", "branch", "--show-current"], cwd=ROOT, text=True).strip() == entry["branch"]
    assert not subprocess.check_output(["git", "diff", "--cached", "--name-only"], cwd=ROOT)
    changed = {p for p, pin in entry["files"].items() if sha(ROOT / p) != pin}
    assert changed == CHANGED
    assert all(sha(AREA / "before" / Path(p).name) == entry["files"][p] for p in CHANGED)
    assert source_files() == read(AREA / "final-source.json")
    assert read(MANIFEST)["parent_manifests"] == parents
    assert counts(AREA / "g4-final-03.xml") == dict(nodes=316, passed=316, failure=0, error=0, skipped=0)
    full = verify_junit(verify_inventory(read(AREA / "node_inventory.json")), AREA / "full.xml")
    for mode in ("collect", "full"):
        kw = dict(inventory=str(AREA / "node_inventory.json")) if mode == "collect" else dict(
            junit=str(AREA / "full.xml"), basetemp=str(ROOT / ".tmp/evals/g3/g4-pr4-fix-full-temp-20261102-001"))
        verify_execution(read(AREA / (mode + ".control.json")), mode=mode, **kw)
    records = {p.name.removesuffix(".command.json"): read(p) for p in AREA.glob("*.command.json")}
    for name, row in records.items():
        assert row["exit_code"] == FAILED.get(name, 0), name
        assert sha(ROOT / row["log"]) == row["log_sha256"], name
    assert {"g4-final-03", "full", "collect", "schema-check-final", "ruff-seal-final", "baseline", "frontend-build",
            "walkthrough-final", "prepare-review-seal-final"} <= set(records)
    proof_path = AREA / "walkthrough-final/proof.json"
    proof = read(proof_path)
    assert proof["status"] == "PASS" and digest(proof["files"]) == proof["aggregate_sha256"]
    assert all(sha(ROOT / p) == pin for p, pin in proof["files"].items())
    api = read(AREA / "walkthrough-final/api/proof.json")
    assert api["state"] == "raw_news_only" and api["deliveries"] == 0
    runtime = read(AREA / "walkthrough-final/api/runtime-output.json")
    for candidate in runtime["context"]["replay"]["candidates"]:
        trace = candidate["trace"]
        assert sha(AREA / "walkthrough-final/api" / trace["path"]) == trace["sha256"]
    temporary = ROOT / ".tmp/evals/g3/g4-pr4-fix-g4-final-03-temp-20261102-001"
    probes = {p.relative_to(ROOT).as_posix(): read(p) for p in temporary.rglob("*-proof.json")
              if p.name in {"corpus-rollback-proof.json", "request-namespace-proof.json", "worker-capacity-proof.json"}}
    assert len(probes) == 6
    corpus = next(v for p, v in probes.items() if p.endswith("corpus-rollback-proof.json"))
    assert corpus["post_status"] == 503 and corpus["checkpoint_heads_unchanged"] and corpus["recovery_required"]
    for p, v in probes.items():
        if p.endswith("request-namespace-proof.json"):
            assert v["cancel_status"] == 200 and v["service_state"] == "ready"
        if p.endswith("worker-capacity-proof.json"):
            assert v["actual_active"] == v["actual_started"] == v["peak"] == v["configured_workers"]
    installs = list(temporary.rglob("offline-proof.json"))
    assert len(installs) == 1
    install = read(installs[0])
    assert all(install[k] for k in ("outside_repository_cwd", "missing_native_dependency_rejected",
                                   "exact_installed_dependency_corruption_rejected"))
    wheels = list((installs[0].parent / "wheels").glob("cfaw_news-*.whl"))
    assert len(wheels) == 1
    with zipfile.ZipFile(wheels[0]) as archive:
        for p, pin in source_files().items():
            if p.startswith("backend/"):
                import hashlib
                assert hashlib.sha256(archive.read(p.removeprefix("backend/"))).hexdigest() == pin, p
    verify()
    cases = list(ET.parse(AREA / "full.xml").iter("testcase"))
    g3 = sum(c.get("classname").startswith("tests.evals.g3.") for c in cases)
    assert g3 == 630
    summary = dict(revision="g4-pr4-review-baseline-v1", status="PASS_LOCAL_REPAIR_PENDING_INDEPENDENT_REVIEW",
        head=entry["head"], branch=entry["branch"], source=dict(files=source_files(), sha256=digest(source_files())),
        schema_sha256=files((ROOT / "evals/intelligence_g4/schema/pr4_review_fix").glob("*.json")),
        results=dict(g4=counts(AREA / "g4-final-03.xml"), additive_review_nodes=23, legacy_full=full, g3_in_full=g3,
            ruff="PASS", schema="PASS_20_ARTIFACTS", baseline="PASS", frontend_build="PASS"),
        migration=dict(revision=MIGRATION.REVISION, source_sha256=MIGRATION.source_sha256(), schema_sha256=MIGRATION.schema_sha256()),
        storage_protocol=dict(checkpoint="g4-checkpoint-v2", corpus="g4-corpus-prefix-v1", namespaces=["client", "system"],
            old_checkpoint_automatic_adoption=False, sql_layout_changed=False),
        native_engine_sha256=ENGINE_PIN, ranking_policy_sha256=RANK_PIN, fact_signature_policy_sha256=FACT_PIN,
        configuration_sha256=read(DELIVERY / "BASELINE.json")["configuration"]["sha256"],
        commands=records, expected_failed_iterations=FAILED,
        preservation=dict(entry_files=len(entry["files"]), changed_entry_files=sorted(changed),
            all_old_test_sources_reports_manifests_schemas_unchanged=True, legacy_and_react_unchanged=True, git_writes=0),
        fixture_proofs={p: dict(sha256=sha(ROOT / p), value=v) for p, v in probes.items()},
        walkthrough=dict(path=proof_path.relative_to(ROOT).as_posix(), sha256=sha(proof_path),
            input_sha256=api["runtime_input_sha256"], output_sha256=api["runtime_output_sha256"]),
        offline_install_proof=dict(path=installs[0].relative_to(ROOT).as_posix(), sha256=sha(installs[0]), **install),
        previous_pr4_release_sha256=entry["prior_release_sha256"], previous_pass_is_historical=True,
        external_network_calls=0, external_model_calls=0, user_database_writes=0, next_pr_authorized=False,
        real_focus_radar="BLOCKED", history_scoring="NOT_APPLIED_PR3_V2", independent_review="PENDING")
    write(DELIVERY / "REVIEW_FIX_BASELINE.json", summary)
    print(json.dumps(dict(status=summary["status"], source_sha256=summary["source"]["sha256"],
        baseline_sha256=sha(DELIVERY / "REVIEW_FIX_BASELINE.json"), g4=summary["results"]["g4"], full=full["nodes"])))


if __name__ == "__main__":
    main()
