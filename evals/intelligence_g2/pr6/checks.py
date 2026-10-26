"""Actual committed-source regressions. No install, live provider or production DB probes."""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone

from evals.intelligence_g2.contracts import read_json

from .contracts import (
    ChecksBundle,
    CommandRecord,
    FilePin,
    cli_entry,
    digest,
    fail,
    json_bytes,
    parse,
)
from .junit_inventory import verify_inventory, verify_junit
from .manifest import PACKAGE, ROOT, output_location, pinned, relative, sha256_bytes, source_release

NAMES = {
    "collect",
    "ruff",
    "g1-strict",
    "legacy-reproduce",
    "pytest-g2",
    "pytest-evals",
    "pytest-full",
    "seed",
    "frontend",
    "diff",
} | {f"schema-{i}" for i in range(7)}


def artifact(path, root):
    return FilePin(path=path.relative_to(root).as_posix(), sha256=sha256_bytes(path.read_bytes()))


def run_command(name, argv, root, *, cwd=ROOT, artifacts=()):
    start = datetime.now(timezone.utc).isoformat()
    log = root / (name + ".log")
    with log.open("xb") as stream:
        proc = subprocess.run(argv, cwd=cwd, stdout=stream, stderr=subprocess.STDOUT, timeout=3600)
    result = CommandRecord(
        name=name,
        argv=tuple(str(a) for a in argv),
        cwd=str(cwd),
        started_at=start,
        finished_at=datetime.now(timezone.utc).isoformat(),
        exit_code=proc.returncode,
        log=artifact(log, root),
        artifacts=tuple(artifact(root / p, root) for p in artifacts),
    )
    with (root / (name + ".command.json")).open("xb") as stream:
        stream.write(json_bytes(result))
    if proc.returncode:
        fail("G2_PR6_CHECK_FAILED", name)
    return result


def g1_compatibility(required, full_xml):
    import xml.etree.ElementTree as ET

    frozen = read_json((ROOT / "evals/intelligence_v1/manifests/required_tests.json").read_bytes())
    root = ET.parse(full_xml).getroot()
    actual = [
        t.get("classname") + "::" + t.get("name")
        for t in root.iter("testcase")
        if not t.get("classname", "").startswith("tests.evals.g2.")
    ]
    from collections import Counter

    sources = frozen["test_source_sha256"]
    if Counter(actual) != Counter(frozen["nodes"]) or any(
        sha256_bytes((ROOT / p).read_bytes()) != h for p, h in sources.items()
    ):
        fail("G2_PR6_G1_INCOMPATIBLE", "frozen_projection")
    return dict(
        status="PASS",
        current_compatible_nodes=len(actual),
        frozen_test_sources=len(sources),
        historical_acceptance="preserved_not_rerun_with_current_junit",
        migration="N/A",
        namespace="G1-T25",
        g2_T25="required",
    )


def verify_legacy_artifacts(root, legacy):
    for name, sha in legacy["artifact_sha256"].items():
        pinned(
            root / "legacy-g1" / relative(name.replace("\\", "/")), sha, areas=(root / "legacy-g1",)
        )
    return len(legacy["artifact_sha256"])


def verify_checks(path, pin):
    from pathlib import Path

    path = Path(path).absolute()
    root = path.parent
    value = parse(ChecksBundle, read_json(pinned(path, pin)))
    if (
        source_release(value.source_release.source_commit) != value.source_release
        or digest(value.source_release) != value.source_release_sha256
    ):
        fail("RUNTIME_CODE_MISMATCH", "checks_source")
    required = read_json(
        pinned(ROOT / relative(value.required_tests.path), value.required_tests.sha256)
    )
    inventory = read_json(
        pinned(root / relative(value.inventory.path), value.inventory.sha256, areas=(root,))
    )
    verify_inventory(required, inventory)
    if len(value.commands) != len(NAMES) or {c.name for c in value.commands} != NAMES:
        fail("G2_PR6_CHECK_FAILED", "command_set")
    expected = {p["name"]: p for p in command_plan(root)}
    for c in value.commands:
        spec = expected[c.name]
        if (
            c.argv != spec["argv"]
            or c.cwd != str(spec["cwd"])
            or {a.path for a in c.artifacts} != set(spec["artifacts"])
            or c.log.path != c.name + ".log"
        ):
            fail("G2_PR6_CHECK_FAILED", "command_binding")
        try:
            start, end = datetime.fromisoformat(c.started_at), datetime.fromisoformat(c.finished_at)
            if start.tzinfo is None or end.tzinfo is None or end < start:
                raise ValueError()
        except ValueError:
            fail("G2_PR6_CHECK_FAILED", "command_time")
        if json_bytes(c) != pinned(
            root / (c.name + ".command.json"), sha256_bytes(json_bytes(c)), areas=(root,)
        ):
            fail("G2_PR6_CHECK_FAILED", "command_record")
        if c.exit_code or not c.argv:
            fail("G2_PR6_CHECK_FAILED", c.name)
        for a in (c.log, *c.artifacts):
            pinned(root / relative(a.path), a.sha256, areas=(root,))
    coverage = {}
    for name, e in (
        ("full", value.full_junit),
        ("g2", value.g2_junit),
        ("evals", value.evals_junit),
    ):
        pinned(root / relative(e.path), e.sha256, areas=(root,))
        coverage[name] = verify_junit(required, root / e.path, scope=name)
    if value.g1_compatibility != g1_compatibility(required, root / value.full_junit.path):
        fail("G2_PR6_G1_INCOMPATIBLE", "compatibility_report")
    legacy = read_json((root / "legacy-g1/reproduction.json").read_bytes())
    if (
        legacy["prediction_runs"],
        legacy["evaluation_runs"],
        legacy["all_deterministic_equal"],
    ) != (200, 400, True):
        fail("G2_PR6_G1_INCOMPATIBLE", "reproduction")
    verify_legacy_artifacts(root, legacy)
    from evals.intelligence_g2.contracts import G1_PIN
    from evals.intelligence_v1.acceptance import verify_matrix
    from evals.intelligence_v1.loader import load_bundle

    dataset = load_bundle(
        ROOT / "evals/intelligence_v1/manifests/dataset_manifest.json", manifest_sha256=G1_PIN
    )
    verify_matrix(
        read_json((root / "legacy-g1/summary/comparison.json").read_bytes()),
        dataset,
        root / "legacy-g1/primary",
    )
    for c in legacy["commands"]:
        pinned(c["log"], c["log_sha256"], areas=(root / "legacy-g1",))
        if c["exit_code"]:
            fail("G2_PR6_CHECK_FAILED", "legacy_command")
    return value, coverage


def command_plan(root):
    python = [sys.executable, "-B"]
    plan = []

    def spec(name, argv, _root, *, cwd=ROOT, artifacts=()):
        return dict(name=name, argv=tuple(str(a) for a in argv), cwd=cwd, artifacts=artifacts)

    plugin = "evals.intelligence_g2.pr6.junit_inventory"
    plan.append(
        spec(
            "collect",
            [
                *python,
                "-m",
                "pytest",
                "--collect-only",
                "-q",
                "-p",
                "no:cacheprovider",
                "-p",
                plugin,
                "--pr6-inventory",
                str(root / "node_inventory.json"),
            ],
            root,
            artifacts=("node_inventory.json",),
        )
    )
    plan.append(spec("ruff", [*python, "-m", "ruff", "check", "backend", "tests", "evals"], root))
    for i, module in enumerate(
        ["evals.intelligence_v1.contracts", "evals.intelligence_g2.contracts"]
        + [f"evals.intelligence_g2.pr{v}.contracts" for v in range(2, 7)]
    ):
        plan.append(spec("schema-" + str(i), [*python, "-m", module, "--check-schemas"], root))
    g1 = ROOT / "evals/intelligence_v1/manifests/dataset_manifest.json"
    from evals.intelligence_g2.contracts import G1_PIN

    plan.append(
        spec(
            "g1-strict",
            [*python, "-m", "evals.intelligence_v1.validate", "--manifest", str(g1), "--strict"],
            root,
        )
    )
    for name, scope in (
        ("pytest-g2", "tests/evals/g2"),
        ("pytest-evals", "tests/evals"),
        ("pytest-full", None),
    ):
        xml = {"pytest-g2": "g2.xml", "pytest-evals": "evals.xml", "pytest-full": "full.xml"}[name]
        argv = [
            *python,
            "-m",
            "pytest",
            "-q",
            "-p",
            "no:cacheprovider",
            "-p",
            plugin,
            "-o",
            "faulthandler_timeout=120",
            "--basetemp=" + str(root / (name + "-temp")),
            "--junitxml=" + str(root / xml),
        ]
        if scope:
            argv.append(scope)
        plan.append(spec(name, argv, root, artifacts=(xml,)))
    plan.append(
        spec(
            "legacy-reproduce",
            [
                *python,
                "-m",
                "evals.intelligence_v1.reproduce",
                "--manifest",
                str(g1),
                "--manifest-sha256",
                G1_PIN,
                "--workers",
                "1",
                "--out",
                str(root / "legacy-g1"),
            ],
            root,
            artifacts=("legacy-g1/reproduction.json",),
        )
    )
    plan.append(
        spec(
            "seed",
            [*python, "evals/run_baseline.py", "--output", str(root / "seed.json")],
            root,
            artifacts=("seed.json",),
        )
    )
    plan.append(
        spec(
            "frontend",
            ["npm.cmd" if os.name == "nt" else "npm", "--offline", "run", "build"],
            root,
            cwd=ROOT / "frontend",
        )
    )
    plan.append(spec("diff", ["git", "diff", "--check"], root))
    return plan


def run_checks(commit, out):
    release = source_release(commit)
    root = output_location(out)
    root.mkdir(parents=True)
    commands = []
    req = PACKAGE / "manifests/pr6_required_tests.json"
    required = read_json(req.read_bytes())
    for spec in command_plan(root):
        commands.append(run_command(root=root, **spec))
        if spec["name"] == "collect":
            verify_inventory(required, read_json((root / "node_inventory.json").read_bytes()))
    if source_release(commit) != release:
        fail("RUNTIME_CODE_MISMATCH", "checks_after")
    value = ChecksBundle(
        source_release=release,
        source_release_sha256=digest(release),
        required_tests=FilePin(
            path=req.relative_to(ROOT).as_posix(), sha256=sha256_bytes(req.read_bytes())
        ),
        commands=tuple(commands),
        inventory=artifact(root / "node_inventory.json", root),
        full_junit=artifact(root / "full.xml", root),
        g2_junit=artifact(root / "g2.xml", root),
        evals_junit=artifact(root / "evals.xml", root),
        g1_compatibility=g1_compatibility(required, root / "full.xml"),
        source_unchanged=True,
    )
    with (root / "checks.json").open("xb") as stream:
        stream.write(json_bytes(value))
    _, coverage = verify_checks(root / "checks.json", sha256_bytes(json_bytes(value)))
    with (root / "requirements_coverage.json").open("xb") as stream:
        stream.write(json_bytes(coverage))
    return dict(ok=True, checks_sha256=sha256_bytes(json_bytes(value)))


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--source-commit", required=True)
    p.add_argument("--out", required=True)
    a = p.parse_args(argv)
    print(json.dumps(run_checks(a.source_commit, a.out)))


if __name__ == "__main__":
    raise SystemExit(cli_entry(main))
