"""Run and verify actual regression commands and exact, additive JUnit inventory."""

import argparse
import os
import subprocess
import sys
from pathlib import Path

from evals.intelligence_g2.contracts import digest, json_bytes, read_json
from evals.intelligence_g2.pr6.junit_inventory import verify_junit

from .artifacts import command, fresh, release, seal, sealed, verify_command, write
from .contracts import ROOT, fail
from .junit_inventory import verify_inventory
from .pytest_runner import verify_execution


def command_plan(root):
    python = [sys.executable, "-B"]
    plugin = "evals.intelligence_g3.junit_inventory"
    runner = "evals.intelligence_g3.pytest_runner"
    plan = [("collect", [*python, "-m", runner, "--mode", "collect", "--inventory",
                          str(root / "node_inventory.json"), "--control-record",
                          str(root / "collect.control.json")], ROOT),
            ("inventory", [*python, "-m", plugin, "--inventory", str(root / "node_inventory.json")], ROOT),
            ("ruff", [*python, "-m", "ruff", "check", "backend", "tests", "evals"], ROOT)]
    for i, module in enumerate(("contracts", "ranking_schema", "revisit_cli", "budget_cli",
                                "pr5_contracts")):
        plan.append((f"schema-g3-{i}", [*python, "-m", "evals.intelligence_g3." + module,
                                        "--check-schemas"], ROOT))
    plan += [("g1-strict", [*python, "-m", "evals.intelligence_v1.validate", "--manifest",
              str(ROOT / "evals/intelligence_v1/manifests/dataset_manifest.json"), "--strict"], ROOT),
             ("seed", [*python, "evals/run_baseline.py", "--output", str(root / "seed.json")], ROOT)]
    for name in ("g3", "full"):
        argv = [*python, "-m", runner, "--mode", name, "--junit", str(root / (name + ".xml")),
                "--basetemp", str(root.parent / (root.name + "-pytest") / name),
                "--control-record", str(root / (name + ".control.json"))]
        plan.append((name, argv, ROOT))
    plan += [("junit", [*python, "-m", plugin, "--inventory", str(root / "node_inventory.json"),
                        "--junit", str(root / "full.xml")], ROOT),
             ("frontend", ["npm.cmd" if os.name == "nt" else "npm", "--offline", "run", "build",
                           "--", "--outDir", str(root / "frontend-dist")], ROOT / "frontend"),
             ("diff", ["git", "diff", "--check"], ROOT)]
    return plan


def frozen_compatibility():
    areas = ("evals/intelligence_v1", "evals/intelligence_g2", "tests/evals/g2",
             "backend", "frontend/src", "frontend/package.json", "frontend/package-lock.json",
             "requirements.lock", "pyproject.toml", "data/archive/articles.json", ".gitignore",
             "docs/plans/G1_IMPLEMENTATION_PLAN.md", "docs/plans/G1_AI_DEVELOPMENT_RULES.md",
             "docs/plans/G2_IMPLEMENTATION_PLAN.md", "docs/G1_ACCEPTANCE.md",
             "docs/G2_PUBLICATION.md", "docs/G2_G3_HANDOFF.md")
    result = subprocess.run(["git", "diff", "--exit-code", "HEAD", "--", *areas],
                            cwd=ROOT, capture_output=True)
    additions = subprocess.check_output(["git", "ls-files", "--others", "--exclude-standard", "-z",
                                        "--", *areas], cwd=ROOT)
    if result.returncode or additions:
        fail("G3_FROZEN_CHANGED", "legacy_runtime_dependencies_archive")
    return dict(status="PASS", anchor_commit=release()["anchor_commit"], areas=areas,
                historical_acceptance="preserved_not_relabelled_as_a_new_G1_G2_acceptance")


def verify_checks(root, pin):
    root = Path(root).absolute()
    manifest = sealed(root, pin, "checks")
    source = release()
    if (manifest["source_sha256"] != digest(source)
            or read_json((root / "source_release.json").read_bytes()) != source):
        fail("G3_SOURCE_MISMATCH", "checks")
    if read_json((root / "frozen_compatibility.json").read_bytes()) != read_json(
            json_bytes(frozen_compatibility())):
        fail("G3_FROZEN_CHANGED", "compatibility_artifact")
    for name, argv, cwd in command_plan(root):
        verify_command(root, name, argv, cwd=cwd)
    for mode in ("collect", "g3", "full"):
        verify_execution(read_json((root / (mode + ".control.json")).read_bytes()), mode=mode,
                         inventory=str(root / "node_inventory.json") if mode == "collect" else None,
                         junit=str(root / (mode + ".xml")) if mode != "collect" else None,
                         basetemp=str(root.parent / (root.name + "-pytest") / mode)
                         if mode != "collect" else None)
    required = verify_inventory(read_json((root / "node_inventory.json").read_bytes()))
    coverage = verify_junit(required, root / "full.xml")
    g3 = {**required, "nodes": [n for n in required["nodes"] if n.startswith("tests/evals/g3/")]}
    verify_junit(g3, root / "g3.xml")
    from .pr5_contracts import check_schemas

    if not check_schemas():
        fail("G3_SCHEMA_INVALID", "schema/v5")
    if read_json((root / "coverage.json").read_bytes()) != coverage:
        fail("G3_CHECK_EVIDENCE_MISMATCH", "junit_coverage")
    return manifest, coverage


def run_checks(out):
    source = release()
    root = fresh(out)
    write(root, "source_release.json", source)
    write(root, "frozen_compatibility.json", frozen_compatibility())
    # pytest creates its basetemp itself, but requires the parent to exist.
    (root.parent / (root.name + "-pytest")).mkdir(parents=True, exist_ok=False)
    for name, argv, cwd in command_plan(root):
        print("Running " + name, flush=True)
        command(root, name, argv, cwd=cwd)
        if name == "collect":
            verify_inventory(read_json((root / "node_inventory.json").read_bytes()))
    if release() != source:
        fail("G3_SOURCE_MISMATCH", "checks_after")
    required = verify_inventory(read_json((root / "node_inventory.json").read_bytes()))
    write(root, "coverage.json", verify_junit(required, root / "full.xml"))
    # pytest's temporary directories are deliberately outside the sealed evidence.
    # Keep their bytes available; seal explicit evidence rather than temp byproducts.
    from .pr5_contracts import check_schemas

    if not check_schemas():
        fail("G3_SCHEMA_INVALID", "schema/v5")
    pin = seal(root, "checks", source_sha256=digest(source))
    verify_checks(root, pin)
    print(pin, flush=True)
    return pin


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", required=True)
    args = p.parse_args(argv)
    run_checks(args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
