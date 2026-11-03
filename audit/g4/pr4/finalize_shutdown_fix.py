"""Seal the current handoff repair without rewriting earlier PR4 evidence."""

import argparse
import hashlib
import json
import subprocess
import zipfile
from pathlib import Path

from cfaw_news.intelligence.native import verify

from audit.g4.pr4.finalize import counts, nodes, read, sha, write
from evals.intelligence_g2.contracts import digest

ROOT = Path(__file__).resolve().parents[3]
AREA = ROOT / ".tmp/evals/g3/g4-pr4-shutdown-fix-20261103-001"
OUT = ROOT / "audit/g4/pr4"
MANIFEST = ROOT / "evals/intelligence_g4/manifests/pr4_shutdown_required_tests.json"
SERVICE = "backend/cfaw_news/intelligence/service.py"
PARENTS = ("pr1_required_tests.json", "pr1_review_required_tests.json", "pr2_required_tests.json",
    "pr2_path_review_required_tests.json", "pr3_required_tests.json", "pr3_review_required_tests.json",
    "pr4_required_tests.json", "pr4_review_required_tests.json")


def files(paths):
    return {p.relative_to(ROOT).as_posix(): sha(p) for p in sorted(set(paths))}


def sources():
    return files([ROOT / SERVICE, ROOT / "evals/intelligence_g4/tests/test_shutdown_handoff.py", MANIFEST,
                  ROOT / "docs/adr/G4_SHUTDOWN_HANDOFF_FIX.md", OUT / "finalize_shutdown_fix.py"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare", action="store_true")
    args = parser.parse_args()
    parents = {"evals/intelligence_g4/manifests/" + p: sha(ROOT / "evals/intelligence_g4/manifests" / p) for p in PARENTS}
    old = sorted(n for p in parents for n in read(ROOT / p)["nodes"])
    current = nodes(AREA / "g4-final.xml")
    additional = sorted(set(current) - set(old))
    assert len(old) == len(set(old)) == 316
    assert len(current) == len(set(current)) == 318 and set(old) <= set(current) and len(additional) == 2
    if args.prepare:
        write(MANIFEST, dict(revision="g4-pr4-shutdown-required-tests-v1", parent_manifests=parents,
            nodes=additional, test_source_sha256=files([ROOT / "evals/intelligence_g4/tests/test_shutdown_handoff.py"])))
        write(AREA / "final-source.json", sources())
        print("PASS: 316 old nodes unchanged, 2 additive handoff cases and source snapshot")
        return
    entry = read(AREA / "entry.json")
    assert subprocess.check_output(["git", "rev-parse", "HEAD"], text=True, cwd=ROOT).strip() == entry["head"]
    assert subprocess.check_output(["git", "branch", "--show-current"], text=True, cwd=ROOT).strip() == entry["branch"]
    assert not subprocess.check_output(["git", "diff", "--cached", "--name-only"], cwd=ROOT)
    assert {p for p, pin in entry["files"].items() if sha(ROOT / p) != pin} == {SERVICE}
    assert sha(AREA / "service-before.py") == entry["files"][SERVICE]
    assert sources() == read(AREA / "final-source.json")
    assert counts(AREA / "g4-final.xml") == dict(nodes=318, passed=318, failure=0, error=0, skipped=0)
    assert counts(AREA / "regression-red.xml")["failure"] == 2
    backend = counts(AREA / "backend.xml")
    assert backend["passed"] == backend["nodes"] and not backend["skipped"]
    records = {p.name.removesuffix(".command.json"): read(p) for p in AREA.glob("*.command.json")}
    for name, row in records.items():
        assert row["exit_code"] == (1 if name == "regression-red" else 0), name
        assert sha(ROOT / row["log"]) == row["log_sha256"], name
    assert {"g4-final", "regression-red", "regression-green", "backend-regression", "schema-check",
            "ruff-final", "baseline", "frontend-build", "prepare-shutdown-seal"} <= set(records)
    temporary = ROOT / ".tmp/evals/g3/g4-pr4-shutdown-final-temp-20261103-001"
    probes = list(temporary.rglob("shutdown-reservation-proof.json"))
    assert len(probes) == 2
    for p in probes:
        row = read(p)
        assert (row["status"] == "PASS" and row["owner_retained_while_start_paused"]
                and row["replacement_before_drain_http"] == 503 and row["old_native_calls"] == 1
                and row["new_native_calls"] == row["total_physical_peak"] == 2
                and row["owner_after_drain_reacquired"] and row["late_publications"] == 0)
        if not row["cancel_waiter"]:
            assert row["owner_retained_during_terminal_cleanup"]
    installs = list(temporary.rglob("offline-proof.json"))
    assert len(installs) == 1
    installed = read(installs[0])
    assert installed["outside_repository_cwd"] and installed["missing_native_dependency_rejected"]
    assert installed["exact_installed_dependency_corruption_rejected"]
    wheel = list((installs[0].parent / "wheels").glob("cfaw_news-*.whl"))
    assert len(wheel) == 1
    with zipfile.ZipFile(wheel[0]) as archive:
        assert hashlib.sha256(archive.read(SERVICE.removeprefix("backend/"))).hexdigest() == sha(ROOT / SERVICE)
    verify()
    prior = read(OUT / "REVIEW_FIX_BASELINE.json")
    summary = dict(revision="g4-pr4-shutdown-baseline-v1", status="PASS_LOCAL_REPAIR_PENDING_INDEPENDENT_REVIEW",
        head=entry["head"], branch=entry["branch"], source=dict(files=sources(), sha256=digest(sources())),
        results=dict(g4=counts(AREA / "g4-final.xml"), backend=backend, new_required_nodes=2,
            schema="PASS_UNCHANGED_20_ARTIFACTS", ruff="PASS", baseline="PASS", frontend_build="PASS"),
        commands=records, expected_failed_iterations={"regression-red": 1},
        probes={p.relative_to(ROOT).as_posix(): dict(sha256=sha(p), value=read(p)) for p in probes},
        offline_install_proof=dict(path=installs[0].relative_to(ROOT).as_posix(), sha256=sha(installs[0]), **installed),
        source_before_sha256=entry["files"][SERVICE],
        native_engine_sha256=prior["native_engine_sha256"], ranking_policy_sha256=prior["ranking_policy_sha256"],
        fact_signature_policy_sha256=prior["fact_signature_policy_sha256"], configuration_sha256=prior["configuration_sha256"],
        preservation=dict(entry_files=len(entry["files"]), changed_entry_files=[SERVICE], old_test_sources_unchanged=True,
            old_reports_manifests_schema_unchanged=True, database_checkpoint_native_algorithms_react_unchanged=True, git_writes=0),
        historical_only=dict(previous_release_sha256=entry["prior_release_sha256"], legacy_full="1753 passed / 1 skipped; NOT_RERUN_THIS_FIX"),
        independent_review="PENDING", external_model_calls=0, external_network_calls=0, user_database_writes=0,
        next_pr_authorized=False)
    write(OUT / "SHUTDOWN_FIX_BASELINE.json", summary)
    print(json.dumps(dict(status=summary["status"], source_sha256=summary["source"]["sha256"],
        baseline_sha256=sha(OUT / "SHUTDOWN_FIX_BASELINE.json"), g4=318, backend=backend)))


if __name__ == "__main__":
    main()
