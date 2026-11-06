"""Seal the separate H09 repair after checks; --verify-only never writes artifacts."""

import argparse
import importlib.metadata
import json
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

from audit.g4.h09.proof import RUN, protected, read
from audit.g4.pr6.freeze import ROOT, sha
from audit.g4.pr6.seal import build_roots, pin, verify_roots, write_new

RELEASE = ROOT / "audit/G4_H09_REPAIR_MANIFEST.json"
REQUIRED = ("full-final", "g4-final", "build-current", "frontend-unit", "ruff-delivery", "baseline-final",
            "collect-final", "schema-check-final", "native-schema-export", "native-schema-check",
            "types-final", "browser-retry", "legacy-replay-final", "proof-final")


def cases(path):
    root = ET.parse(path).getroot()
    result = dict(tests=0, passed=0, failed=0, skipped=0, seconds=0.0)
    for case in root.iter("testcase"):
        result["tests"] += 1
        result["seconds"] += float(case.attrib.get("time", 0))
        key = "failed" if case.find("failure") is not None or case.find("error") is not None else "skipped" if case.find("skipped") is not None else "passed"
        result[key] += 1
    return result


def receipt_checks():
    records = {p.stem.removesuffix(".command"): read(p) for p in RUN.glob("*.command.json")}
    for record in records.values():
        assert sha(ROOT / record["log"]) == record["log_sha256"]
    assert all(records[n]["exit_code"] == 0 for n in REQUIRED)
    assert records["full-registered"]["exit_code"] == 1
    for name in ("contracts", "pilot", "strict-focus"):
        record = read(RUN / f"browser-retry/{name}.command.json")
        assert record["exit_code"] == 0 and sha(ROOT / record["log"]) == record["log_sha256"]
        assert record["environment"]["CFAW_PR6_PILOT"] == "pilot-retry"
        assert sha(Path(record["fixtures"]["path"])) == record["fixtures"]["sha256"]
        assert record["environment"]["CFAW_PR5_OUT"] == str(Path(record["fixtures"]["path"]).parent)
        for service in record["active_services"]:
            assert sha(Path(service["config"])) == service["config_sha256"]
    lifecycle = read(RUN / "browser-retry/lifecycle.json")
    assert lifecycle["status"] == "PASS" and lifecycle["browser_exit_code"] == 0
    assert lifecycle["service_exit_codes"] == [0, 0, 0]
    for name in ("contract", "pilot", "development"):
        record = read(RUN / f"browser-retry/{name}.service.json")
        assert record["exit_code"] == 0 and record["stop_method"].startswith("stdin STOP")
        assert sha(ROOT / record["log"]) == record["log_sha256"]
        assert sha(Path(record["config"])) == record["config_sha256"]
    config = read(RUN / "browser-retry/pilot.config.json")
    assert config["qa_delay_seconds"] == 2 and not any(config[k] for k in ("news_auto_refresh", "news_media_fetch", "news_reading_fetch"))
    contract = read(RUN / "browser-contracts-native/browser-results.json")
    pilot = read(RUN / "browser-pilot-retry/result.json")
    focus = read(RUN / "browser-retry/focus/focus-result.json")
    assert contract["status"] == pilot["status"] == focus["status"] == "PASS"
    assert len(contract["checks"]) == 27 and len(pilot["checks"]) == 11
    assert not pilot["external_attempts"] and not pilot["page_errors"]
    assert focus["strict_mode"] and focus["cycles"] == 3 and len(focus["checks"]) == 5
    assert read(RUN / "legacy-replay-final/result.json")["original_backup_unchanged"]
    full, g4 = cases(RUN / "full-final.xml"), cases(RUN / "g4-final.xml")
    assert full["tests"] == 1754 and full["failed"] == 0 and full["skipped"] == 1
    assert g4["tests"] == g4["passed"] == 339
    return dict(commands=records, full=full, g4=g4, browser=dict(contract_groups=27, pilot_groups=11,
        focus_checks=5, focus_cycles=3, browser_version=pilot["browser_version"], lifecycle="PASS"))


def snapshot():
    names = subprocess.check_output(["git", "ls-files", "--cached", "--others", "--exclude-standard"], cwd=ROOT, text=True).splitlines()
    assert not subprocess.check_output(["git", "diff", "--cached", "--name-only"], cwd=ROOT, text=True).strip()
    assert "/dev-diaries/" in (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    names = sorted({n for n in names if not n.startswith(("dev-diaries/", ".tmp/", ".local/", ".venv/", "frontend/node_modules/", "frontend/dist/"))
                    and n != RELEASE.relative_to(ROOT).as_posix() and (ROOT / n).is_file()})
    assert not any(n.endswith((".db", ".sqlite", ".sqlite3")) or n == ".env" or n.endswith("/.env") for n in names)
    target = RUN / "source-snapshot"
    target.mkdir(exist_ok=False)
    hashes = {}
    for name in names:
        dest = target / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, dest)
        hashes[name] = sha(dest)
        assert hashes[name] == sha(ROOT / name)
    entry = read(RUN / "entry.json")["files"]
    return hashes, {n: dict(before=h, after=hashes.get(n)) for n, h in entry.items() if hashes.get(n) != h}


def toolchain():
    old = read(ROOT / "audit/g4/pr6/ENTRY_FREEZE.json")
    distributions = sorted({(d.metadata["Name"], d.version) for d in importlib.metadata.distributions()})
    assert [list(d) for d in distributions] == old["python_distributions"]
    receipt = read(RUN / "browser-retry/contracts.command.json")
    modules = Path(receipt["argv"][-1])
    libraries = {}
    for name in ("playwright", "playwright-core"):
        folder = modules / name
        libraries[name] = dict(version=read(folder / "package.json")["version"],
            files={p.relative_to(folder).as_posix(): pin(p) for p in folder.rglob("*") if p.is_file()})
    return dict(python=sys.version, python_distributions=distributions, python_executable=pin(Path(sys.executable)),
        node_version=subprocess.check_output(["node", "--version"], text=True).strip(),
        node_executable=pin(Path(shutil.which("node"))), browser_executable=pin(Path("C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe")),
        libraries=libraries)


def gates():
    references = {
        "H00": ["docs/G4_G5_HANDOFF.md", "audit/g4/pr2/UPSTREAM_REVIEW.json"],
        "H01": ["audit/g4/pr6/samples/vite-8.3.4/PROVENANCE.json", "audit/g4/pr6/samples/vite-8.3.4/LICENSE.md", "pilot-retry/result.json"],
        "H02": ["g4-final.xml", "legacy-replay-final/result.json"],
        "H03": ["g4-final.xml", "browser-contracts-native/browser-results.json"],
        "H04": ["g4-final.xml", "sqlite-proof.json"],
        "H05": ["g4-final.xml", "legacy-replay-final/result.json", "audit/g4/pr6/REVIEW_FIX_RESULTS.json"],
        "H06": ["g4-final.xml", "browser-contracts-native/browser-results.json", "browser-pilot-retry/result.json"],
        "H07": ["g4-final.xml", "browser-pilot-retry/result.json", "browser-retry/pilot.config.json"],
        "H08": ["g4-final.xml", "browser-retry/pilot.service.json"],
        "H09": ["evals/intelligence_g4/tests/test_h09_continuity.py", "g4-final.xml", "sqlite-proof.json", "browser-pilot-retry/result.json", "legacy-replay-final/result.json"],
        "H10": ["full-final.xml", "control-verification.json", "protected-verification.json", "browser-pilot-retry/result.json"],
        "H11": ["browser-retry/lifecycle.json", "browser-contracts-native/browser-results.json", "browser-pilot-retry/result.json"],
        "H12": ["docs/G4_ACCEPTANCE.md", "docs/G4_G5_HANDOFF.md", "docs/G4_BETA_USER_GUIDE.md", "audit/g4/h09/REPAIR_REPORT.md"],
    }
    result = {}
    for line in (ROOT / "docs/G4_ACCEPTANCE.md").read_text(encoding="utf-8").splitlines():
        if not line.startswith("| H"):
            continue
        key, status, reason = (v.strip() for v in line.strip("|").split("|"))
        key = key.split()[0]
        paths = [ROOT / n if n.startswith(("audit/", "docs/", "evals/")) else RUN / n for n in references[key]]
        result[key] = dict(status=status, failure_or_limit=reason,
                           artifacts={p.relative_to(ROOT).as_posix(): pin(p) for p in paths})
    assert len(result) == 13
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    if args.verify_only:
        release = read(RELEASE)
        for name, expected in release["source_files_sha256"].items():
            assert sha(ROOT / name) == expected, name
        protected()
        print(json.dumps(verify_roots(release["roots"])))
        return
    assert not RELEASE.exists()
    preserved = protected()
    results = receipt_checks()
    write_new(RUN / "toolchain.json", toolchain())
    write_new(RUN / "seed-baseline.json", read(ROOT / ".local/evals/baseline.json"))
    files, changes = snapshot()
    result = dict(revision="g4-h09-repair-results-v1", **results, entry_changes=changes,
        protected_files=len(preserved["frozen_files"]), status="PASS_LOCAL_ENGINEERING_PENDING_REVIEW")
    write_new(RUN / "results.json", result)
    folders = [RUN, *sorted((ROOT / ".tmp/evals/g3").glob("h09-*"))]
    assert all(p.is_dir() for p in folders)
    roots = build_roots(folders)
    verified = verify_roots(roots)  # Never publish a seal before validating every nested reference.
    policy = read(ROOT / "evals/intelligence_g4/schema/h09_v2/Version.json")
    write_new(RELEASE, dict(revision="g4-h09-repair-release-v1", created_at=datetime.now(timezone.utc).isoformat(),
        head=read(RUN / "entry.json")["head"], working_tree_uncommitted=True,
        source_files_sha256=files, roots=roots, recursive_verification=verified, result=pin(RUN / "results.json"),
        results_path=(RUN / "results.json").relative_to(ROOT).as_posix(), schema=policy,
        prior_historical_seal=dict(path="audit/G4_RELEASE_MANIFEST.json", sha256=preserved["prior_seal_sha256"], applies_to="its historical source-snapshot only"),
        tracks=dict(g4_development="CONDITIONAL_PENDING_REVIEW", g4_beta_utility="OFFLINE_REJECTION_PILOT_PASSED_BETA_PENDING", g4_research_optional="NOT_EVALUATED"),
        gates_source="docs/G4_ACCEPTANCE.md:H00-H12", gates=gates(), h09="PASS_LOCAL_ENGINEERING_PENDING_REVIEW",
        defaults=dict(algorithm="b4", budget_profile="focus70-radar30-v1", budget_seconds=420, estimated=True),
        limits=dict(external_network_smoke="not_evaluated", human_research="not_evaluated", algorithm_gains="not_evaluated",
                    real_qualified_focus_radar="not_evaluated; actual licensed sample remains raw_news_only/hold", owner_beta_approval="pending", independent_total_review="pending"),
        original_user_database_used=False, automatic_push_deploy=False, sensitive_files_or_dev_diaries_submitted=False,
        self_hash="excluded to avoid circularity"))
    print(json.dumps(dict(status="SEALED_AFTER_RECURSIVE_VERIFY", manifest_sha256=sha(RELEASE), verification=verified)))


if __name__ == "__main__":
    main()
