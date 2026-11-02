"""Verify this review-fix run; original PR1 receipts remain immutable historical evidence."""

import subprocess

from evals.intelligence_g2.contracts import digest, json_bytes
from evals.intelligence_g2.pr6.junit_inventory import verify_junit
from evals.intelligence_g3.junit_inventory import verify_inventory
from evals.intelligence_g3.pytest_runner import verify_execution
from evals.intelligence_g4.contracts import RuntimeBriefing, parse
from evals.intelligence_g4.schema import check_schemas

from .finalize import ROOT, read, sha, suite

BASE = ROOT / ".tmp/evals/g3/g4-pr1-review-fix-20261102-001"


def main():
    entry = read(BASE / "entry.json")
    legacy = read(ROOT / ".tmp/evals/g3/g4-pr1-20261102-001/entry.json")
    for name, pin in legacy["protected_files"].items():
        if sha(ROOT / name) != pin:
            raise ValueError("legacy or original plan changed: " + name)
    allowed = {"evals/intelligence_g4/contracts.py", "evals/intelligence_g4/slice.py",
        "evals/intelligence_g4/schema.py", "evals/intelligence_g4/README.md",
        "docs/adr/G4_RUNTIME_LOCAL_V1.md", "audit/G4_ENTRY_REUSE_AUDIT.md",
        "audit/g4/pr1/IMPLEMENTATION_REPORT.md"}
    changed = [n for n, pin in entry["files"].items() if sha(ROOT / n) != pin]
    if set(changed) - allowed:
        raise ValueError("unexpected preexisting file change")
    old_review = ROOT / ".tmp/evals/g3/g4-pr1-review-20261102-001"
    if any(sha(old_review / n) != pin for n, pin in entry["review_evidence_pins"].items()):
        raise ValueError("original review evidence changed")
    commands = {p.name.removesuffix(".command.json"): read(p) for p in BASE.glob("*.command.json")}
    if any(sha(ROOT / r["log"]) != r["log_sha256"] for r in commands.values()):
        raise ValueError("actual command log changed")
    expected_codes = {name: 0 for name in ("green-tests-02", "g3", "full", "schema-check", "ruff-final",
        "g4-collect", "collect", "inventory", "baseline", "frontend", "diff-check",
        "green-coverage-minute", "green-namespace-70", "green-namespace-60", "compatibility")}
    expected_codes.update({"green-rollback": 1, "green-fork": 1, "red-tests": 1,
                          "red-rollback": 0, "red-fork": 0, "red-coverage-minute": 0})
    if any(n not in commands or commands[n]["exit_code"] != code for n, code in expected_codes.items()):
        raise ValueError("missing command or unexpected exit code")
    parent_path = ROOT / "evals/intelligence_g4/manifests/pr1_required_tests.json"
    extra_path = ROOT / "evals/intelligence_g4/manifests/pr1_review_required_tests.json"
    parent, extra = read(parent_path), read(extra_path)
    if extra["parent_manifest_sha256"] != sha(parent_path):
        raise ValueError("old required-test pin changed")
    expected_nodes = sorted(parent["nodes"] + extra["nodes"])
    if sorted(read(BASE / "g4_inventory.json")["nodes"]) != expected_nodes:
        raise ValueError("G4 collection differs from pinned test union")
    for n, pin in {**parent["test_source_sha256"], **extra["test_source_sha256"]}.items():
        if sha(ROOT / n) != pin:
            raise ValueError("test source changed after collection")
    focused = suite(BASE / "green-02.xml")
    if focused["passed"] != len(expected_nodes) or focused["skipped"] or focused["errors"] or focused["failures"]:
        raise ValueError("incomplete current G4 JUnit")
    required = verify_inventory(read(BASE / "node_inventory.json"))
    full_coverage = verify_junit(required, BASE / "full.xml")
    for mode in ("collect", "g3", "full"):
        kwargs = (dict(inventory=str(BASE / "node_inventory.json")) if mode == "collect" else
            dict(junit=str(BASE / (mode + ".xml")), basetemp=str(BASE / "g3-temp") if mode == "g3"
                 else str(ROOT / ".tmp/evals/g3/g4-fix-full-temp-20261102-001")))
        verify_execution(read(BASE / (mode + ".control.json")), mode=mode, **kwargs)
    if not check_schemas():
        raise ValueError("current v2 schema mismatch")
    probes = {}
    for name in ("green-coverage-minute", "compatible-out", "namespace-70-out", "namespace-60-out"):
        out = BASE / name
        manifest = read(out / "manifest.json")
        if (set(p.name for p in out.iterdir()) != set(manifest["files"]) | {"manifest.json"}
                or any(sha(out / n) != pin for n, pin in manifest["files"].items())):
            raise ValueError("output artifact set or bytes mismatch")
        value = parse(RuntimeBriefing, read(out / "result.json"))
        probes[name] = dict(manifest_pin=sha(out / "manifest.json"), input_pin=value.input_sha256,
                           config_pin=sha(out / "config.json"), result_revision=value.schema_revision)
    minute = read(BASE / "green-coverage-minute/result.json")["native_steps"][0]
    if (not minute["coverage"]["has_gap"] or minute["coverage"]["sources"][0]["segments"][0]["status"]
            != "unknown" or minute["evidence"]["validation"]["coverage_gaps"] != []):
        raise ValueError("requested-window diagnostic missing or frozen G2 changed")
    for name in ("rollback", "fork"):
        if (BASE / ("green-" + name)).exists():
            raise ValueError("invalid chain signed output")
    namespace = read(BASE / "namespace-current.json")
    if not all(namespace[k] for k in ("input_pins_differ", "config_pins_differ", "identity_projection_equal")):
        raise ValueError("namespace comparison mismatch")
    compatibility = read(BASE / "native-compatibility.json")
    if not compatibility["input_pin_unchanged"] or not all(compatibility["unchanged_native_outputs"].values()):
        raise ValueError("native semantics changed")
    files = {p.relative_to(ROOT).as_posix(): sha(p) for p in (ROOT / "evals/intelligence_g4").rglob("*")
             if p.is_file() and "__pycache__" not in p.parts and p.suffix in {".py", ".json"}}
    for p in (ROOT / "audit/g4/pr1").glob("*.py"):
        files[p.relative_to(ROOT).as_posix()] = sha(p)
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    if head != entry["head"]:
        raise ValueError("HEAD changed")
    value = dict(revision="g4-pr1-review-fix-baseline-v1", client_date="2026-11-02", status="PASS",
        scope="three_review_findings_only_pending_independent_re_review", head=head,
        findings={"document_chain_P1": "FIXED", "coverage_interval_P2": "FIXED",
                  "namespace_documentation_P2": "CORRECTED"},
        results=dict(g4=focused, g3=suite(BASE / "g3.xml"), full=suite(BASE / "full.xml"),
            full_required_junit=full_coverage, ruff="PASS", schema_v2="PASS",
            lexical_baseline="PASS", offline_frontend_build="PASS"),
        preservation=dict(legacy_files=len(legacy["protected_files"]), unchanged=True,
            changed_preexisting_files=changed, original_v1_schemas_and_test_pins_unchanged=True,
            old_receipts="preserved_historical_not_current", review_evidence_unchanged=True),
        source=dict(files=files, tree_sha256=digest(files)), commands=commands, probes=probes,
        namespace_comparison=namespace, native_compatibility=compatibility,
        limits=dict(runtime_adapter="BLOCKED_UNREGISTERED", publishable=False, no_git_writes=True,
            no_production_db_writes=True, no_network_model_calls=True, independent_research=False))
    target = ROOT / "audit/g4/pr1/REVIEW_FIX_BASELINE.json"
    target.write_bytes(json_bytes(value))
    print(json_bytes(dict(status=value["status"], source_pin=value["source"]["tree_sha256"],
                          baseline_pin=sha(target), results=value["results"])).decode(), end="")


if __name__ == "__main__":
    main()
