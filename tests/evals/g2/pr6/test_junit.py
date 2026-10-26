import hashlib
import json
import xml.etree.ElementTree as ET

import pytest

from evals.intelligence_g2.pr6.contracts import cli_entry
from evals.intelligence_g2.pr6.junit_inventory import verify_junit
from evals.intelligence_v1.exceptions import ContractError


@pytest.mark.parametrize(
    "fault", ["missing", "duplicate", "failure", "error", "skip", "no_property", "no_value"]
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
            ET.SubElement(
                props, "property", name="pr6_nodeid",
                **({"value": nodes[0]} if fault != "no_value" else {}),
            )
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


@pytest.mark.parametrize("outcome,code", [
    ("failure", "G2_PR6_REQUIRED_TEST_FAILED"),
    ("error", "G2_PR6_REQUIRED_TEST_FAILED"),
    ("skipped", "G2_PR6_UNEXEMPT_SKIP"),
])
def test_review_sensitive_nodeid_is_hashed_in_public_diagnostic(tmp_path, capsys, outcome, code):
    canary = "TEST_ONLY_PR6_CANARY_1234567890"
    node = "tests/example.py::test_case[api_key=" + canary + "]"
    root = ET.Element("testsuites")
    suite = ET.SubElement(root, "testsuite")
    case = ET.SubElement(suite, "testcase")
    props = ET.SubElement(case, "properties")
    ET.SubElement(props, "property", name="pr6_nodeid", value=node)
    ET.SubElement(case, outcome, message=canary)
    path = tmp_path / "full.xml"
    ET.ElementTree(root).write(path)
    required = dict(nodes=[node], skip_exemptions=[], requirements={})
    assert cli_entry(lambda: verify_junit(required, path)) == 1
    captured = capsys.readouterr()
    stdout = captured.out
    assert node not in stdout and canary not in stdout + captured.err
    assert json.loads(stdout) == dict(ok=False, code=code, stage="pr6",
        field="node_sha256:" + hashlib.sha256(node.encode("utf-8")).hexdigest())


def test_review_raw_nodeids_still_require_exact_match_and_skip_exemption(tmp_path):
    node = "tests/example.py::test_case[configuration=ordinary]"
    root = ET.Element("testsuites")
    suite = ET.SubElement(root, "testsuite")
    case = ET.SubElement(suite, "testcase")
    props = ET.SubElement(case, "properties")
    ET.SubElement(props, "property", name="pr6_nodeid", value=node)
    path = tmp_path / "full.xml"
    ET.ElementTree(root).write(path)
    required = dict(nodes=[node], skip_exemptions=[], requirements={})
    assert verify_junit(required, path)["nodes"] == 1
    with pytest.raises(ContractError) as error:
        verify_junit({**required, "nodes": [node + "-different"]}, path)
    assert (error.value.code, error.value.stage, error.value.field) == (
        "G2_PR6_JUNIT_INVALID", "pr6", "complete_node_set"
    )
    ET.SubElement(case, "skipped", message="exact reason")
    ET.ElementTree(root).write(path)
    required["skip_exemptions"] = [dict(node=node, platform="unit", reason="exact reason")]
    assert verify_junit(required, path, platform="unit")["skipped"] == 1
    with pytest.raises(ContractError) as error:
        verify_junit({**required, "skip_exemptions": [dict(node=node + "-different",
            platform="unit", reason="exact reason")]}, path, platform="unit")
    assert (error.value.code, error.value.stage, error.value.field) == (
        "G2_PR6_UNEXEMPT_SKIP", "pr6",
        "node_sha256:" + hashlib.sha256(node.encode("utf-8")).hexdigest()
    )
