import asyncio
import copy
import json
import subprocess
import sys

import pytest

from evals.intelligence_g2.pr6.acceptance import decide
from evals.intelligence_g2.pr6.checks import NAMES, command_plan
from evals.intelligence_g2.pr6.contracts import DevelopmentReference, data, parse
from evals.intelligence_g2.pr6.handoff import views
from evals.intelligence_g2.pr6.junit_inventory import requirements, verify_inventory
from evals.intelligence_g2.pr6.junit_inventory import test_sources as sources
from evals.intelligence_g2.pr6.manifest import ROOT, relative
from evals.intelligence_g2.pr6.predict import inputs_for, run_job
from evals.intelligence_v1.exceptions import ContractError

from ..support import output_path
from .support import campaign, job


@pytest.mark.parametrize(
    "path", ["../reference/a", "a/../b", "./a", "a//b", "C:/private", "a\\b", "/absolute"]
)
def test_manifest_paths_are_not_normalized_into_authority(path):
    with pytest.raises(ContractError) as error:
        relative(path)
    assert (error.value.code, error.value.stage, error.value.field) == (
        "MANIFEST_PATH_INVALID",
        "pr6",
        "path",
    )


def test_future_input_precedes_full_parse(monkeypatch):
    import evals.intelligence_g2.pr6.predict as module

    calls = []
    original = module.parse

    def observe(model, raw):
        calls.append(model.__name__)
        return original(model, raw)

    monkeypatch.setattr(module, "parse", observe)
    with pytest.raises(ContractError) as error:
        inputs_for(job("E01-negative"), campaign())
    assert error.value.code == "FUTURE_VERSION" and calls == []


@pytest.mark.parametrize("fault", ["omitted", "duplicate", "mapping", "source", "skip"])
def test_inventory_rejects_tampered_requirements(fault):
    inventory = dict(
        nodes=[f"tests/evals/g2/test_case.py::test_T{i:02}" for i in range(1, 47)],
        test_source_sha256=sources(),
    )
    required = requirements(inventory)
    verify_inventory(required, inventory)
    changed = copy.deepcopy(required)
    if fault == "omitted":
        changed["nodes"].pop()
    elif fault == "duplicate":
        changed["nodes"].append(changed["nodes"][0])
    elif fault == "mapping":
        changed["requirements"]["G2-T25"] = [changed["nodes"][0]]
    elif fault == "source":
        changed["test_source_sha256"] = {}
    else:
        changed["skip_exemptions"].append(
            dict(node=changed["nodes"][0], platform=sys.platform, reason="all allowed")
        )
    with pytest.raises(ContractError) as error:
        verify_inventory(changed, inventory)
    assert error.value.code == "G2_PR6_TEST_INVENTORY_INVALID"


def test_missing_gate_is_blocked_and_unknown_gate_rejected():
    result = decide({}, "a" * 40)
    assert len(result.gates) == 10 and {v.status for v in result.gates.values()} == {"BLOCKED"}
    with pytest.raises(ContractError) as error:
        decide({"fake_pass": next(iter(result.gates.values()))}, "a" * 40)
    assert error.value.field == "gate_names"


def test_reference_unknown_check_is_not_a_pass():
    with pytest.raises(ContractError) as error:
        parse(
            DevelopmentReference,
            dict(
                case_id="x",
                error_mode="E01",
                side="positive",
                expected_code=None,
                checks=["always_pass"],
            ),
        )
    assert error.value.code == "G2_PR6_SCHEMA_INVALID"


def test_check_commands_cover_all_regressions_without_live_install():
    plan = command_plan(output_path())
    assert len(plan) == len(NAMES) and {p["name"] for p in plan} == NAMES
    full = next(p for p in plan if p["name"] == "pytest-full")
    assert full["argv"].count("pytest") == 1 and "tests/evals" not in full["argv"]
    assert full["artifacts"] == ("full.xml",)
    assert all("install" not in p["argv"] and "--live" not in p["argv"] for p in plan)


@pytest.mark.parametrize(
    "action",
    [
        "reference_stat",
        "reference_os_stat",
        "reference_open",
        "private_stat",
        "network",
        "tool",
        "outside_write",
        "reference_import",
    ],
)
def test_prediction_audit_rejects_capabilities_in_fresh_process(action):
    script = """
import json, socket, subprocess, sys, os
from pathlib import Path
from evals.intelligence_g2.pr6.predict import audit_prediction
from evals.intelligence_g2.pr6.manifest import ROOT
from evals.intelligence_v1.exceptions import ContractError
audit_prediction(ROOT/".tmp/evals/g2/audit-child")
action=sys.argv[1]
try:
    if action=="reference_stat": (ROOT/"evals/intelligence_g2/fixtures/pr6/v1/reference/manifest_v5.json").stat()
    elif action=="reference_os_stat": os.stat(ROOT/"evals/intelligence_g2/fixtures/pr6/v1/reference/manifest_v5.json")
    elif action=="reference_open": (ROOT/"evals/intelligence_v1/claims/claims.jsonl").read_bytes()
    elif action=="private_stat": (ROOT/".env").stat()
    elif action=="network": socket.socket()
    elif action=="tool": subprocess.run([sys.executable,"-c","pass"])
    elif action=="reference_import": __import__("evals.intelligence_g2.pr2.reference_loader")
    else: (ROOT/".tmp/audit-outside-canary").write_text("forbidden")
except ContractError as error:
    print(json.dumps(dict(code=error.code,stage=error.stage,field=error.field)))
else: raise AssertionError("capability accepted")
"""
    result = subprocess.run(
        [sys.executable, "-B", "-c", script, action],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stderr
    issue = json.loads(result.stdout)
    assert issue["code"] == "G2_PR6_CAPABILITY_DENIED" and issue["stage"] == "pr6"
    assert not (ROOT / ".tmp/audit-outside-canary").exists()


def test_handoff_retains_native_identity_and_no_rank():
    async def check():
        rows, _ = await run_job(job("E06-correction"), campaign())
        exported = views(rows[-1], "trace.json")
        assert exported and exported[0].event_key == rows[-1].grouping.events[0].event_key
        assert exported[0].event_revision == rows[-1].grouping.events[0].event_revision
        assert exported[0].final_personalized_rank is None
        assert exported[0].rule_item == data(rows[-1].rule.items[0])

    asyncio.run(check())
