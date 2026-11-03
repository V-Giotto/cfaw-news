"""Explicit migration/rollback/restore, backup safety and untouched legacy rows."""

import json
import os
import sqlite3
import subprocess
import sys

import pytest
from cfaw_news.database import Article, ArticleReading, Database, Goal
from cfaw_news.intelligence.checkpoint import PersistenceError
from cfaw_news.intelligence.history_store import HistoryStore
from cfaw_news.intelligence.migrate import restore, sha
from cfaw_news.intelligence.persistence_migrate import maintain, paths_for, restore_with_epoch
from sqlalchemy import text

from .persistence_support import setup_store
from .test_history_db import append, head


def test_legacy_upgrade_backup_rollback_and_restored_epoch(tmp_path):
    path, anchor = tmp_path / "legacy.db", tmp_path / "anchor.json"
    db = Database("sqlite:///" + path.as_posix())
    db.create()
    with db.session.begin() as session:
        session.add(Goal(id="old-goal", data=dict(name="legacy")))
        session.add(Article(id="old", origin="feed", content_hash="legacy", data=dict(title="Current cache")))
        session.flush()
        session.add(ArticleReading(article_id="old", data=dict(text="Cache is never a historical evidence snapshot")))
    with db.session() as session:
        previous = session.execute(text("SELECT id,data FROM articles")).all()
    upgraded = maintain(path, anchor, "upgrade", backup=tmp_path / "before.db")
    assert upgraded["backup_verified_after_commit"]
    with db.session() as session:
        assert session.execute(text("SELECT id,data FROM articles")).all() == previous
        assert session.scalar(text("SELECT count(*) FROM g4_document_versions")) == 0
        assert session.scalar(text("SELECT count(*) FROM intelligence_entries")) == 0
    store = HistoryStore(db, anchor)
    append(store, head(store))
    rolled = maintain(path, anchor, "rollback", backup=tmp_path / "complete.db")
    assert rolled["backup_verified_after_commit"]
    with db.session() as session:
        assert session.execute(text("SELECT id,data FROM articles")).all() == previous
        assert session.scalar(text("SELECT count(*) FROM g4_document_versions")) == 0
        assert not session.scalar(text("SELECT name FROM sqlite_master WHERE name='intelligence_entries'"))
    restored, restored_anchor = tmp_path / "restored.db", tmp_path / "restored-anchor.json"
    result = restore_with_epoch(tmp_path / "complete.db", restored, restored_anchor,
                               expected_sha256=sha(tmp_path / "complete.db"), acknowledge_restore=True)
    assert result["continuity"] == "administrator_acknowledged_restore_epoch"
    copy = Database("sqlite:///" + restored.as_posix())
    assert head(HistoryStore(copy, restored_anchor)) == json.loads(anchor.read_bytes())["heads"]["real:local"]["sha256"]
    copy.engine.dispose()
    db.engine.dispose()


def test_independent_anchor_detects_whole_db_rollback_and_requires_new_epoch(tmp_path):
    db, store, path, anchor = setup_store(tmp_path)
    first = append(store, head(store))
    maintain(path, anchor, "backup", backup=tmp_path / "checkpoint.db")
    append(store, head(store), key="second")
    old_epoch = json.loads(anchor.read_bytes())["epoch"]
    restored = tmp_path / "older.db"
    restore(tmp_path / "checkpoint.db", restored, expected_sha256=sha(tmp_path / "checkpoint.db"))
    old_db = Database("sqlite:///" + restored.as_posix())
    with pytest.raises(PersistenceError, match="TRUSTED_HEAD_MISMATCH"):
        with HistoryStore(old_db, anchor).read():
            pass
    fresh = tmp_path / "acknowledged.db"
    new_anchor = tmp_path / "new-anchor.json"
    restore_with_epoch(tmp_path / "checkpoint.db", fresh, new_anchor,
                       expected_sha256=sha(tmp_path / "checkpoint.db"), acknowledge_restore=True)
    copied = Database("sqlite:///" + fresh.as_posix())
    renewed = HistoryStore(copied, new_anchor)
    assert json.loads(new_anchor.read_bytes())["epoch"] != old_epoch
    with pytest.raises(PersistenceError, match="RECOVERY_EPOCH_CONFLICT"):
        renewed.mutate("real:local", key="late-client", operation="bad", payload={}, expected_head=first["head"]["sha256"],
                      expected_epoch=old_epoch, apply=lambda *_: pytest.fail("stale epoch mutated data"))
    copied.engine.dispose()
    old_db.engine.dispose()
    db.engine.dispose()


@pytest.mark.parametrize("suffix", ["-journal", "-wal", "-shm"])
@pytest.mark.parametrize("product", ["backup", "anchor", "receipt"])
def test_reserved_paths_rejected_before_database_creation(tmp_path, suffix, product):
    database, anchor = tmp_path / "new.db", tmp_path / "head.json"
    backup, receipt = tmp_path / "copy.db", tmp_path / "receipt.json"
    if product == "backup":
        backup = type(database)(str(database) + suffix)
    elif product == "anchor":
        anchor = type(database)(str(database) + suffix)
    else:
        receipt = type(database)(str(database) + suffix)
    with pytest.raises(ValueError, match="PATH_"):
        paths_for(database, anchor, backup, receipt)
    assert not database.exists() and not receipt.exists()


def test_cli_receipt_collision_cannot_commit(tmp_path):
    database = tmp_path / "collision.db"
    process = subprocess.run([sys.executable, "-B", "-m", "cfaw_news.intelligence.persistence_migrate", "upgrade",
        "--database", str(database), "--anchor", str(tmp_path / "anchor.json"), "--receipt", str(database)],
        capture_output=True, text=True, env={**os.environ})
    assert process.returncode == 1 and not database.exists(), process.stdout + process.stderr
    assert json.loads(process.stdout)["database_state"] == "not_started"


def test_schema_transaction_rolls_back_failed_upgrade(tmp_path, monkeypatch):
    from cfaw_news.intelligence.persistence_migrate import MIGRATION
    original = MIGRATION.statements
    monkeypatch.setattr(MIGRATION, "statements", lambda: [original()[0], "INVALID SQL"])
    database = tmp_path / "failed.db"
    with pytest.raises(ValueError):
        maintain(database, tmp_path / "head.json", "upgrade")
    with sqlite3.connect(database) as connection:
        assert not connection.execute("SELECT name FROM sqlite_master WHERE name LIKE 'intelligence_%'").fetchall()
