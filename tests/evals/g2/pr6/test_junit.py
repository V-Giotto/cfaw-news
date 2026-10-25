import xml.etree.ElementTree as ET

import pytest

from evals.intelligence_g2.pr6.junit_inventory import verify_junit
from evals.intelligence_v1.exceptions import ContractError


@pytest.mark.parametrize(
    "fault", ["missing", "duplicate", "failure", "error", "skip", "no_property"]
)
def test_full_junit_cannot_hide_bad_or_missing_nodes(tmp_path, fault):
    root = ET.Element("testsuites")
    suite = ET.SubElement(root, "testsuite")
    nodes = ["tests/example.py::test_one"]
    required = dict(nodes=nodes, skip_exemptions=[], requirements={"G2-T25": nodes})
    for _ in range(0 if fault == "missing" else 2 if fault == "duplicate" else 1):
        case = ET.SubElement(suite, "testcase", name="test_one", classname="tests.example")
        if fault != "no_property":
            props = ET.SubElement(case, "properties")
            ET.SubElement(props, "property", name="pr6_nodeid", value=nodes[0])
        if fault in {"failure", "error", "skip"}:
            ET.SubElement(case, "skipped" if fault == "skip" else fault, message="not exempt")
    path = tmp_path / "full.xml"
    ET.ElementTree(root).write(path)
    with pytest.raises(ContractError):
        verify_junit(required, path)


def test_exact_skip_exemption_and_complete_nodes(tmp_path):
    root = ET.Element("testsuites")
    suite = ET.SubElement(root, "testsuite")
    case = ET.SubElement(suite, "testcase")
    props = ET.SubElement(case, "properties")
    node = "tests/example.py::test_one"
    ET.SubElement(props, "property", name="pr6_nodeid", value=node)
    ET.SubElement(case, "skipped", message="exact platform reason")
    path = tmp_path / "full.xml"
    ET.ElementTree(root).write(path)
    req = dict(
        nodes=[node],
        requirements={"G2-T25": [node]},
        skip_exemptions=[dict(node=node, platform="unit", reason="exact platform reason")],
    )
    assert verify_junit(req, path, platform="unit")["skipped"] == 1
    with pytest.raises(ContractError):
        verify_junit(req, path, platform="other")


def test_truncated_junit_is_not_partial_success(tmp_path):
    path = tmp_path / "truncated.xml"
    path.write_bytes(b"<testsuites><testsuite>")
    with pytest.raises(ContractError) as error:
        verify_junit(dict(nodes=[], requirements={}, skip_exemptions=[]), path)
    assert (error.value.code, error.value.stage, error.value.field) == (
        "G2_PR6_JUNIT_INVALID",
        "pr6",
        "xml",
    )
