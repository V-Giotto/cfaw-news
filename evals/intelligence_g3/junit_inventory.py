"""Additive PR1/PR2/PR3/PR4 inventories plus the exact frozen G2 projection."""

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
PR3_REQUIRED_PIN = "25685047495403513b51a94abfc38d11d90727f5dbcd96bf8d4f6fa36cfbfecb"
PR4_REQUIRED_PIN = "3d269a4361dc67ce08db7d9ab1bb5f541a4f26971eb72cc0b88240ef25d61b8b"
PR4_DIAGNOSTICS_REQUIRED_PIN = "a6d5bde7ee1547afdf7b3565280e2df88637e6eb246e6f0cd1d0539dc6c4f6d7"
PR5_REQUIRED_PIN = "7e851dd8bb3bac76cdcfc9f77ab7462d0359386f16f6bbfa32bb91e098e2d34d"
PR5_WIRE_REQUIRED_PIN = "a6079a8c831531644e64ca302d6d36df8aaf271f876addae4e32e2456a2988a8"
PR5_REVIEW_REQUIRED_PIN = "0ef1a7ee654aae1b36e8affec43a598c3bd83bc457ea327b871c44c2aeddf2d2"
FACT_REQUIRED_PIN = "3e9bf5cc3e568d06da92c71fcca9f8a051dc9726b5e9d6cc8167efee14050d91"
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
    raw = (PACKAGE / "manifests/pr3_required_tests.json").read_bytes()
    if sha256_bytes(raw) != PR3_REQUIRED_PIN:
        fail("G3_TEST_INVENTORY_INVALID", "pr3_manifest_pin")
    pr3 = read_json(raw)
    pr3_sources = {"tests/evals/g3/history_support.py", "tests/evals/g3/test_history.py",
                   "tests/evals/g3/test_revisit.py"}
    if (pr3.get("revision") != "g3-pr3-required-tests-v1" or not pr3["nodes"]
            or any(not n.startswith(("tests/evals/g3/test_history.py::",
                                     "tests/evals/g3/test_revisit.py::")) for n in pr3["nodes"])
            or set(pr3["test_source_sha256"]) != pr3_sources
            or set(pr3["nodes"]) & set(legacy["nodes"] + current["nodes"] + pr2["nodes"])
            or pr3_sources & set({**legacy["test_source_sha256"],
                                  **current["test_source_sha256"], **pr2["test_source_sha256"]})):
        fail("G3_TEST_INVENTORY_INVALID", "pr3_scope")
    previous_nodes = legacy["nodes"] + current["nodes"] + pr2["nodes"] + pr3["nodes"]
    previous_sources = {**legacy["test_source_sha256"], **current["test_source_sha256"],
                        **pr2["test_source_sha256"], **pr3["test_source_sha256"]}
    raw = (PACKAGE / "manifests/pr4_required_tests.json").read_bytes()
    if sha256_bytes(raw) != PR4_REQUIRED_PIN:
        fail("G3_TEST_INVENTORY_INVALID", "pr4_manifest_pin")
    pr4 = read_json(raw)
    pr4_sources = {"tests/evals/g3/test_budget.py", "tests/evals/g3/budget_support.py"}
    if (pr4.get("revision") != "g3-pr4-required-tests-v1" or not pr4["nodes"]
            or any(not n.startswith("tests/evals/g3/test_budget.py::") for n in pr4["nodes"])
            or set(pr4["test_source_sha256"]) != pr4_sources
            or set(pr4["nodes"]) & set(previous_nodes) or pr4_sources & set(previous_sources)):
        fail("G3_TEST_INVENTORY_INVALID", "pr4_scope")
    previous_nodes += pr4["nodes"]
    previous_sources.update(pr4["test_source_sha256"])
    raw = (PACKAGE / "manifests/pr4_diagnostics_required_tests.json").read_bytes()
    if sha256_bytes(raw) != PR4_DIAGNOSTICS_REQUIRED_PIN:
        fail("G3_TEST_INVENTORY_INVALID", "pr4_diagnostics_manifest_pin")
    repair = read_json(raw)
    repair_sources = {"tests/evals/g3/test_budget_diagnostics.py"}
    if (repair.get("revision") != "g3-pr4-diagnostics-required-tests-v1" or not repair["nodes"]
            or any(not n.startswith("tests/evals/g3/test_budget_diagnostics.py::") for n in repair["nodes"])
            or set(repair["test_source_sha256"]) != repair_sources
            or set(repair["nodes"]) & set(previous_nodes) or repair_sources & set(previous_sources)):
        fail("G3_TEST_INVENTORY_INVALID", "pr4_diagnostics_scope")
    previous_nodes += repair["nodes"]
    previous_sources.update(repair["test_source_sha256"])
    raw = (PACKAGE / "manifests/pr5_required_tests.json").read_bytes()
    if sha256_bytes(raw) != PR5_REQUIRED_PIN:
        fail("G3_TEST_INVENTORY_INVALID", "pr5_manifest_pin")
    pr5 = read_json(raw)
    pr5_sources = {"tests/evals/g3/test_pr5.py"}
    if (pr5.get("revision") != "g3-pr5-required-tests-v1" or not pr5["nodes"]
            or any(not n.startswith("tests/evals/g3/test_pr5.py::") for n in pr5["nodes"])
            or set(pr5["test_source_sha256"]) != pr5_sources
            or set(pr5["nodes"]) & set(previous_nodes) or pr5_sources & set(previous_sources)):
        fail("G3_TEST_INVENTORY_INVALID", "pr5_scope")
    previous_nodes += pr5["nodes"]
    previous_sources.update(pr5["test_source_sha256"])
    raw = (PACKAGE / "manifests/pr5_wire_required_tests.json").read_bytes()
    if sha256_bytes(raw) != PR5_WIRE_REQUIRED_PIN:
        fail("G3_TEST_INVENTORY_INVALID", "pr5_wire_manifest_pin")
    wire = read_json(raw)
    if (wire.get("revision") != "g3-pr5-wire-required-tests-v1" or not wire["nodes"]
            or any(not n.startswith("tests/evals/g3/test_pr5_wire.py::") for n in wire["nodes"])
            or set(wire["test_source_sha256"]) != {"tests/evals/g3/test_pr5_wire.py"}
            or set(wire["nodes"]) & set(previous_nodes)):
        fail("G3_TEST_INVENTORY_INVALID", "pr5_wire_scope")
    previous_nodes += wire["nodes"]
    previous_sources.update(wire["test_source_sha256"])
    raw = (PACKAGE / "manifests/pr5_review_required_tests.json").read_bytes()
    if sha256_bytes(raw) != PR5_REVIEW_REQUIRED_PIN:
        fail("G3_TEST_INVENTORY_INVALID", "pr5_review_manifest_pin")
    review = read_json(raw)
    if (review.get("revision") != "g3-pr5-review-required-tests-v1" or not review["nodes"]
            or any(not n.startswith("tests/evals/g3/test_pr5_review.py::") for n in review["nodes"])
            or set(review["test_source_sha256"]) != {"tests/evals/g3/test_pr5_review.py"}
            or set(review["nodes"]) & set(previous_nodes)):
        fail("G3_TEST_INVENTORY_INVALID", "pr5_review_scope")
    previous_nodes += review["nodes"]
    previous_sources.update(review["test_source_sha256"])
    raw = (PACKAGE / "manifests/fact_signature_required_tests.json").read_bytes()
    if sha256_bytes(raw) != FACT_REQUIRED_PIN:
        fail("G3_TEST_INVENTORY_INVALID", "fact_signature_manifest_pin")
    fact = read_json(raw)
    if (fact.get("revision") != "g3-fact-signature-required-tests-v1" or not fact["nodes"]
            or any(not n.startswith("tests/evals/g3/test_fact_signature.py::") for n in fact["nodes"])
            or set(fact["test_source_sha256"]) != {"tests/evals/g3/test_fact_signature.py",
                                                 "tests/evals/g3/fact_signature_support.py"}
            or set(fact["nodes"]) & set(previous_nodes)):
        fail("G3_TEST_INVENTORY_INVALID", "fact_signature_scope")
    return {**legacy, "nodes": previous_nodes + fact["nodes"],
            "test_source_sha256": {**previous_sources, **fact["test_source_sha256"]}}


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
