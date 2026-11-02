"""PR2 review regressions: reserved paths, artifact aliases and durable receipts."""

import importlib
import json
import os
import sqlite3
import subprocess
import sys
from contextlib import closing
from pathlib import Path

import pytest
from cfaw_news.intelligence import migrate
from cfaw_news.intelligence.contracts import LedgerError
from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

ROOT = Path(__file__).resolve().parents[3]


def tables(path):
    with closing(sqlite3.connect(path)) as connection:
        return connection.execute("SELECT name FROM sqlite_master WHERE type='table' "
                                  "ORDER BY name").fetchall()


def fixture_db(folder, mode="DELETE"):
    db = folder / "source.db"
    migrate.maintain(db, "upgrade")
    with closing(sqlite3.connect(db)) as connection:
        assert connection.execute("PRAGMA journal_mode=" + mode).fetchone()[0] == mode.lower()
        connection.execute("CREATE TABLE legacy_preserved(value TEXT)")
        connection.execute("INSERT INTO legacy_preserved VALUES ('authored fixture')")
        connection.commit()
    return db


def cli(action, database, receipt, *extra):
    return subprocess.run([sys.executable, "-B", "-m", "cfaw_news.intelligence.migrate", action,
        "--database", str(database), "--receipt", str(receipt), *map(str, extra)], cwd=ROOT,
        env={**os.environ, "PYTHONPATH": str(ROOT / "backend"), "PYTHONDONTWRITEBYTECODE": "1"},
        capture_output=True, text=True)


@pytest.mark.parametrize("mode", ["DELETE", "WAL"])
@pytest.mark.parametrize("suffix", ["-journal", "-wal", "-shm", "-mj123456789"])
def test_api_reserved_backup_rejected_before_rollback(tmp_path, mode, suffix):
    db = fixture_db(tmp_path, mode)
    before = tables(db)
    backup = Path(str(db) + suffix)
    with pytest.raises(LedgerError, match="G4_PATH_RESERVED"):
        migrate.maintain(db, "rollback", backup=backup)
    assert tables(db) == before
    assert not Path(str(backup) + ".manifest.json").exists()


@pytest.mark.parametrize("mode", ["DELETE", "WAL"])
@pytest.mark.parametrize("suffix", ["-journal", "-wal", "-shm"])
def test_cli_reserved_backup_has_structured_refusal(tmp_path, mode, suffix):
    db = fixture_db(tmp_path, mode)
    before = tables(db)
    receipt = tmp_path / "refusal.json"
    result = cli("rollback", db, receipt, "--backup", str(db) + suffix)
    assert result.returncode == 1, result.stdout + result.stderr
    value = json.loads(result.stdout)
    assert value["error_code"] == "G4_PATH_RESERVED"
    assert value["database_state"] == "not_started"
    assert json.loads(receipt.read_bytes())["status"] == "FAIL"
    assert tables(db) == before


@pytest.mark.parametrize("alias", ["same", "dotdot"])
def test_new_database_receipt_alias_rejected_before_create(tmp_path, alias):
    db = tmp_path / "new.db"
    receipt = db if alias == "same" else tmp_path / "unused" / ".." / db.name
    result = cli("upgrade", db, receipt)
    assert result.returncode == 1
    value = json.loads(result.stdout)
    assert value["error_code"] == "G4_PATH_CONFLICT" and value["database_state"] == "not_started"
    assert not db.exists() and "Traceback" not in result.stderr


@pytest.mark.parametrize("kind", ["backup", "manifest", "database_sidecar", "backup_sidecar",
                                   "receipt_staging", "sidecar_parent"])
def test_all_receipt_artifact_collisions_refuse_before_mutation(tmp_path, kind):
    db, backup = tmp_path / "new.db", tmp_path / "backup.db"
    receipt = {"backup": backup, "manifest": Path(str(backup) + ".manifest.json"),
        "database_sidecar": Path(str(db) + "-journal"),
        "backup_sidecar": Path(str(backup) + "-journal"),
        "receipt_staging": tmp_path / "receipt.json",
        "sidecar_parent": Path(str(db) + "-journal") / "receipt.json"}[kind]
    if kind == "receipt_staging":
        db = Path(str(receipt) + ".pending")
    result = cli("upgrade", db, receipt, "--backup", backup)
    assert result.returncode == 1
    assert json.loads(result.stdout)["database_state"] == "not_started"
    assert not db.exists() and not backup.exists() and not receipt.exists()


def test_backup_manifest_cannot_alias_database(tmp_path):
    backup = tmp_path / "name"
    db = Path(str(backup) + ".manifest.json")
    migrate.maintain(db, "upgrade")
    before = tables(db)
    with pytest.raises(LedgerError, match="G4_PATH_CONFLICT"):
        migrate.maintain(db, "rollback", backup=backup)
    assert tables(db) == before and not backup.exists()


def test_existing_hardlink_alias_rejected(tmp_path):
    db = fixture_db(tmp_path)
    alias = tmp_path / "hardlink.db"
    os.link(db, alias)
    before = tables(db)
    with pytest.raises(LedgerError, match="G4_PATH_CONFLICT"):
        migrate.maintain(db, "rollback", backup=alias)
    assert tables(db) == before


def test_receipt_parent_not_writable_refuses_before_database(tmp_path):
    parent = tmp_path / "not-a-directory"
    parent.write_text("preserve", encoding="utf-8")
    db = tmp_path / "new.db"
    result = cli("upgrade", db, parent / "receipt.json")
    assert result.returncode == 1
    assert json.loads(result.stdout)["database_state"] == "not_started"
    assert not db.exists() and parent.read_text(encoding="utf-8") == "preserve"


@pytest.mark.parametrize("side", ["source", "target"])
def test_restore_sidecar_namespace_rejected(tmp_path, side):
    backup = fixture_db(tmp_path)
    target = tmp_path / "new.db"
    if side == "source":
        invalid_backup = Path(str(target) + "-journal")
        invalid_backup.write_bytes(backup.read_bytes())
        backup = invalid_backup
    else:
        target = Path(str(backup) + "-journal")
    with pytest.raises(LedgerError, match="G4_PATH_RESERVED"):
        migrate.restore(backup, target, expected_sha256=migrate.sha(backup))
    assert not target.exists()


def test_direct_backup_helper_cannot_bypass_reserved_guard(tmp_path):
    db = fixture_db(tmp_path)
    with pytest.raises(LedgerError, match="G4_PATH_RESERVED"):
        migrate.backup_locked(db, str(db) + "-journal")


@pytest.mark.parametrize("mode", ["DELETE", "WAL"])
def test_valid_backup_survives_commit_and_restores(tmp_path, mode):
    db = fixture_db(tmp_path, mode)
    before = tables(db)
    backup, receipt = tmp_path / "safe-backup.db", tmp_path / "receipt.json"
    result = cli("rollback", db, receipt, "--backup", backup)
    assert result.returncode == 0, result.stdout + result.stderr
    value = json.loads(receipt.read_bytes())
    assert value["database_state"] == "committed" and value["backup_verified_after_commit"]
    assert migrate.sha(backup) == value["backup"]["backup_sha256"]
    assert json.loads(Path(str(backup) + ".manifest.json").read_bytes()) == value["backup"]
    target = tmp_path / "restored.db"
    migrate.restore(backup, target, expected_sha256=value["backup"]["backup_sha256"])
    assert tables(target) == before
    assert not Path(str(receipt) + ".pending").exists()


@pytest.mark.parametrize("fault", ["remove", "change"])
def test_postcommit_backup_loss_is_explicit_not_success(tmp_path, fault):
    db = fixture_db(tmp_path)
    backup = tmp_path / "removed-at-commit.db"
    def remove_backup(connection):
        if Path(connection.engine.url.database) == db and backup.exists():
            if fault == "remove":
                backup.unlink()
            else:
                with backup.open("ab") as stream:
                    stream.write(b"authored SHA mismatch")
    event.listen(Engine, "commit", remove_backup)
    try:
        with pytest.raises(LedgerError, match="G4_BACKUP_POSTCOMMIT_INVALID") as caught:
            migrate.maintain(db, "rollback", backup=backup)
    finally:
        event.remove(Engine, "commit", remove_backup)
    assert caught.value.database_state == "committed"
    assert tables(db) == [("legacy_preserved",)]


@pytest.mark.parametrize("failure", ["write", "replace"])
def test_postcommit_receipt_failure_is_committed_and_prepared_record_survives(
        tmp_path, monkeypatch, capsys, failure):
    io = importlib.import_module("cfaw_news.intelligence.maintenance_io")
    db, receipt = tmp_path / "new.db", tmp_path / "receipt.json"
    monkeypatch.setattr(sys, "argv", ["migrate", "upgrade", "--database", str(db),
                                      "--receipt", str(receipt)])
    if failure == "write":
        original = io.write_synced
        def fail_final(stream, value):
            if value["status"] == "PASS":
                raise OSError("authored final receipt write failure")
            return original(stream, value)
        monkeypatch.setattr(io, "write_synced", fail_final)
    else:
        def fail_replace(*_):
            raise OSError("authored atomic replace failure")
        monkeypatch.setattr(io.os, "replace", fail_replace)
    assert migrate.main() == 2
    value = json.loads(capsys.readouterr().out)
    assert value["status"] == "COMMITTED_RECEIPT_FAILED" and value["database_state"] == "committed"
    assert value["receipt_written"] is False
    assert len(tables(db)) == 7
    assert json.loads(receipt.read_bytes())["status"] == "PREPARED"
    if failure == "replace":
        assert json.loads(Path(str(receipt) + ".pending").read_bytes())["status"] == "PASS"


def test_prepared_receipt_sync_failure_never_starts_database(tmp_path, monkeypatch, capsys):
    io = importlib.import_module("cfaw_news.intelligence.maintenance_io")
    db, receipt = tmp_path / "new.db", tmp_path / "receipt.json"
    monkeypatch.setattr(sys, "argv", ["migrate", "upgrade", "--database", str(db),
                                      "--receipt", str(receipt)])
    def fail(*_):
        raise OSError("authored fsync failure")
    monkeypatch.setattr(io, "write_synced", fail)
    assert migrate.main() == 1
    assert json.loads(capsys.readouterr().out)["database_state"] == "not_started"
    assert not db.exists()


def test_commit_exception_reports_unknown_outcome(tmp_path, monkeypatch, capsys):
    db, receipt = tmp_path / "new.db", tmp_path / "receipt.json"
    monkeypatch.setattr(sys, "argv", ["migrate", "upgrade", "--database", str(db),
                                      "--receipt", str(receipt)])
    def fail_commit(connection):
        if Path(connection.engine.url.database) == db:
            raise SQLAlchemyError("authored commit boundary failure")
    event.listen(Engine, "commit", fail_commit)
    try:
        assert migrate.main() == 1
    finally:
        event.remove(Engine, "commit", fail_commit)
    value = json.loads(capsys.readouterr().out)
    assert value["database_state"] == "unknown"
    assert value["error_code"] == "G4_COMMIT_OUTCOME_UNKNOWN"
    assert json.loads(receipt.read_bytes()) == value


@pytest.mark.skipif(os.name != "nt", reason="Win32 filename alias semantics")
@pytest.mark.parametrize("suffix", [":stream", ".", " "])
def test_windows_receipt_filename_aliases_are_rejected(tmp_path, suffix):
    db = tmp_path / "new.db"
    result = cli("upgrade", db, str(db) + suffix)
    assert result.returncode == 1
    value = json.loads(result.stdout)
    assert value["error_code"] == "G4_PATH_INVALID"
    assert value["database_state"] == "not_started" and not db.exists()


def test_valid_literal_filenames_and_same_basename_in_other_directory(tmp_path):
    name = "literal # % space.db"
    db = tmp_path / name
    migrate.maintain(db, "upgrade")
    other = tmp_path / "backup-directory" / name
    result = migrate.maintain(db, "rollback", backup=other)
    assert result["backup_verified_after_commit"] and other.is_file()
    assert len(tables(other)) == 7 and tables(db) == []
