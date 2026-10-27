import copy
import xml.etree.ElementTree as ET

import pytest

from evals.intelligence_g2.pr6.junit_inventory import test_sources as current_sources
from evals.intelligence_g2.pr6.junit_inventory import verify_junit
from evals.intelligence_g3.junit_inventory import requirements, verify_inventory
from evals.intelligence_v1.exceptions import ContractError


def test_current_inventory_preserves_all_frozen_nodes_and_sources():
    required = requirements()
    inventory = dict(nodes=required["nodes"], test_source_sha256=current_sources())
    assert verify_inventory(inventory) == required
    assert any(n.startswith("tests/evals/g3/") for n in required["nodes"])
    assert all(required["requirements"].values())


@pytest.mark.parametrize("fault", ["missing_old", "missing_new", "duplicate", "unknown", "source"])
def test_inventory_rejects_missing_duplicate_foreign_or_stale_evidence(fault):
    required = requirements()
    inventory = dict(nodes=required["nodes"][:], test_source_sha256=current_sources())
    if fault == "missing_old":
        inventory["nodes"].pop(0)
    elif fault == "missing_new":
        inventory["nodes"].remove(next(n for n in inventory["nodes"] if n.startswith("tests/evals/g3/")))
    elif fault == "duplicate":
        inventory["nodes"].append(inventory["nodes"][0])
    elif fault == "unknown":
        inventory["nodes"].append("tests/evals/g3/test_invented.py::test_unregistered")
    else:
        inventory["test_source_sha256"] = {}
    with pytest.raises(ContractError, match="G3_TEST_INVENTORY_INVALID"):
        verify_inventory(inventory)


@pytest.mark.parametrize("fault", ["missing", "failure", "skip"])
def test_complete_junit_requires_new_and_old_tests_without_new_skip_exemptions(tmp_path, fault):
    required = requirements()
    xml = ET.Element("testsuites")
    suite = ET.SubElement(xml, "testsuite")
    for node in required["nodes"]:
        if fault == "missing" and node == required["nodes"][-1]:
            continue
        case = ET.SubElement(suite, "testcase")
        props = ET.SubElement(case, "properties")
        ET.SubElement(props, "property", name="pr6_nodeid", value=node)
        if node == required["nodes"][-1] and fault != "missing":
            ET.SubElement(case, "failure" if fault == "failure" else "skipped", message="synthetic")
    path = tmp_path / "synthetic.xml"
    ET.ElementTree(xml).write(path)
    with pytest.raises(ContractError):
        verify_junit(copy.deepcopy(required), path)
