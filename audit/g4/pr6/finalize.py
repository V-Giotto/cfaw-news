"""PR6 v2 seal utilities; keep the original entry and research assets immutable."""

import json
import shutil
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

from audit.g4.pr6.freeze import ROOT, sha, write

QA = ROOT / "audit/g4/pr6"
RUN = ROOT / ".tmp/evals/g3/g4-pr6-review-fix-20261105-001"
RELEASE = ROOT / "audit/G4_RELEASE_MANIFEST.json"
DOCS = ["docs/G4_ACCEPTANCE.md", "docs/G4_G5_HANDOFF.md", "docs/G4_BETA_USER_GUIDE.md"]
TRACKS = {
    "g4_development": "CONDITIONAL_PENDING_REVIEW",
    "g4_beta_utility": "OFFLINE_REJECTION_PILOT_PASSED_BETA_PENDING",
    "g4_research_optional": "NOT_EVALUATED",
}


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def pin(path):
    return dict(sha256=sha(path), bytes=path.stat().st_size)


def rel(path):
    return path.relative_to(ROOT).as_posix()


def verify_controls():
    """Validate frozen control evidence without creating or updating artifacts."""
    from evals.intelligence_g3.junit_inventory import verify_inventory, verify_junit
    from evals.intelligence_g3.pytest_runner import verify_execution

    inventory = read(RUN / "inventory.json")
    full = read(RUN / "full-final-control.json")
    collect = read(RUN / "collect-control.json")
    verify_execution(full, mode="full", junit=str(RUN / "full-final.xml"),
                     basetemp=str(ROOT / ".tmp/evals/g3/p6-fix-full-final"))
    verify_execution(collect, mode="collect", inventory=str(RUN / "inventory.json"))
    required = verify_inventory(inventory)
    junit = verify_junit(required, RUN / "full-final.xml")
    value = dict(status="PASS", full_execution="PASS", collect_execution="PASS", junit=junit,
                 g3_nodes=sum(n.startswith("tests/evals/g3/") for n in inventory["nodes"]),
                 plugin_count=len(full["loaded_plugins"]),
                 record_sha256={n: sha(RUN / n) for n in (
                     "inventory.json", "full-final.xml", "full-final-control.json", "collect-control.json")},
                 required_test_source_sha256=required["test_source_sha256"],
                 matrix_2574="not_evaluated; no new ranking experiment or research acceptance")
    return value


def cases(path):
    root = ET.parse(path).getroot()
    result = []
    for case in root.iter("testcase"):
        properties = {p.attrib["name"]: p.attrib["value"] for p in case.findall("properties/property")}
        node = properties.get("nodeid") or case.attrib["classname"].replace(".", "/") + ".py::" + case.attrib["name"]
        status = "SKIPPED" if case.find("skipped") is not None else "PASS"
        assert case.find("failure") is None and case.find("error") is None, node
        result.append(dict(node=node, status=status, seconds=float(case.attrib.get("time", 0))))
    return result


def upstream_review():
    area = ROOT / ".tmp/evals/g3/g4-pr4-final-rereview-20261103-001"
    value = read(area / "review-summary.json")
    assert value["status"] == "PASS_LOCAL_ENGINEERING_SCOPE" and not any(value["open_findings"].values())
    assert sha(area / "independent-shutdown-replay.json") == value["independent_replay_sha256"]
    assert sha(area / "actual-process-handoff-proof.json") == value["actual_process_proof_sha256"]
    return dict(status="PR4_HISTORICALLY_CLOSED_INDEPENDENT_AI_LOCAL_SCOPE", reviewed_head=value["head"],
                evidence={rel(area / n): pin(area / n) for n in (
                    "review-summary.json", "independent-shutdown-replay.json", "actual-process-handoff-proof.json")},
                distinction="Old PR4 fix report and entry freeze still say pending. This later independent evidence closes PR4 historically; PR5 integration and PR6 review remain pending.")


def gates():
    rows = [
        ("H00", "PENDING_REVIEW", ["audit/g4/pr2/UPSTREAM_REVIEW.json", "audit/g4/pr5/REVIEW_FIXES.md", "audit/g4/pr6/REVIEW_FIX_RESULTS.json"], "PR4 later independent PASS verified; PR5 fixes/PR6 total review and owner Beta decision pending."),
        ("H01", "PASS_OFFLINE_SAMPLE", ["audit/g4/pr6/samples/vite-8.3.4/PROVENANCE.json", "audit/g4/pr6/samples/vite-8.3.4/LICENSE.md", rel(RUN / "pilot-native/result.json")], "Local MIT documentation only; no new external fetch or live smoke; original publication date unknown."),
        ("H02", "PASS_SAFE_DEGRADATION", [rel(RUN / "g4-final.xml"), rel(RUN / "pilot-native/briefing.json")], "Real independent-support qualification unresolved; actual real result raw_news_only/hold; qualified real pipeline not evaluated."),
        ("H03", "PASS_ENGINEERING", [rel(RUN / "g4-final.xml"), rel(RUN / "browser-contracts-native/browser-results.json")], "Authored adversaries plus real safe rejection; no independent semantic-truth study."),
        ("H04", "PASS_ENGINEERING", ["audit/g4/pr6/ENTRY_FREEZE.json", rel(RUN / "full-final.xml"), rel(RUN / "browser-contracts-native/browser-results.json")], "B4/frozen policy unchanged; uncalibrated budget, greedy limitations and native history-scoring gap retained."),
        ("H05", "PASS_LOCAL_QA", [rel(RUN / "g4-final.xml"), rel(RUN / "restore-proof-final/result.json")], "Isolated SQLite backups/restores/migrations only; real user database and hardware power-cut not evaluated."),
        ("H06", "PASS_LOCAL_QA", [rel(RUN / "g4-final.xml"), rel(RUN / "browser-contracts-native/browser-results.json"), rel(RUN / "browser-pilot/result.json")], "Qualified exposure viewport path uses UI fixtures; real hold Archive has zero rendered and explicit metadata feedback."),
        ("H07", "PASS_LOCAL_QA", [rel(RUN / "g4-final.xml"), rel(RUN / "browser-pilot/result.json")], "Controlled faults and bounded QA entry delay; cooperative cancellation does not force-stop an uncooperative thread."),
        ("H08", "PASS_LOCAL_BOUNDARY", [rel(RUN / "g4-final.xml"), rel(RUN / "browser-pilot/result.json")], "Local single-user boundary; no multiuser authentication or cloud security claim."),
        ("H09", "PARTIAL", [rel(RUN / "browser-pilot/result.json"), rel(RUN / "browser-contracts-native/browser-results.json"), "docs/G4_G5_HANDOFF.md"], "1/3/7-day UI fixtures only; native feedback scoring, late Persona continuity and long-window generation remain unimplemented."),
        ("H10", "PASS", [rel(RUN / "full-final.xml"), rel(RUN / "control-verification.json"), rel(RUN / "browser-pilot/result.json"), "audit/g4/pr6/REVIEW_FIX_SOURCE_FREEZE.json"], "1145 original files preserved, one authorized StrictMode focus fix; G1/G2/G3 unchanged. Actual legacy workflow and recovery pass; lexical baseline is not LLM reasoning."),
        ("H11", "PASS_OFFLINE_QA", [rel(RUN / "browser-contracts-native/browser-results.json"), rel(RUN / "browser-pilot/result.json")], "Actual Windows Edge; no live-network smoke or human-utility validation."),
        ("H12", "PASS_WITH_OPEN_GATES", DOCS + ["audit/G4_RELEASE_MANIFEST.json"], "Failed QA iterations preserved; conditional/PARTIAL/not_evaluated retained; self hash excluded to avoid circularity."),
    ]
    return {key: dict(status=status, artifacts=paths, failure_or_limit=reason) for key, status, paths, reason in rows}


def toolchain():
    modules = Path(read(RUN / "browser-green/contracts.command.json")["argv"][-1])
    packages = {}
    for name in ("playwright", "playwright-core"):
        package = modules / name
        packages[name] = dict(version=read(package / "package.json")["version"],
                             files={p.relative_to(package).as_posix(): pin(p)
                                    for p in sorted(package.rglob("*")) if p.is_file()})
    edge = Path("C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe")
    assert edge.is_file()
    value = dict(node_version=subprocess.check_output(["node", "--version"], text=True).strip(),
                 node_executable=pin(Path(shutil.which("node"))), browser_executable=pin(edge),
                 browser_version=read(RUN / "browser-pilot/result.json")["browser_version"],
                 packages=packages, python_versions="audit/g4/pr6/ENTRY_FREEZE.json:python_distributions",
                 dependency_locks="Entry freeze pins pyproject.toml, frontend/package-lock.json and source/package manifests")
    write(RUN / "toolchain.json", value)


def main():
    from audit.g4.pr6.finalize_review import main as review_main
    return review_main()


if __name__ == "__main__":
    main()
