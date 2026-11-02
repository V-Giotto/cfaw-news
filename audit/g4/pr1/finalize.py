"""Verify actual PR1 evidence and write its baseline; never run or bless missing tests."""

import hashlib
import json
import platform
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from evals.intelligence_g2.contracts import data, digest, json_bytes
from evals.intelligence_g3.fact_signature import policy, policy_sha256
from evals.intelligence_g3.pytest_runner import verify_execution
from evals.intelligence_g4.contracts import RuntimeBriefing, parse
from evals.intelligence_g4.schema import check_schemas

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / ".tmp/evals/g3/g4-pr1-20261102-001"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_bytes())


def suite(path):
    cases = list(ET.parse(path).iter("testcase"))
    return dict(nodes=len(cases), passed=sum(not any(c.find(t) is not None for t in
        ("failure", "error", "skipped")) for c in cases),
        failures=sum(c.find("failure") is not None for c in cases),
        errors=sum(c.find("error") is not None for c in cases),
        skipped=sum(c.find("skipped") is not None for c in cases))


def main():
    entry = read(BASE / "entry.json")
    changed = [p for p, pin in entry["protected_files"].items()
               if not (ROOT / p).is_file() or sha(ROOT / p) != pin]
    if changed:
        raise ValueError("protected files changed: " + repr(changed))
    if subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip() != entry["head"]:
        raise ValueError("HEAD changed")
    commands = {p.name.removesuffix(".command.json"): read(p)
                for p in sorted(BASE.glob("*.command.json"))}
    for record in commands.values():
        if sha(ROOT / record["log"]) != record["log_sha256"]:
            raise ValueError("command log hash mismatch")
    required = ("focused-release", "full-loopback", "collect", "inventory", "junit",
                "g4-collect-release", "schema-release", "ruff-release", "baseline",
                "frontend", "diff-check")
    if any(name not in commands or commands[name]["exit_code"] != 0 for name in required):
        raise ValueError("missing or nonzero final verification command")
    full = suite(BASE / "full-loopback.xml")
    focused = suite(BASE / "focused-release.xml")
    if full != dict(nodes=1754, passed=1753, failures=0, errors=0, skipped=1):
        raise ValueError("unexpected legacy test result; inspect instead of changing thresholds")
    manifest_path = ROOT / "evals/intelligence_g4/manifests/pr1_required_tests.json"
    new = read(manifest_path)
    collected = read(BASE / "g4_inventory_release.json")
    if (sorted(collected["nodes"]) != new["nodes"] or len(new["nodes"]) != focused["nodes"]
            or focused["failures"] or focused["errors"] or focused["skipped"]
            or any(sha(ROOT / p) != pin for p, pin in new["test_source_sha256"].items())):
        raise ValueError("G4 required nodes, source or actual results mismatch")
    for mode, name in (("collect", "collect"), ("full", "full-loopback")):
        kwargs = (dict(inventory=str(BASE / "node_inventory.json")) if mode == "collect" else
                  dict(junit=str(BASE / "full-loopback.xml"), basetemp=str(BASE / "full-loopback-temp")))
        verify_execution(read(BASE / (name + ".control.json")), mode=mode, **kwargs)
    if not check_schemas():
        raise ValueError("G4 schemas changed")
    probes = []
    for case in read(BASE / "inputs/index.json"):
        name = "probe-" + case["name"] + "-release"
        record = commands[name]
        if record["exit_code"] != case["expected_exit"] or sha(ROOT / case["path"]) != case["input_pin"]:
            raise ValueError("probe command/input mismatch")
        output = BASE / name
        row = dict(name=case["name"], input_pin=case["input_pin"],
                   exit_code=record["exit_code"], log=record["log"])
        if record["exit_code"] == 0:
            release = read(output / "manifest.json")
            if (release["input_pin"] != case["input_pin"] or any(
                    sha(output / p) != pin for p, pin in release["files"].items())):
                raise ValueError("output manifest mismatch")
            result = parse(RuntimeBriefing, read(output / "result.json"))
            if result.status.publishable or result.plan is not None:
                raise ValueError("unexpected publication")
            row.update(output_pin=sha(output / "manifest.json"),
                       config_pin=sha(output / "config.json"), status=data(result.status))
        elif output.exists():
            raise ValueError("invalid probe unexpectedly signed output")
        probes.append(row)
    source_files = {p.relative_to(ROOT).as_posix(): sha(p) for area in (
        ROOT / "evals/intelligence_g4", ROOT / "audit/g4/pr1")
        for p in sorted(area.rglob("*")) if p.is_file() and "__pycache__" not in p.parts
        and p.suffix in {".py", ".json"}}
    # Avoid self-reference if a later verification reruns this builder.
    source_files.pop("audit/g4/pr1/RELEASE_MANIFEST.json", None)
    documents = {name: sha(ROOT / name) for name in (
        "audit/G4_ENTRY_REUSE_AUDIT.md", "docs/adr/G4_RUNTIME_LOCAL_V1.md",
        "evals/intelligence_g4/README.md")}
    value = dict(revision="g4-pr1-baseline-v1", client_date="2026-11-02", timezone="Asia/Shanghai",
        status="PASS", scope="PR1_contract_feasibility_only_pending_independent_review",
        entry=dict(head=entry["head"], branch=entry["branch"], initial_status=entry["status"],
            authorization=entry["authorization"],
            plan_requested_path_exists=False, plan_actual_path=entry["plan_actual_path"],
            g3_fact_technical_review="prior_chat_audit_plus_current_unchanged_source_regression",
            g3_final_owner_acceptance="not_reissued_or_silently_changed",
            downstream_implementation_authorized=False),
        runtime=dict(python=platform.python_version(), platform=sys.platform),
        results=dict(g4_focused=focused, legacy_full=full, legacy_inventory="PASS",
            schemas=dict(status="PASS", files=len(list((ROOT / "evals/intelligence_g4/schema/v1").glob("*.json")))),
            ruff="PASS", lexical_baseline="PASS", frontend_offline_build="PASS",
            registered_control_records="PASS", expected_negative_probes="PASS",
            old_full_sandbox=dict(status="INTERRUPTED_SOCKETPAIR_BLOCK",
                                 exit_code=commands["full"]["exit_code"])),
        protected=dict(file_count=len(entry["protected_files"]), unchanged=True,
            files=entry["protected_files"], tree_sha256=digest(entry["protected_files"])),
        source=dict(files=source_files, tree_sha256=digest(source_files), documents=documents),
        policy=dict(fact_signature=policy(), fact_signature_policy_sha256=policy_sha256(),
                    g4_required_tests_sha256=sha(manifest_path)),
        probes=probes, commands=commands,
        unverified=dict(g3_runtime_adapter="BLOCKED_UNREGISTERED",
            cross_request_identity="NOT_IMPLEMENTED", production_dependency_packaging="NOT_IMPLEMENTED",
            real_rss_capture="NOT_EVALUATED", database_migration="NOT_IMPLEMENTED",
            real_user_database="NOT_ACCESSED", api_frontend_integration="NOT_IMPLEMENTED",
            browser_e2e="NOT_EVALUATED", remote_ci="NOT_EVALUATED",
            independent_research="NOT_EVALUATED"),
        effects=dict(external_model_calls=0, paid_api_calls=0, external_news_collection=0,
            production_database_writes=0, git_writes=0, frontend_source_changes=0,
            dev_diaries_read_or_uploaded=False),
        historical_evidence="Prior chat and G3 old reports are context only, never current command PASS",
        builder_argv=[sys.executable, "-B", "-m", "audit.g4.pr1.finalize"])
    target = ROOT / "audit/G4_BASELINE.json"
    target.write_bytes(json_bytes(value))
    print(json.dumps(dict(status=value["status"], focused=focused, legacy_full=full,
                         source_pin=value["source"]["tree_sha256"], baseline_pin=sha(target))))


if __name__ == "__main__":
    main()
