"""Offline restore inputs and exact approval retries remain stable at boundaries."""

import importlib.util
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from cfaw_news.intelligence.contracts import LedgerError
from cfaw_news.intelligence.migrate import restore, sha
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[3]


def offline_wal(folder):
    folder.mkdir()
    path = folder / "backup.db"
    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("CREATE TABLE preserved(value TEXT)")
        connection.execute("INSERT INTO preserved VALUES ('pinned offline bytes')")
        connection.commit()
    connection.close()
    assert not Path(str(path) + "-wal").exists()
    return path


def inventory(folder):
    return {p.name: (p.stat().st_size, p.stat().st_mtime_ns, sha(p)) for p in folder.iterdir() if p.is_file()}


def test_offline_wal_restore_preserves_entire_input_directory(tmp_path):
    source = offline_wal(tmp_path / "input")
    before = inventory(source.parent)
    target = tmp_path / "output/restored.db"
    restore(source, target, expected_sha256=sha(source))
    assert inventory(source.parent) == before
    with sqlite3.connect(target) as restored:
        assert restored.execute("SELECT value FROM preserved").fetchall() == [("pinned offline bytes",)]


def test_sqlite_opens_only_isolated_restore_input(tmp_path, monkeypatch):
    source = offline_wal(tmp_path / "input")
    connect, opened = sqlite3.connect, []

    def guarded(database, *args, **kwargs):
        assert source.as_uri() not in str(database)
        opened.append(str(database))
        return connect(database, *args, **kwargs)

    monkeypatch.setattr(sqlite3, "connect", guarded)
    target = tmp_path / "output/restored.db"
    restore(source, target, expected_sha256=sha(source))
    assert opened and inventory(source.parent).keys() == {"backup.db"}


@pytest.mark.parametrize("suffix", ["-wal", "-journal"])
def test_restore_rejects_unpinned_nonempty_sidecar(tmp_path, suffix):
    source = offline_wal(tmp_path / "input")
    Path(str(source) + suffix).write_bytes(b"not part of pinned offline backup")
    before = inventory(source.parent)
    target = tmp_path / "output/restored.db"
    with pytest.raises(LedgerError, match="G4_BACKUP_NOT_SELF_CONTAINED"):
        restore(source, target, expected_sha256=sha(source))
    assert not target.exists() and inventory(source.parent) == before


def test_proof_reader_preserves_input_namespace(tmp_path):
    from audit.g4.h09.proof import readonly
    source = offline_wal(tmp_path / "input")
    before = inventory(source.parent)
    with readonly(source) as conn:
        assert conn.execute("SELECT value FROM preserved").fetchone()[0] == "pinned offline bytes"
    assert inventory(source.parent) == before


def test_retired_schedule_exact_retry_across_minute_uses_original_payload(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("workflow_boundary_regression", ROOT / "tests/test_workflow.py")
    workflow = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(workflow)
    payloads = []

    class Clock:
        current = datetime.now(timezone.utc).replace(second=59, microsecond=999999)
        calls = 0

        @classmethod
        def now(cls, zone):
            cls.calls += 1
            return cls.current.astimezone(zone)

    class TrackedClient(TestClient):
        def post(self, url, **kwargs):
            if str(url).endswith("/approve"):
                payloads.append(dict(kwargs["json"]))
            result = super().post(url, **kwargs)
            if str(url).endswith("/approve") and len(payloads) == 1:
                assert result.status_code == 200
                Clock.current += timedelta(microseconds=2)
            return result

    monkeypatch.setattr(workflow, "datetime", Clock)
    monkeypatch.setattr(workflow, "TestClient", TrackedClient)
    settings = workflow.settings.__wrapped__(tmp_path)
    workflow.test_retire_demo_news_keeps_feed_history_and_user_records(settings)
    assert len(payloads) == 3 and payloads == [payloads[0]] * 3
    assert Clock.calls == 1


@pytest.mark.parametrize("damage", ["missing", "duplicate", "foreign", "source"])
def test_amended_inventory_keeps_strict_node_and_source_validation(damage):
    import copy

    from audit.g4.h09_review.test_control import required, verify_inventory

    value = required()
    inventory = dict(nodes=value["nodes"][:], test_source_sha256=copy.deepcopy(value["test_source_sha256"]))
    assert verify_inventory(inventory) == value
    if damage == "missing":
        inventory["nodes"].pop()
    elif damage == "duplicate":
        inventory["nodes"].append(inventory["nodes"][0])
    elif damage == "foreign":
        inventory["nodes"][-1] = "tests/unregistered.py::test_fabricated"
    else:
        inventory["test_source_sha256"]["tests/test_workflow.py"] = "0" * 64
    with pytest.raises(AssertionError):
        verify_inventory(inventory)


def test_amendment_does_not_change_frozen_nodes_or_skip_exemptions():
    from audit.g4.h09_review.test_control import ORIGINAL_REQUIREMENTS, required

    original, current = ORIGINAL_REQUIREMENTS(), required()
    assert original["nodes"] == current["nodes"]
    assert original["skip_exemptions"] == current["skip_exemptions"]
    assert {n for n in original["test_source_sha256"]
            if original["test_source_sha256"][n] != current["test_source_sha256"][n]} == {"tests/test_workflow.py"}
