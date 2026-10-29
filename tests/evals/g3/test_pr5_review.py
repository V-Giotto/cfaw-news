"""Independent-review regressions: test control plane, effective support and schema CLI."""

import json
import os
import shutil
import subprocess
import sys
from types import SimpleNamespace
from uuid import uuid4

import pytest

from evals.intelligence_g3 import pytest_control
from evals.intelligence_g3.artifacts import OUTPUT_BASE, load_campaign, release
from evals.intelligence_g3.contracts import PACKAGE, ROOT
from evals.intelligence_g3.evaluate import evaluate_rows
from evals.intelligence_g3.experiments import predict
from evals.intelligence_g3.metrics import aggregate, measure
from evals.intelligence_g3.pytest_control import command_environment, control_files, snapshot
from evals.intelligence_g3.reproduce import jobs
from evals.intelligence_v1.exceptions import ContractError

from .test_pr5 import labels_for, result_for, source

PIN = "56f2244812449db5ddb5a8bd2384cb302a3f9d66fb1205be167e9308da530daf"


@pytest.fixture(scope="module")
def campaign():
    return load_campaign(PACKAGE / "manifests/pr5_campaign.json", PIN)


@pytest.fixture
def work():
    path = OUTPUT_BASE / "tests/pr5-review" / uuid4().hex
    path.mkdir(parents=True)
    return path


@pytest.fixture
def control_copy(work):
    for name in pytest_control.APPROVED_FILES:
        dest = work / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes((ROOT / name).read_bytes())
    assert control_files(work) == pytest_control.APPROVED_FILES
    return work


@pytest.mark.parametrize("name", ["conftest.py", "pytest.ini", ".pytest.ini", "pytest.toml",
    ".pytest.toml", "tox.ini", "setup.cfg", "tests/nested/conftest.py"])
def test_new_test_control_file_is_rejected(control_copy, name):
    path = control_copy / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("# controlled negative fixture\n", encoding="utf-8")
    with pytest.raises(ContractError, match="G3_TEST_CONTROL_UNAPPROVED"):
        control_files(control_copy)


@pytest.mark.parametrize("name", list(pytest_control.APPROVED_FILES))
def test_changed_approved_control_file_is_rejected(control_copy, name):
    with (control_copy / name).open("a", encoding="utf-8") as stream:
        stream.write("\n# changed control input\n")
    with pytest.raises(ContractError, match="G3_TEST_CONTROL_UNAPPROVED"):
        control_files(control_copy)


@pytest.mark.parametrize("name,value", [("PYTEST_ADDOPTS", "-p evil"), ("PYTEST_PLUGINS", "evil"),
    ("PYTEST_DISABLE_PLUGIN_AUTOLOAD", "0"), ("PYTEST_DEBUG", "1"), ("PYTHONHOME", "unapproved"),
    ("PYTHONPATH", "unapproved"), ("PYTHONWARNINGS", "ignore"), ("PYTEST_VERSION", "0.0")])
def test_controlling_environment_injection_is_rejected(monkeypatch, name, value):
    monkeypatch.setenv(name, value)
    with pytest.raises(ContractError, match="G3_TEST_CONTROL_UNAPPROVED"):
        snapshot()


def test_runtime_plugin_discovery_change_changes_fingerprint(monkeypatch):
    before = release()
    original = pytest_control.importlib.metadata.entry_points
    entries = list(original(group="pytest11"))
    extra = SimpleNamespace(name="controlled-extra", value="controlled.plugin", dist=SimpleNamespace(
        name="controlled-negative-not-installed", version="1"))
    monkeypatch.setattr(pytest_control.importlib.metadata, "entry_points", lambda **kw: [*entries, extra])
    assert release() != before


def test_diagnostic_current_test_does_not_invalidate_control_plane(monkeypatch):
    before = snapshot()
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "diagnostic-only (call)")
    assert snapshot() == before
    assert before["environment"]["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] == "1"
    assert before["runtime"]["packages"]["_pytest"]["files"]


def test_real_unapproved_runtime_plugin_is_rejected_before_hook_execution(work):
    marker = work / "EVIL_MUST_NOT_EXECUTE"
    body = work / "test_body.py"
    body.write_text("def test_body():\n    assert False\n", encoding="utf-8")
    script = f'''
from pathlib import Path
from evals.intelligence_g3.pytest_runner import Guard
import pytest
class Evil:
    def pytest_pyfunc_call(self, pyfuncitem):
        Path({str(marker)!r}).write_text("executed")
        return True
guard = Guard()
raise SystemExit(pytest.main(["-q", "-c", {str(ROOT / 'pyproject.toml')!r},
    "--confcutdir", {str(ROOT)!r}, "-p", "no:cacheprovider", {str(body)!r}], plugins=[guard, Evil()]))
'''
    run = subprocess.run([sys.executable, "-B", "-c", script], cwd=ROOT,
        env={**os.environ, **command_environment()}, capture_output=True, text=True, timeout=60)
    (work / "unapproved-plugin.log").write_text(run.stdout + run.stderr, encoding="utf-8")
    assert run.returncode != 0
    assert "G3_TEST_CONTROL_UNAPPROVED" in run.stdout + run.stderr
    assert not marker.exists()


def test_runner_rejects_unregistered_plugin_argument(work):
    run = subprocess.run([sys.executable, "-B", "-m", "evals.intelligence_g3.pytest_runner",
        "--mode", "collect", "--inventory", str(work / "inventory.json"),
        "--control-record", str(work / "control.json"), "-p", "unapproved.plugin"],
        cwd=ROOT, env={**os.environ, **command_environment()}, capture_output=True, text=True, timeout=60)
    assert run.returncode == 2
    assert not (work / "control.json").exists()


@pytest.mark.parametrize("horizon", [1, 3, 7])
def test_unrelated_pressure_case_cannot_inflate_window_support(campaign, horizon):
    case = f"material-ack-{horizon}d"
    one, _ = measure(result_for(campaign, case), labels_for(campaign, case), horizon)
    stress, _ = measure(result_for(campaign, "crowded14"), labels_for(campaign, "crowded14"), None)
    key = f"RevisitCoverage@{horizon}d"
    assert stress["metrics"][key]["sample_count"] == stress["metrics"][key]["event_family_count"] == 0
    assert stress["metrics"][key]["undefined_reason"] == "outside_revisit_window"
    combined = next(r for r in aggregate([one, stress]) if r["axis"] == "all")
    assert combined["metrics"][key] == one["metrics"][key]
    assert combined["metrics"][key]["sample_count"] == combined["metrics"][key]["event_family_count"] == 1
    assert combined["dataset_support"]["sample_count"] == 15
    assert combined["dataset_support"]["event_family_count"] == 14


def test_full_frozen_reference_window_support_is_18_samples_one_family(campaign):
    inputs = {c.case_id: source(campaign, c.case_id) for c in campaign.cases}
    predictions = [predict(inputs[j.case_id], j) for j in jobs(campaign) if j.variant == "p1"]
    metrics, _ = evaluate_rows(campaign, predictions)
    cell = next(r for r in metrics["aggregates"] if r["axis"] == "all")
    assert cell["dataset_support"]["sample_count"] == 141
    assert cell["dataset_support"]["event_family_count"] == 16
    for horizon in (1, 3, 7):
        value = cell["metrics"][f"RevisitCoverage@{horizon}d"]
        assert (value["numerator"], value["denominator"]) == (9, 9)
        assert (value["sample_count"], value["event_family_count"]) == (18, 1)
        assert len(cell["metric_support"][f"RevisitCoverage@{horizon}d"]["family_ids"]) == 1


def test_no_applicable_window_has_zero_support_and_undefined_ratio(campaign):
    stress, _ = measure(result_for(campaign, "crowded14"), labels_for(campaign, "crowded14"), None)
    aggregate_row = next(r for r in aggregate([stress]) if r["axis"] == "all")
    value = aggregate_row["metrics"]["RevisitCoverage@1d"]
    assert value["value"] is None and value["numerator"] == value["denominator"] == 0
    assert value["sample_count"] == value["event_family_count"] == 0
    assert value["undefined_reason"] == "no_applicable_samples_in_this_cell"


@pytest.mark.parametrize("fault", ["changed", "missing", "extra"])
def test_actual_schema_cli_rejects_corrupted_schema(work, fault):
    folder = work / "schema"
    shutil.copytree(PACKAGE / "schema/v2", folder)
    file = next(folder.glob("*.schema.json"))
    if fault == "changed":
        file.write_text(json.dumps({"not": "the registered schema"}), encoding="utf-8")
    elif fault == "missing":
        file.unlink()
    else:
        (folder / "extra.schema.json").write_text("{}", encoding="utf-8")
    run = subprocess.run([sys.executable, "-B", "-m", "evals.intelligence_g3.ranking_schema",
        "--check-schemas", "--schema-dir", str(folder)], cwd=ROOT,
        env={**os.environ, **command_environment()}, capture_output=True, text=True, timeout=60)
    assert run.returncode == 1
    assert "G3_SCHEMA_INVALID" in run.stdout


def test_actual_schema_cli_checks_real_schema_and_rejects_unknown_arguments():
    for args, expected in ((["--check-schemas"], 0), (["--does-not-exist"], 2)):
        run = subprocess.run([sys.executable, "-B", "-m", "evals.intelligence_g3.ranking_schema", *args],
            cwd=ROOT, env={**os.environ, **command_environment()}, capture_output=True, text=True, timeout=60)
        assert run.returncode == expected
