"""Approved pytest control plane. Discovery occurs before any conftest is imported."""

import importlib.metadata
import importlib.util
import os
import sys
from pathlib import Path

from evals.intelligence_v1.hashing import sha256_bytes

from .contracts import ROOT, fail

REVISION = "g3-pytest-control-v1"
APPROVED_FILES = {
    "pyproject.toml": "de24cd2072f46d360be071f1bb60f2b184f3ab680d0636e1e791264d356ed7da",
    "tests/evals/conftest.py": "fe2e72aa90b05ea7b01295fc7e9445cd1443b0ca7f077e6ceba7676059e72f5b",
}
CONFIG_NAMES = ("conftest.py", "pytest.ini", ".pytest.ini", "pytest.toml", ".pytest.toml",
                "tox.ini", "setup.cfg", "pyproject.toml")
EXPLICIT_PLUGIN = "evals.intelligence_g3.junit_inventory"
PYTHON_CONTROLS = {"PYTHONPATH", "PYTHONUTF8", "PYTHONHASHSEED", "PYTHONDONTWRITEBYTECODE",
                   "PYTHONNOUSERSITE"}


def validate_environment(environment=None):
    environment = os.environ if environment is None else environment
    for name in environment:
        if (name.startswith("PYTEST_") and name not in
                {"PYTEST_CURRENT_TEST", "PYTEST_VERSION", "PYTEST_DISABLE_PLUGIN_AUTOLOAD"}):
            fail("G3_TEST_CONTROL_UNAPPROVED", "environment:" + name)
        if name.startswith("PYTHON") and name not in PYTHON_CONTROLS:
            fail("G3_TEST_CONTROL_UNAPPROVED", "environment:" + name)
    if environment.get("PYTEST_DISABLE_PLUGIN_AUTOLOAD") not in (None, "1"):
        fail("G3_TEST_CONTROL_UNAPPROVED", "plugin_autoload")
    if environment.get("PYTEST_VERSION") not in (None, importlib.metadata.version("pytest")):
        fail("G3_TEST_CONTROL_UNAPPROVED", "environment:PYTEST_VERSION")
    path = environment.get("PYTHONPATH")
    if path is not None and Path(path).resolve() != (ROOT / "backend").resolve():
        fail("G3_TEST_CONTROL_UNAPPROVED", "environment:PYTHONPATH")


def command_environment(seed="1"):
    validate_environment()
    return dict(PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1", PYTHONHASHSEED=str(seed),
                PYTHONPATH=str(ROOT / "backend"), PYTHONNOUSERSITE="1",
                PYTEST_DISABLE_PLUGIN_AUTOLOAD="1")


def control_files(root=ROOT):
    root = Path(root).resolve()
    candidates = [root / name for name in CONFIG_NAMES]
    candidates += [p for p in (root / "tests").rglob("*")
                   if p.is_file() and p.name in CONFIG_NAMES]
    existing = {p.relative_to(root).as_posix(): p for p in candidates if p.is_file()}
    if set(existing) != set(APPROVED_FILES):
        fail("G3_TEST_CONTROL_UNAPPROVED", "config_or_conftest_set_and_hashes")
    for file in existing.values():
        if any(p.is_symlink() or getattr(p, "is_junction", lambda: False)()
               for p in (file, *file.parents) if p != root.parent):
            fail("G3_TEST_CONTROL_UNAPPROVED", "linked_control_file")
    current = {name: sha256_bytes(p.read_bytes()) for name, p in existing.items()}
    if current != APPROVED_FILES:
        fail("G3_TEST_CONTROL_UNAPPROVED", "config_or_conftest_set_and_hashes")
    return current


def runtime():
    # Autoload is disabled. Still bind installed pytest11 discovery metadata so
    # installing/removing a plugin invalidates previous credentials.
    entries = []
    for entry in importlib.metadata.entry_points(group="pytest11"):
        entries.append(dict(name=entry.name, value=entry.value, distribution=entry.dist.name,
                            version=entry.dist.version))
    entries.sort(key=lambda e: (e["distribution"], e["name"], e["value"]))
    packages, hashes = {}, {}
    for module, distribution in (("pytest", "pytest"), ("_pytest", "pytest"), ("pluggy", "pluggy")):
        dist = importlib.metadata.distribution(distribution)
        folder = Path(dist.locate_file(module)).resolve()
        spec = importlib.util.find_spec(module)
        if spec is None or Path(spec.origin).resolve() != folder / "__init__.py":
            fail("G3_TEST_CONTROL_UNAPPROVED", "runtime_module_origin:" + module)
        files = {p.relative_to(folder).as_posix(): sha256_bytes(p.read_bytes())
                 for p in sorted(folder.rglob("*")) if p.is_file() and p.suffix in {".py", ".pyc"}}
        packages[module] = dict(distribution=distribution, version=dist.version,
                                path=str(folder), files=files)
        hashes.update({str((folder / p).resolve()): sha for p, sha in files.items()})
    return dict(packages=packages, installed_pytest11=entries), hashes


def snapshot():
    validate_environment()
    files = control_files()
    packages, _ = runtime()
    startup = {}
    # Fingerprint startup path controls, never their raw contents or secrets.
    for item in sys.path:
        path = Path(item or ROOT)
        if not path.is_dir():
            continue
        candidates = [path / "sitecustomize.py", path / "usercustomize.py"]
        if path.name.lower() == "site-packages":
            candidates += list(path.glob("*.pth"))
        for file in candidates:
            if file.is_file():
                startup[str(file.resolve())] = sha256_bytes(file.read_bytes())
    return dict(revision=REVISION, files=files, runtime=packages, startup_files=startup,
                explicit_plugin=EXPLICIT_PLUGIN, environment=command_environment(),
                discovery=dict(config="pyproject.toml", confcutdir=str(ROOT), rootdir=str(ROOT),
                               autoload=False, test_root="tests"),
                diagnostic_environment_excluded=["PYTEST_CURRENT_TEST", "PYTEST_VERSION_matches_runtime"])


def allowed_plugin_files():
    _, files = runtime()
    for name in ("tests/evals/conftest.py", "evals/intelligence_g3/junit_inventory.py",
                 "evals/intelligence_g2/pr6/junit_inventory.py"):
        path = (ROOT / name).resolve()
        files[str(path)] = sha256_bytes(path.read_bytes())
    return files
