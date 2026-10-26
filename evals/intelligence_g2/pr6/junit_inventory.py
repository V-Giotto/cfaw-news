"""Pytest collection metadata and exact JUnit verification, without renaming tests."""

import json
import re
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

from evals.intelligence_g2.contracts import ROOT, json_bytes, read_json
from evals.intelligence_g2.replay import OUTPUT_BASE, safe_path
from evals.intelligence_v1.hashing import sha256_bytes

from .contracts import fail


def test_sources():
    return {
        p.relative_to(ROOT).as_posix(): sha256_bytes(p.read_bytes())
        for p in sorted((ROOT / "tests").rglob("*.py"))
        if "__pycache__" not in p.parts
    }


def pytest_addoption(parser):
    parser.addoption("--pr6-inventory", default=None)


def pytest_collection_modifyitems(items):
    for item in items:
        item.user_properties.append(("pr6_nodeid", item.nodeid))


def pytest_collection_finish(session):
    name = session.config.getoption("--pr6-inventory")
    if name:
        path = safe_path(name, areas=(OUTPUT_BASE,))
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as stream:
            stream.write(
                json_bytes(
                    dict(nodes=[i.nodeid for i in session.items], test_source_sha256=test_sources())
                )
            )


def requirements(inventory):
    nodes = inventory["nodes"]
    mapping = {f"G2-T{i:02}": [] for i in range(1, 47)}
    auxiliary = []
    for node in nodes:
        if not node.startswith("tests/evals/g2/"):
            auxiliary.append(node)
            continue
        ids = {int(n) for n in re.findall(r"(?:G2_)?T(\d{2})", node) if 1 <= int(n) <= 46}
        if "test_G2_T01_T10_all_35" in node:
            ids.update(range(1, 11))
        if "/pr5/test_review_regressions.py" in node:
            ids.add(42)
        if "/pr4/test_review_credentials.py" in node:
            ids.update((33, 41))
        if (
            "/pr3/test_lifecycle_target_scope.py" in node
            or "/pr3/test_review_regressions.py" in node
        ):
            ids.add(24)
        if "/pr2/" in node and "test_review_" in node:
            ids.add(15 if "identity.py" in node else 17 if "replay.py" in node else 13)
        if "/test_export_reliability.py" in node:
            ids.update((10, 18, 36, 45))
        if not ids:
            auxiliary.append(node)
        for i in sorted(ids):
            mapping[f"G2-T{i:02}"].append(node)
    skip = []
    for n in nodes:
        if (
            n
            == "tests/evals/test_provenance_and_rights.py::test_symlink_outside_bundle_rejected_if_supported"
        ):
            skip.append(dict(node=n, platform="win32", reason="symlink creation unavailable: 1314"))
        if (
            "test_export_reliability.py::test_native_handle_without_delete_sharing_recovers_after_release["
            in n
        ):
            skip.append(
                dict(node=n, platform="linux", reason="native Windows directory sharing semantics")
            )
    result = dict(
        revision="g2-pr6-required-tests-v1",
        nodes=nodes,
        requirements=mapping,
        auxiliary_nodes=auxiliary,
        test_source_sha256=inventory["test_source_sha256"],
        skip_exemptions=skip,
        h_mapping={
            "H01": [1, 2, 3, 5, 9, 10, 17, 26, 43, 44],
            "H02": list(range(11, 19)),
            "H03": [7, 19, 25, 26, 27, 33, 37, 43],
            "H04": [19, 20, 21, 22, 23, 24, 25, 33, 34, 38, 39, 40],
            "H05": [8, 20, 21, 22, 23, 24, 27, 28, 29, 30, 31, 32, 46],
            "H06": [4, 15, 16, 18, 36, 45],
            "H07": [],
            "H08": [],
            "H09": [9, 10, 41, 44],
            "H10": [18, 25, 38, 42, 45, 46],
        },
        not_applicable={"G1-T25": "No production migration"},
    )
    auxiliary_h = {name: [] for name in result["h_mapping"]}
    for node in auxiliary:
        auxiliary_h["H07"].append(node)
        if "/pr6/" not in node:
            continue
        auxiliary_h["H06"].append(node)
        if any(
            x in node
            for x in (
                "test_boundaries", "test_manifest", "test_matrix", "test_path_compatibility", "test_junit"
            )
        ):
            auxiliary_h["H01"].append(node)
            auxiliary_h["H09"].append(node)
        if any(x in node for x in ("test_contracts", "test_evaluation")):
            auxiliary_h["H08"].append(node)
            auxiliary_h["H10"].append(node)
        if "test_matrix" in node or "test_evaluation" in node:
            auxiliary_h["H02"].append(node)
        if "test_matrix" in node:
            for name in ("H03", "H04", "H05"):
                auxiliary_h[name].append(node)
    result["auxiliary_h_mapping"] = auxiliary_h
    result["h_nodes"] = {
        name: sorted(set(auxiliary_h[name]) | {n for i in ids for n in mapping[f"G2-T{i:02}"]})
        for name, ids in result["h_mapping"].items()
    }
    result["h_nodes"]["H07"] = list(nodes)
    return result


def verify_inventory(required, inventory):
    ids = {f"G2-T{i:02}" for i in range(1, 47)}
    nodes = required["nodes"]
    if required != requirements(inventory):
        fail("G2_PR6_TEST_INVENTORY_INVALID", "mapping_or_exemption")
    if (
        required.get("revision") != "g2-pr6-required-tests-v1"
        or len(nodes) != len(set(nodes))
        or Counter(nodes) != Counter(inventory["nodes"])
        or set(required["requirements"]) != ids
        or any(not v or not set(v) <= set(nodes) for v in required["requirements"].values())
        or required["test_source_sha256"] != test_sources()
        or inventory["test_source_sha256"] != test_sources()
    ):
        fail("G2_PR6_TEST_INVENTORY_INVALID", "required_tests")


def verify_junit(required, path, *, scope="full", platform=None):
    platform = platform or sys.platform
    try:
        root = ET.fromstring(Path(path).read_bytes())
    except ET.ParseError:
        fail("G2_PR6_JUNIT_INVALID", "xml")
    cases = list(root.iter("testcase"))
    nodes = []
    expected = [
        n
        for n in required["nodes"]
        if scope == "full" or n.startswith("tests/evals/g2/" if scope == "g2" else "tests/evals/")
    ]
    for case in cases:
        values = [
            p.get("value")
            for p in case.findall("properties/property")
            if p.get("name") == "pr6_nodeid"
        ]
        if len(values) != 1 or values[0] is None:
            fail("G2_PR6_JUNIT_INVALID", "node_property")
        node = values[0]
        nodes.append(node)
        if case.find("failure") is not None or case.find("error") is not None:
            fail("G2_PR6_REQUIRED_TEST_FAILED", "node_sha256:" + sha256_bytes(node.encode("utf-8")))
        skipped = case.find("skipped")
        if skipped is not None and not any(
            e == dict(node=node, platform=platform, reason=skipped.get("message"))
            for e in required["skip_exemptions"]
        ):
            fail("G2_PR6_UNEXEMPT_SKIP", "node_sha256:" + sha256_bytes(node.encode("utf-8")))
    if Counter(nodes) != Counter(expected):
        fail("G2_PR6_JUNIT_INVALID", "complete_node_set")
    if any(int(s.get("failures", 0)) or int(s.get("errors", 0)) for s in root.iter("testsuite")):
        fail("G2_PR6_REQUIRED_TEST_FAILED", "suite")
    return dict(
        nodes=len(nodes),
        skipped=sum(c.find("skipped") is not None for c in cases),
        requirements={k: len(set(v) & set(nodes)) for k, v in required["requirements"].items()},
        gates={k: len(set(v) & set(nodes)) for k, v in required.get("h_nodes", {}).items()},
    )


def main(argv=None):
    import argparse

    from .contracts import cli_entry

    parser = argparse.ArgumentParser()
    parser.add_argument("--inventory", required=True)
    parser.add_argument("--junit")
    args = parser.parse_args(argv)

    def check():
        inventory = read_json(safe_path(args.inventory, areas=(OUTPUT_BASE,)).read_bytes())
        required = read_json(
            (ROOT / "evals/intelligence_g2/manifests/pr6_required_tests.json").read_bytes()
        )
        verify_inventory(required, inventory)
        result = (
            verify_junit(required, args.junit)
            if args.junit
            else dict(nodes=len(inventory["nodes"]))
        )
        print(json.dumps(result))

    return cli_entry(check)


if __name__ == "__main__":
    raise SystemExit(main())
