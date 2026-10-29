"""Registered pytest invocation with an explicit configuration and plugin allowlist."""

import argparse
import inspect
import sys
from pathlib import Path

from evals.intelligence_g2.contracts import json_bytes
from evals.intelligence_g2.replay import safe_path
from evals.intelligence_v1.hashing import sha256_bytes

from .contracts import ROOT, fail
from .pytest_control import EXPLICIT_PLUGIN, allowed_plugin_files, snapshot


def pytest_arguments(mode, *, inventory=None, junit=None, basetemp=None):
    args = ["-q", "-c", str(ROOT / "pyproject.toml"), "--rootdir=" + str(ROOT),
            "--confcutdir=" + str(ROOT), "-p", "no:cacheprovider", "-p", EXPLICIT_PLUGIN,
            "-o", "faulthandler_timeout=120"]
    if mode == "collect":
        args += ["--collect-only", "--g3-inventory", str(inventory)]
    else:
        args += ["--junitxml=" + str(junit), "--basetemp=" + str(basetemp)]
    args.append(str(ROOT / ("tests/evals/g3" if mode == "g3" else "tests")))
    return args


class Guard:
    def __init__(self):
        self.before = snapshot()
        self.allowed = allowed_plugin_files()
        self.plugins = []

    def check(self, manager):
        plugins = []
        for name, plugin in manager.list_name_plugin():
            if plugin is None or plugin is self:
                continue
            try:
                origin = getattr(plugin, "__file__", None) or inspect.getsourcefile(
                    plugin if inspect.isclass(plugin) else type(plugin))
            except (OSError, TypeError):
                origin = None
            path = str(Path(origin).resolve()) if origin else ""
            if path not in self.allowed or sha256_bytes(Path(path).read_bytes()) != self.allowed[path]:
                fail("G3_TEST_CONTROL_UNAPPROVED", "loaded_plugin:" + str(name))
            plugins.append(dict(name=name, path=path, sha256=self.allowed[path]))
        # Verify hook function origins as well as plugin-object origins.
        for name in dir(manager.hook):
            hook = getattr(manager.hook, name)
            if not hasattr(hook, "get_hookimpls"):
                continue
            for impl in hook.get_hookimpls():
                if impl.plugin is self:
                    continue
                try:
                    origin = inspect.getsourcefile(impl.function)
                except (OSError, TypeError):
                    origin = None
                if origin is None or str(Path(origin).resolve()) not in self.allowed:
                    fail("G3_TEST_CONTROL_UNAPPROVED", "hook_origin:" + name)
        self.plugins = sorted(plugins, key=lambda p: (p["name"], p["path"]))

    def pytest_configure(self, config):
        self.check(config.pluginmanager)

    def pytest_collection_finish(self, session):
        self.check(session.config.pluginmanager)

    def pytest_sessionfinish(self, session, exitstatus):
        self.check(session.config.pluginmanager)
        if snapshot() != self.before:
            fail("G3_TEST_CONTROL_CHANGED", "session_control_plane")


def verify_execution(record, *, mode, inventory=None, junit=None, basetemp=None):
    expected = pytest_arguments(mode, inventory=inventory, junit=junit, basetemp=basetemp)
    plane = snapshot()
    if (record.get("revision") != "g3-pytest-execution-v1" or record.get("exit_code") != 0
            or record.get("mode") != mode or record.get("pytest_argv") != expected
            or record.get("before") != plane or record.get("after") != plane
            or not record.get("loaded_plugins")):
        fail("G3_TEST_CONTROL_CHANGED", "execution_record")
    allowed = allowed_plugin_files()
    for plugin in record["loaded_plugins"]:
        if allowed.get(plugin["path"]) != plugin["sha256"]:
            fail("G3_TEST_CONTROL_UNAPPROVED", "recorded_plugin")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("collect", "g3", "full"), required=True)
    parser.add_argument("--inventory")
    parser.add_argument("--junit")
    parser.add_argument("--basetemp")
    parser.add_argument("--control-record", required=True)
    args = parser.parse_args(argv)
    if ((args.mode == "collect" and (not args.inventory or args.junit or args.basetemp))
            or (args.mode != "collect" and (args.inventory or not args.junit or not args.basetemp))):
        parser.error("mode-specific inventory or junit/basetemp required")
    try:
        from .artifacts import OUTPUT_BASE, write

        # Never inherit plugin or option injection. This validation happens before
        # importing pytest or loading any conftest/plugin.
        before = snapshot()
        import os

        os.environ["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
        for name in ("inventory", "junit", "basetemp", "control_record"):
            value = getattr(args, name)
            if value:
                setattr(args, name, str(safe_path(value, areas=(OUTPUT_BASE,), code="G3_PATH_INVALID")))
        guard = Guard()
        import pytest

        arguments = pytest_arguments(args.mode, inventory=args.inventory, junit=args.junit,
                                     basetemp=args.basetemp)
        code = int(pytest.main(arguments, plugins=[guard]))
        after = snapshot()
        if before != after:
            fail("G3_TEST_CONTROL_CHANGED", "after_pytest")
        record = dict(revision="g3-pytest-execution-v1", mode=args.mode, exit_code=code,
                      pytest_argv=arguments, before=before, after=after, loaded_plugins=guard.plugins)
        target = Path(args.control_record)
        write(target.parent, target.name, record)
        return code
    except (ValueError, OSError, TypeError) as error:
        print(json_bytes(dict(ok=False, code=getattr(error, "code", "G3_TEST_CONTROL_INVALID"),
                              field=getattr(error, "field", "pytest_control"))).decode(), end="")
        return 1


if __name__ == "__main__":
    sys.exit(main())
