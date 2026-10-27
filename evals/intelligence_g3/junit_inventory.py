"""Additive PR1/PR2 inventories plus the exact frozen G2 projection."""

import argparse
from collections import Counter

from evals.intelligence_g2.contracts import read_json
from evals.intelligence_g2.pr6.junit_inventory import (
    pytest_collection_modifyitems as pytest_collection_modifyitems,
)
from evals.intelligence_g2.pr6.junit_inventory import (
    test_sources,
    verify_junit,
)
from evals.intelligence_g2.replay import safe_path
from evals.intelligence_v1.hashing import sha256_bytes

from .contracts import PACKAGE, ROOT, fail, json_bytes

LEGACY_PIN = "304164804aa1e55433ce12cd535de432c48d8102ef0fe82ad1ae5eb53b4c8b2e"
G3_REQUIRED_PIN = "023f3c5ac90515583589d132fb7fba847932bd860da6e0a547a678bd5477930e"
PR2_REQUIRED_PIN = "3c0acba58113a2de902a2dc4501658097f543d4883347f10d4d9fec2b2298722"
OUTPUT_BASE = ROOT / ".tmp/evals/g3"


def pytest_addoption(parser):
    parser.addoption("--g3-inventory", default=None)


def pytest_collection_finish(session):
    name = session.config.getoption("--g3-inventory")
    if name:
        path = safe_path(name, areas=(OUTPUT_BASE,))
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as stream:
            stream.write(json_bytes(dict(nodes=[i.nodeid for i in session.items],
                                         test_source_sha256=test_sources())))


def requirements():
    raw = (ROOT / "evals/intelligence_g2/manifests/pr6_required_tests.json").read_bytes()
    if sha256_bytes(raw) != LEGACY_PIN:
        fail("G3_TEST_INVENTORY_INVALID", "legacy_manifest_pin")
    legacy = read_json(raw)
    raw = (PACKAGE / "manifests/pr1_required_tests.json").read_bytes()
    if sha256_bytes(raw) != G3_REQUIRED_PIN:
        fail("G3_TEST_INVENTORY_INVALID", "g3_manifest_pin")
    current = read_json(raw)
    if current.get("revision") != "g3-pr1-required-tests-v1" or not current["nodes"]:
        fail("G3_TEST_INVENTORY_INVALID", "g3_revision")
    if (any(not n.startswith("tests/evals/g3/") for n in current["nodes"])
            or any(not n.startswith("tests/evals/g3/") for n in current["test_source_sha256"])):
        fail("G3_TEST_INVENTORY_INVALID", "g3_scope")
    raw = (PACKAGE / "manifests/pr2_required_tests.json").read_bytes()
    if sha256_bytes(raw) != PR2_REQUIRED_PIN:
        fail("G3_TEST_INVENTORY_INVALID", "pr2_manifest_pin")
    pr2 = read_json(raw)
    if (pr2.get("revision") != "g3-pr2-required-tests-v1" or not pr2["nodes"]
            or any(not n.startswith("tests/evals/g3/test_rankers.py::") for n in pr2["nodes"])
            or set(pr2["test_source_sha256"]) != {"tests/evals/g3/test_rankers.py",
                                                "tests/evals/g3/ranking_support.py"}
            or set(pr2["nodes"]) & set(current["nodes"])
            or set(pr2["test_source_sha256"]) & set(current["test_source_sha256"])):
        fail("G3_TEST_INVENTORY_INVALID", "pr2_scope")
    return {**legacy, "nodes": legacy["nodes"] + current["nodes"] + pr2["nodes"],
            "test_source_sha256": {**legacy["test_source_sha256"], **current["test_source_sha256"],
                                   **pr2["test_source_sha256"]}}


def verify_inventory(inventory):
    required = requirements()
    nodes = inventory["nodes"]
    if (len(nodes) != len(set(nodes)) or Counter(nodes) != Counter(required["nodes"])
            or required["test_source_sha256"] != test_sources()
            or inventory["test_source_sha256"] != required["test_source_sha256"]):
        fail("G3_TEST_INVENTORY_INVALID", "complete_nodes_and_sources")
    return required


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--inventory", required=True)
    parser.add_argument("--junit")
    args = parser.parse_args(argv)
    try:
        path = safe_path(args.inventory, areas=(OUTPUT_BASE,))
        required = verify_inventory(read_json(path.read_bytes()))
        result = (verify_junit(required, safe_path(args.junit, areas=(OUTPUT_BASE,)))
                  if args.junit else dict(nodes=len(required["nodes"])))
    except (ValueError, OSError, KeyError, TypeError) as error:
        print(json_bytes(dict(ok=False, code=getattr(error, "code", "G3_TEST_INVENTORY_INVALID"),
                              field=getattr(error, "field", "inventory"))).decode(), end="")
        return 1
    print(json_bytes(dict(ok=True, **result)).decode(), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
