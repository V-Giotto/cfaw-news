"""Real isolated SQLite files, explicit maintenance and exact legacy row preservation."""

import json
import os
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from cfaw_news.config import Settings
from cfaw_news.database import Article, ArticleReading, Database, Decision, Goal, Run, Schedule
from cfaw_news.intelligence.contracts import LedgerError, canonical
from cfaw_news.intelligence.document_store import DocumentLedger, enabled
from cfaw_news.intelligence.migrate import MIGRATION, maintain, restore, sha
from cfaw_news.intelligence.models import G4Base, G4Capture, G4Coverage, G4Version
from cfaw_news.main import create_app
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from .test_capture import ROOT, SOURCE, T0, T1, T2, article, policy, versions, write
from .test_capture import ledger_db as ledger_db


def legacy_snapshot(path):
    with sqlite3.connect(path) as c:
        names = [x[0] for x in c.execute("SELECT name FROM sqlite_master WHERE type='table' "
                                        "AND name NOT LIKE 'g4_%' ORDER BY name")]
        return {t: sorted(c.execute(f'SELECT * FROM "{t}"').fetchall(), key=repr) for t in names}


def old_database(path):
    db = Database("sqlite:///" + path.as_posix())
    db.create()
    with db.session.begin() as s:
        s.add(Goal(id="goal", data={"preserve": "goal"}))
        s.add(Article(id="old", content_hash="oldhash", origin="feed", data=dict(
            source_id="ithome", source_url="https://www.ithome.com/post/old",
            title="FORBIDDEN past title", summary="FORBIDDEN summary", paragraphs=[
                dict(id="p1", text="FORBIDDEN cached body")],
            captured_at="2020-01-01T00:00:00Z", published_at="2019-01-01T00:00:00Z")))
        s.flush()
        s.add(ArticleReading(article_id="old", data=dict(text="FORBIDDEN current web reading")))
        s.add(Run(id="run", goal_id="goal", goal_version=1, mode="baseline", status="completed",
                  snapshot={"preserve": "snapshot"}, result={"preserve": "result"}, basis_hash="basis"))
        s.flush()
        s.add(Decision(id="decision", run_id="run", goal_id="goal", goal_version=1,
                       basis_hash="basis", choice="approve", reason="explicit"))
        s.add(Schedule(id="schedule", proposal_key="proposal", run_id="run", title="keep",
                       content="keep", start=T1, end=T2, status="planned"))
    db.engine.dispose()
    return db


def test_new_database_migration_then_legacy_creation(tmp_path):
    p = tmp_path / "new.db"
    r = maintain(p, "upgrade")
    assert r["result"] == "upgraded"
    db = Database("sqlite:///" + p.as_posix())
    db.create()
    with db.session() as s:
        assert enabled(s) and s.get(Goal, "unknown") is None
    db.engine.dispose()


def test_upgrade_backup_and_rollback_preserve_legacy_tables_exactly(tmp_path):
    p = tmp_path / "old.db"
    old_database(p)
    before = legacy_snapshot(p)
    r = maintain(p, "upgrade", backup=tmp_path / "pre-upgrade.db")
    assert r["backup"]["backup_sha256"] == sha(tmp_path / "pre-upgrade.db")
    assert legacy_snapshot(p) == before
    assert maintain(p, "upgrade", backup=tmp_path / "pre-noop.db")["result"] == "already_current"
    assert legacy_snapshot(p) == before
    r = maintain(p, "rollback", backup=tmp_path / "pre-rollback.db")
    assert r["result"] == "g4_tables_removed_legacy_untouched"
    assert legacy_snapshot(p) == before
    with sqlite3.connect(p) as c:
        assert not c.execute("SELECT name FROM sqlite_master WHERE name LIKE 'g4_%'").fetchall()


def test_old_db_requires_explicit_backup_and_never_overwrites_backup(tmp_path):
    p = tmp_path / "old.db"
    old_database(p)
    with pytest.raises(LedgerError, match="G4_BACKUP_REQUIRED"):
        maintain(p, "upgrade")
    b = tmp_path / "backup.db"
    maintain(p, "upgrade", backup=b)
    pin = sha(b)
    with pytest.raises(LedgerError, match="G4_BACKUP_TARGET_EXISTS"):
        maintain(p, "backup", backup=b)
    assert sha(b) == pin


def test_ddl_failure_rolls_back_every_created_table(tmp_path, monkeypatch):
    p = tmp_path / "old.db"
    old_database(p)
    before = legacy_snapshot(p)
    original = MIGRATION.statements()
    monkeypatch.setattr(MIGRATION, "statements", lambda: original + ["INVALID SQL FAULT"])
    with pytest.raises(SQLAlchemyError):
        maintain(p, "upgrade", backup=tmp_path / "fault-backup.db")
    assert legacy_snapshot(p) == before
    with sqlite3.connect(p) as c:
        assert not c.execute("SELECT name FROM sqlite_master WHERE name LIKE 'g4_%'").fetchall()


def test_partial_migration_is_rejected_not_treated_as_disabled(tmp_path):
    p = tmp_path / "partial.db"
    with sqlite3.connect(p) as c:
        c.execute("CREATE TABLE g4_documents (document_id TEXT)")
    with pytest.raises(LedgerError, match="G4_MIGRATION_INCOMPLETE"):
        maintain(p, "upgrade", backup=tmp_path / "partial-backup.db")
    db = Database("sqlite:///" + p.as_posix())
    with db.session() as s, pytest.raises(LedgerError, match="G4_MIGRATION_INCOMPLETE"):
        enabled(s)
    db.engine.dispose()


def test_wal_backup_includes_committed_wal_and_restore_is_pin_checked(tmp_path):
    p, b = tmp_path / "wal.db", tmp_path / "wal-backup.db"
    connection = sqlite3.connect(p)
    try:
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("CREATE TABLE preserved (value TEXT)")
        connection.execute("INSERT INTO preserved VALUES ('committed WAL only')")
        connection.commit()
        assert Path(str(p) + "-wal").stat().st_size > 0
        maintain(p, "backup", backup=b)
        restored = tmp_path / "restored.db"
        with pytest.raises(LedgerError, match="G4_BACKUP_PIN_MISMATCH"):
            restore(b, restored, expected_sha256="0" * 64)
        assert not restored.exists()
        restore(b, restored, expected_sha256=sha(b))
        assert legacy_snapshot(restored) == legacy_snapshot(p)
        with pytest.raises(LedgerError, match="G4_RESTORE_TARGET_EXISTS"):
            restore(b, restored, expected_sha256=sha(b))
    finally:
        connection.close()


def test_backfill_is_current_metadata_only_and_idempotent(tmp_path):
    p = tmp_path / "old.db"
    db = old_database(p)
    before = legacy_snapshot(p)
    maintain(p, "upgrade", backup=tmp_path / "pre-upgrade.db")
    result = maintain(p, "backfill", backup=tmp_path / "pre-backfill.db", root=ROOT)
    assert result["backfill"]["created"] == 1
    value = versions(db)[0]
    assert value.provenance == "legacy_cache_metadata_observed_now"
    assert value.observed_at == value.available_at == result["backfill"]["observed_at"]
    assert value.observed_at > T2 and value.published_at < T0
    assert "FORBIDDEN" not in value.model_dump_json()
    assert value.rights == "unknown" and value.retention == "metadata_only"
    with db.session() as s:
        assert list(s.scalars(select(G4Capture))) == []  # Backfill is no successful RSS poll.
        assert list(s.scalars(select(G4Coverage))) == []
    again = maintain(p, "backfill", backup=tmp_path / "pre-second-backfill.db", root=ROOT)
    assert again["backfill"]["created"] == 0 and again["backfill"]["already_present"] == 1
    assert legacy_snapshot(p) == before and len(versions(db)) == 1
    db.engine.dispose()


def test_rollback_then_restore_preserves_exact_versions(ledger_db, tmp_path):
    a = write(ledger_db)
    b = write(ledger_db, article("new"), stamp=T2)
    ledger_db.engine.dispose()
    p = Path(ledger_db.engine.url.database)
    backup = tmp_path / "pre-removal.db"
    maintain(p, "rollback", backup=backup)
    target = tmp_path / "recovered.db"
    r = restore(backup, target, expected_sha256=sha(backup))
    restored = Database("sqlite:///" + target.as_posix())
    assert versions(restored) == [a, b]
    assert "restore_epoch" in r["continuity"]
    with restored.session() as s:
        assert enabled(s)
    restored.engine.dispose()


def test_rights_policy_change_creates_new_immutable_version(ledger_db, tmp_path):
    ledger = DocumentLedger(tmp_path)
    with ledger_db.session.begin() as s:
        ledger.record_poll(s, SOURCE, [article()], started_at=T0, observed_at=T1, available_at=T1)
    before = versions(ledger_db)[0]
    registry = tmp_path / "data/g4_source_policies.json"
    registry.parent.mkdir()
    approved = policy("excerpt_only")
    registry.write_bytes(canonical(dict(schema_revision="g4-source-registry-v1",
                                       sources=[approved.model_dump(mode="json")])))
    with ledger_db.session.begin() as s:
        assert not ledger.has_snapshot(s, SOURCE)
        ledger.record_poll(s, SOURCE, [article()], started_at=T2, observed_at=T2, available_at=T2)
    after = versions(ledger_db)[1]
    assert before.retention == "metadata_only" and after.retention == "excerpt"
    assert after.supersedes_version_id == before.doc_version_id
    assert after.source_policy_sha256 != before.source_policy_sha256
    assert versions(ledger_db)[0] == before


def test_schema_export_and_exact_check(tmp_path):
    from cfaw_news.intelligence.schema import MODELS
    folder = ROOT / "evals/intelligence_g4/schema/pr2"
    for model in MODELS:
        assert (folder / (model.__name__ + ".schema.json")).read_bytes() == (
            canonical(model.model_json_schema()) + b"\n")


def test_migration_cli_real_receipts_and_nonzero_restore_refusal(tmp_path):
    p = tmp_path / "cli.db"
    env = {**os.environ, "PYTHONPATH": str(ROOT / "backend"), "PYTHONDONTWRITEBYTECODE": "1"}
    receipt = tmp_path / "upgrade.json"
    cmd = [sys.executable, "-B", "-m", "cfaw_news.intelligence.migrate", "upgrade",
           "--database", str(p), "--receipt", str(receipt)]
    result = subprocess.run(cmd, env=env, cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(receipt.read_bytes())["status"] == "PASS"
    failed = tmp_path / "refusal.json"
    result = subprocess.run([*cmd[:4], "restore", "--database", str(p), "--backup", str(p),
        "--backup-pin", sha(p), "--receipt", str(failed)], env=env, cwd=ROOT,
        capture_output=True, text=True)
    assert result.returncode == 1
    assert json.loads(failed.read_bytes())["error_code"] == "G4_RESTORE_TARGET_EXISTS"


def test_separate_g4_metadata_cannot_implicitly_upgrade_legacy():
    from cfaw_news.database import Base
    assert set(Base.metadata.tables).isdisjoint(G4Base.metadata.tables)


def test_missing_rights_never_reuses_article_reading_as_native_content(ledger_db):
    write(ledger_db, rights="unknown")
    with ledger_db.session() as s:
        row = s.scalar(select(G4Version))
        assert row.data["content"]["paragraphs"] == []
        assert row.data["content"]["text_excerpt"] is None


def test_removed_immutability_trigger_is_detected(ledger_db):
    with ledger_db.engine.begin() as c:
        c.exec_driver_sql("DROP TRIGGER g4_document_versions_no_update")
    with ledger_db.session() as s, pytest.raises(LedgerError, match="G4_MIGRATION_SCHEMA_MISMATCH"):
        enabled(s)


def test_migrated_app_legacy_library_run_approval_schedule_restart(tmp_path):
    path = tmp_path / "migrated-app.db"
    maintain(path, "upgrade")
    settings = Settings(_env_file=None, database_url="sqlite:///" + path.as_posix(), root=ROOT,
        demo_seed=True, archive_seed=True, llm_mode="baseline", news_auto_refresh=False,
        news_media_fetch=False, news_reading_fetch=False)
    with TestClient(create_app(settings)) as client:
        assert client.get("/api/health").status_code == 200
        articles = client.get("/api/articles?limit=2").json()
        assert len(articles) == 2 and all("paragraphs" in a for a in articles)
        goal = client.get("/api/goals").json()[0]
        response = client.post(f"/api/goals/{goal['id']}/checks",
                               json=dict(expected_version=goal["version"]))
        assert response.status_code == 202
        run_id = response.json()["id"]
        for _ in range(200):
            run = client.get(f"/api/runs/{run_id}").json()
            if run["status"] not in {"queued", "running"}:
                break
            time.sleep(0.01)
        assert run["status"] == "completed" and run["result"]["outcome"] == "needs_review"
        start = (datetime.now(timezone.utc) + timedelta(days=2)).replace(second=0, microsecond=0)
        end = start + timedelta(minutes=run["result"]["proposal"]["duration_minutes"])
        body = dict(start=start.isoformat(), end=end.isoformat())
        first = client.post(f"/api/runs/{run_id}/approve", json=body)
        second = client.post(f"/api/runs/{run_id}/approve", json=body)
        assert first.status_code == second.status_code == 200
        assert first.json()["created"] and not second.json()["created"]
        schedule_id = first.json()["schedule"]["id"]
        with client.app.state.database.session() as s:
            assert enabled(s) and list(s.scalars(select(G4Version))) == []
    with TestClient(create_app(settings)) as client:
        assert client.get(f"/api/runs/{run_id}").json()["snapshot"] == run["snapshot"]
        assert any(s["id"] == schedule_id for s in client.get("/api/schedules").json())
        assert client.get("/api/articles?limit=2").json() == articles


def test_invalid_legacy_metadata_skip_rolls_back_per_document(tmp_path):
    path = tmp_path / "invalid-legacy.db"
    db = old_database(path)
    with db.session.begin() as s:
        row = s.get(Article, "old")
        row.data = {**row.data, "published_at": "not a timestamp"}
    db.engine.dispose()
    before = legacy_snapshot(path)
    maintain(path, "upgrade", backup=tmp_path / "pre-upgrade.db")
    result = maintain(path, "backfill", backup=tmp_path / "pre-invalid-backfill.db", root=ROOT)
    assert result["backfill"]["skipped"] == 1 and result["backfill"]["created"] == 0
    assert legacy_snapshot(path) == before
    with db.session() as s:
        assert list(s.scalars(select(G4Version))) == []
        assert s.connection().exec_driver_sql("SELECT count(*) FROM g4_documents").scalar() == 0
        assert s.connection().exec_driver_sql("SELECT count(*) FROM g4_source_policies").scalar() == 0
    db.engine.dispose()
