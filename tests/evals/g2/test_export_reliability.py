"""Atomic publication under controlled native/injected rename failures; no external data."""

import ctypes
import errno
import importlib
import json
import os
from pathlib import Path

import pytest

from evals.intelligence_g2 import replay
from evals.intelligence_g2.contracts import G2Error

from .support import assert_error, output_path

PAYLOADS = {"first.json": b'{"ok":true}\n', "last.jsonl": b""}
PRIVATE_ERROR = "PRIVATE_PATH_OR_PAYLOAD_MUST_NOT_BE_PRINTED"


def denied(winerror=None, number=errno.EACCES):
    error = OSError(number, PRIVATE_ERROR)
    if winerror is not None:
        error.winerror = winerror
    return error


def assert_clean(out):
    assert not out.exists()
    assert not list(out.parent.glob("." + out.name + ".staging-*"))


@pytest.mark.parametrize("winerror", [5, 32, 33])
def test_transient_windows_rename_keeps_complete_atomic_publication(monkeypatch, caplog, winerror):
    out = output_path()
    original = Path.rename
    calls = []

    def rename(self, target):
        calls.append((self, target))
        assert not out.exists()
        assert {p.name: p.read_bytes() for p in self.iterdir()} == PAYLOADS
        if len(calls) == 1:
            raise denied(winerror)
        return original(self, target)

    monkeypatch.setattr(Path, "rename", rename)
    monkeypatch.setattr(replay, "sleep", lambda _: None, raising=False)
    replay.write_payloads(out, PAYLOADS)
    assert len(calls) == 2
    assert {p.name: p.read_bytes() for p in out.iterdir()} == PAYLOADS
    assert not list(out.parent.glob("." + out.name + ".staging-*"))
    assert "publish.rename" in caplog.text and "winerror=" + str(winerror) in caplog.text
    assert PRIVATE_ERROR not in caplog.text and str(out) not in caplog.text


def test_persistent_rename_is_bounded_diagnosed_and_cleaned(monkeypatch, caplog):
    out = output_path()
    attempts, delays = [], []

    def rename(self, target):
        attempts.append(self)
        assert not out.exists()
        raise denied(5)

    monkeypatch.setattr(Path, "rename", rename)
    monkeypatch.setattr(replay, "sleep", delays.append, raising=False)
    with pytest.raises(G2Error) as caught:
        replay.write_payloads(out, PAYLOADS)
    assert len(attempts) == 6 and delays == [0.05, 0.1, 0.2, 0.4, 0.8]
    assert_error(caught, "EXPORT_IO_ERROR", "export",
                 "publish.rename:attempts=6:errno=13:winerror=5")
    assert PRIVATE_ERROR not in str(caught.value) + caplog.text
    assert str(out) not in caplog.text
    assert_clean(out)


@pytest.mark.parametrize("winerror,number", [(None, errno.EACCES), (3, errno.ENOENT),
                                           (112, errno.ENOSPC), (None, errno.EIO)])
def test_other_rename_errors_fail_once_without_retry(monkeypatch, winerror, number):
    out = output_path()
    attempts = []

    def rename(self, target):
        attempts.append(self)
        raise denied(winerror, number)

    def forbidden_sleep(_):
        pytest.fail("non-retryable rename must fail immediately")

    monkeypatch.setattr(Path, "rename", rename)
    monkeypatch.setattr(replay, "sleep", forbidden_sleep, raising=False)
    with pytest.raises(G2Error) as caught:
        replay.write_payloads(out, PAYLOADS)
    assert len(attempts) == 1
    assert_error(caught, "EXPORT_IO_ERROR", "export",
        f"publish.rename:attempts=1:errno={number}:winerror={winerror}")
    assert_clean(out)


@pytest.mark.parametrize("with_file", [False, True])
def test_target_appearing_during_retry_is_never_overwritten(monkeypatch, with_file):
    out = output_path()
    attempts = []

    def rename(self, target):
        attempts.append(self)
        raise denied(5)

    def competing_writer(_):
        out.mkdir()
        if with_file:
            (out / "owner.txt").write_bytes(b"other writer\n")

    monkeypatch.setattr(Path, "rename", rename)
    monkeypatch.setattr(replay, "sleep", competing_writer, raising=False)
    with pytest.raises(G2Error) as caught:
        replay.write_payloads(out, PAYLOADS)
    assert_error(caught, "OUTPUT_EXISTS", "export", "out")
    assert len(attempts) == 1
    assert {p.name: p.read_bytes() for p in out.iterdir()} == (
        {"owner.txt": b"other writer\n"} if with_file else {})
    assert not list(out.parent.glob("." + out.name + ".staging-*"))


@pytest.mark.skipif(os.name != "nt", reason="native Windows directory sharing semantics")
@pytest.mark.parametrize("child_file,expected", [(False, 32), (True, 5)])
def test_native_handle_without_delete_sharing_recovers_after_release(
        monkeypatch, request, child_file, expected):
    from ctypes import wintypes

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    create = kernel.CreateFileW
    create.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
                       wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    create.restype = wintypes.HANDLE
    close = kernel.CloseHandle
    close.argtypes = [wintypes.HANDLE]
    close.restype = wintypes.BOOL
    out = output_path()
    original, errors, attempts = Path.rename, [], []

    def rename(self, target):
        attempts.append(self)
        if len(attempts) > 1:
            return original(self, target)
        # A directory reader gives WinError 32; a reader of its child gives WinError 5.
        # Both deliberately omit FILE_SHARE_DELETE, without changing ACLs or external processes.
        locked = self / "first.json" if child_file else self
        handle = create(str(locked), 0x80000000, 0x1 | 0x2, None, 3,
                        0 if child_file else 0x02000000, None)
        assert handle != wintypes.HANDLE(-1).value, ctypes.get_last_error()
        try:
            try:
                return original(self, target)
            except OSError as exc:
                errors.append(exc.winerror)
                raise
        finally:
            assert close(handle)

    monkeypatch.setattr(Path, "rename", rename)
    replay.write_payloads(out, PAYLOADS)
    assert errors == [expected] and len(attempts) == 2
    assert {p.name: p.read_bytes() for p in out.iterdir()} == PAYLOADS
    request.node.user_properties.append(("native_failure",
        f"CreateFileW_without_FILE_SHARE_DELETE:winerror={expected}"))


def test_interrupted_publication_cleans_staging_without_retry(monkeypatch):
    out = output_path()

    def interrupted(self, target):
        raise KeyboardInterrupt()

    monkeypatch.setattr(Path, "rename", interrupted)
    with pytest.raises(KeyboardInterrupt):
        replay.write_payloads(out, PAYLOADS)
    assert_clean(out)


@pytest.mark.parametrize("generation", [1, 2, 3, 4])
def test_each_public_cli_preserves_safe_publish_diagnostics(monkeypatch, capsys, generation):
    # Isolate CLI error transport; real parent loading/export is covered by the unchanged CLI tests.
    name = "evals.intelligence_g2." + ("" if generation == 1 else f"pr{generation}.") + "replay"
    module = importlib.import_module(name)
    out = output_path()

    def publish(*args, **kwargs):
        replay.write_payloads(out, PAYLOADS)

    def rename(self, target):
        raise denied(5)

    monkeypatch.setattr(module, "run_replay", publish)
    monkeypatch.setattr(Path, "rename", rename)
    monkeypatch.setattr(replay, "sleep", lambda _: None)
    argv = ["--config", "unused.json", "--config-sha256", "0" * 64, "--out", str(out)]
    if generation in (1, 2):
        argv += ["--manifest", "unused.json", "--manifest-sha256", "0" * 64,
                 "--timeline", "DEV-01", "--step" if generation == 1 else "--through-step", "D0"]
    else:
        parent = "grouping" if generation == 3 else "evidence"
        argv += [f"--{parent}-run", "unused", f"--{parent}-manifest-sha256", "0" * 64,
                 "--through-step", "D0"]
    assert module.main(argv) == 1
    stdout = capsys.readouterr().out
    issue = json.loads(stdout)["errors"][0]
    assert (issue["code"], issue["stage"], issue["field"]) == (
        "EXPORT_IO_ERROR", "export", "publish.rename:attempts=6:errno=13:winerror=5")
    assert PRIVATE_ERROR not in stdout and str(out) not in stdout
    assert_clean(out)
