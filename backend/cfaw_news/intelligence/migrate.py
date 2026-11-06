"""Explicit SQLite upgrade/backfill/rollback and WAL-consistent backup/restore CLI.

Stop the application before maintenance. No default database path, no in-place restore.
"""

import argparse
import hashlib
import importlib
import json
import os
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from pydantic import ValidationError
from sqlalchemy import create_engine, select
from sqlalchemy.engine import URL
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ..database import Article
from .contracts import LedgerError, SourcePolicy, instant, safe_url
from .document_store import capture_version
from .maintenance_io import (
    SIDECARS,
    MaintenanceFailure,
    Receipt,
    resolve_paths,
    validate_paths,
    write_synced,
)
from .models import G4Base, G4Document
from .sqlite_input import isolated_sqlite_input

MIGRATION = importlib.import_module(".migrations.001_g4_documents", __package__)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def utcnow():
    return instant(datetime.now(timezone.utc).isoformat())


def table_names(connection):
    return set(connection.exec_driver_sql(
        "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'g4_%'").scalars())


def check_installed(connection):
    if table_names(connection) != set(G4Base.metadata.tables):
        raise LedgerError("G4_MIGRATION_INCOMPLETE")
    rows = connection.exec_driver_sql(
        "SELECT revision,source_sha256,schema_sha256 FROM g4_migrations").all()
    if rows != [(MIGRATION.REVISION, MIGRATION.source_sha256(), MIGRATION.schema_sha256())]:
        raise LedgerError("G4_MIGRATION_PIN_MISMATCH")
    if connection.exec_driver_sql(MIGRATION.SCHEMA_QUERY).all() != (
            MIGRATION.expected_schema_rows(MIGRATION.source_sha256())):
        raise LedgerError("G4_MIGRATION_SCHEMA_MISMATCH")


def backup_locked(database, destination):
    """Caller holds SQLite write reservation. A second reader includes committed WAL pages."""
    paths = validate_paths(resolve_paths(database, destination))
    database, target, manifest = paths.database, paths.backup, paths.manifest
    if target.exists() or manifest.exists():
        raise LedgerError("G4_BACKUP_TARGET_EXISTS")
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("xb"):
        pass  # Reserve a fresh destination before SQLite opens it.
    with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True, timeout=15)) as source:
        with closing(sqlite3.connect(target)) as dest:
            source.backup(dest)
            if dest.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
                raise LedgerError("G4_BACKUP_INTEGRITY_FAILED")
    record = dict(revision="g4-sqlite-backup-v1", backup_sha256=sha(target),
                  created_at=utcnow(), database_name=database.name)
    with target.open("r+b") as stream:
        os.fsync(stream.fileno())
    with manifest.open("x+b") as stream:
        write_synced(stream, record)
    verify_backup(paths, record)
    return record


def verify_backup(paths, record):
    if (not paths.backup.is_file() or sha(paths.backup) != record["backup_sha256"]
            or not paths.manifest.is_file() or json.loads(paths.manifest.read_bytes()) != record):
        raise LedgerError("G4_BACKUP_VERIFICATION_FAILED")


def maintain(database, action, *, backup=None, root=None):
    paths = validate_paths(resolve_paths(database, backup))
    path, backup = paths.database, paths.backup
    existed = path.exists() and path.stat().st_size > 0
    if existed and backup is None:
        raise MaintenanceFailure("G4_BACKUP_REQUIRED")
    if action not in {"upgrade", "backup", "rollback", "backfill"}:
        raise MaintenanceFailure("G4_MIGRATION_ACTION_INVALID")
    if action != "upgrade" and not existed:
        raise MaintenanceFailure("G4_DATABASE_NOT_FOUND")
    if backup is not None and (backup.exists() or paths.manifest.exists()):
        raise MaintenanceFailure("G4_BACKUP_TARGET_EXISTS")
    path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(URL.create("sqlite", database=path.as_posix()),
                           connect_args={"timeout": 15})
    receipt = dict(action=action, started_at=utcnow(), migration=MIGRATION.REVISION,
                   migration_sha256=MIGRATION.source_sha256(), schema_sha256=MIGRATION.schema_sha256())
    try:
        with engine.connect() as connection:
            connection.exec_driver_sql("PRAGMA foreign_keys=ON")
            connection.exec_driver_sql("BEGIN IMMEDIATE")
            if connection.exec_driver_sql("PRAGMA integrity_check").all() != [("ok",)]:
                raise LedgerError("G4_DATABASE_INTEGRITY_FAILED")
            if backup is not None:
                receipt["backup"] = backup_locked(path, backup)
            names = table_names(connection)
            if action == "upgrade":
                if names:
                    check_installed(connection)
                    receipt["result"] = "already_current"
                else:
                    for statement in MIGRATION.statements():
                        connection.exec_driver_sql(statement)
                    connection.exec_driver_sql("INSERT INTO g4_migrations VALUES (?,?,?,?)", (
                        MIGRATION.REVISION, MIGRATION.source_sha256(), MIGRATION.schema_sha256(),
                        utcnow()))
                    receipt["result"] = "upgraded"
            elif action == "rollback":
                check_installed(connection)
                connection.exec_driver_sql("PRAGMA defer_foreign_keys=ON")
                for table in reversed(G4Base.metadata.sorted_tables):
                    connection.exec_driver_sql(f'DROP TABLE "{table.name}"')
                receipt["result"] = "g4_tables_removed_legacy_untouched"
            elif action == "backfill":
                check_installed(connection)
                if root is None:
                    raise LedgerError("G4_BACKFILL_ROOT_REQUIRED")
                with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
                    receipt["backfill"] = backfill(session, Path(root), utcnow())
                    session.commit()  # Savepoint only; outer migration lock/transaction owns commit.
                receipt["result"] = "metadata_only_backfill"
            else:
                receipt["result"] = "backed_up"
            if connection.exec_driver_sql("PRAGMA foreign_key_check").all():
                raise LedgerError("G4_DATABASE_FOREIGN_KEY_FAILED")
            try:
                connection.commit()
            except (OSError, sqlite3.Error, SQLAlchemyError):
                raise MaintenanceFailure("G4_COMMIT_OUTCOME_UNKNOWN", database_state="unknown",
                                         operation=receipt) from None
    finally:
        engine.dispose()
    if backup is not None:
        try:
            verify_backup(paths, receipt["backup"])
        except (OSError, ValueError, LedgerError):
            raise MaintenanceFailure("G4_BACKUP_POSTCOMMIT_INVALID", database_state="committed",
                                     operation=receipt) from None
        receipt["backup_verified_after_commit"] = True
    try:
        receipt.update(finished_at=utcnow(), database_sha256=sha(path), database_state="committed")
    except OSError:
        raise MaintenanceFailure("G4_POSTCOMMIT_VERIFICATION_FAILED", database_state="committed",
                                 operation=receipt) from None
    return receipt


def backfill(session, root, now):
    from ..ingestion import catalog
    sources = {s["id"]: s for s in catalog(root)["sources"]}
    exists = session.scalar(select(Article.id).limit(1)) if session.connection().exec_driver_sql(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='articles'").first() else None
    result = dict(created=0, already_present=0, skipped=0, observed_at=now,
                  provenance="legacy_cache_metadata_observed_now", historical_bodies_imported=0)
    if exists is None:
        return result
    for row in session.scalars(select(Article).where(Article.origin == "feed")):
        data = row.data
        source_id, url = data.get("source_id"), data.get("source_url")
        try:
            url = safe_url(url)
            if not isinstance(source_id, str) or not source_id:
                raise LedgerError("G4_CAPTURE_SOURCE_MISSING")
            source = sources.get(source_id)
            policy = SourcePolicy(source_id=source_id,
                source_url=safe_url(source["url"] if source else url.replace("http:", "https:"),
                                    https=True),
                source_label=(source["label"] if source else "Legacy source")[:512])
            from .contracts import digest
            key = "g4doc:" + digest([source_id, url])
            if session.get(G4Document, key) is not None:
                result["already_present"] += 1
                continue
            # No title/summary/paragraphs/ArticleReading access. Only safe current metadata.
            with session.begin_nested():
                capture_version(session, dict(id=row.id, source_url=url,
                    published_at=data.get("published_at")), policy, observed_at=now, available_at=now,
                    legacy=True)
            result["created"] += 1
        except (LedgerError, ValidationError):
            # Invalid metadata is counted; no payload, URL or title in maintenance logs.
            result["skipped"] += 1
    return result


def restore(backup, database, *, expected_sha256):
    source, target = Path(backup).resolve(), Path(database).resolve()
    if target.exists():
        raise MaintenanceFailure("G4_RESTORE_TARGET_EXISTS")
    paths = validate_paths(resolve_paths(target, source))
    target, source = paths.database, paths.backup
    if any(Path(str(target) + suffix).exists() for suffix in SIDECARS):
        raise MaintenanceFailure("G4_RESTORE_TARGET_EXISTS")
    if sha(source) != expected_sha256:
        raise MaintenanceFailure("G4_BACKUP_PIN_MISMATCH")
    target.parent.mkdir(parents=True, exist_ok=True)
    with isolated_sqlite_input(source, expected_sha256=expected_sha256, directory=target.parent) as staged:
        with closing(sqlite3.connect(staged.as_uri() + "?mode=ro", uri=True)) as src:
            if src.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
                raise LedgerError("G4_BACKUP_INTEGRITY_FAILED")
            with target.open("xb"):
                pass
            with closing(sqlite3.connect(target)) as dst:
                src.backup(dst)
                if dst.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
                    raise LedgerError("G4_RESTORE_INTEGRITY_FAILED")
    return dict(action="restore", result="restored_to_new_path", backup_sha256=expected_sha256,
                database_sha256=sha(target), restored_at=utcnow(), database_state="committed",
                continuity="explicit_restore_epoch_required_before_future_runtime_history",
                source_opened_by_sqlite=False, input_policy="verified_offline_copy_v1")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("upgrade", "backup", "backfill", "rollback", "restore"))
    parser.add_argument("--database", required=True, type=Path)
    parser.add_argument("--backup", type=Path)
    parser.add_argument("--backup-pin")
    parser.add_argument("--root", type=Path)
    parser.add_argument("--receipt", required=True, type=Path)
    args = parser.parse_args()
    output = None
    operation_started = False
    try:
        paths = resolve_paths(args.database, args.backup, args.receipt)
        output = Receipt(paths)
        output.prepare(args.action)  # Exclusive creation, write/readback/fsync before DB work.
        operation_started = True
        if args.action == "restore":
            if not args.backup or not args.backup_pin:
                raise LedgerError("G4_BACKUP_PIN_REQUIRED")
            result = restore(paths.backup, paths.database, expected_sha256=args.backup_pin)
        else:
            result = maintain(paths.database, args.action, backup=paths.backup, root=args.root)
        result["status"] = "PASS"
        code = 0
    except (LedgerError, OSError, sqlite3.Error, SQLAlchemyError, ValidationError) as error:
        result = dict(status="FAIL", action=args.action,
                      database_state=getattr(error, "database_state",
                                             "unknown" if operation_started else "not_started"),
                      error_code=error.code if isinstance(error, LedgerError) else
                      "G4_MAINTENANCE_FAILED")
        if isinstance(error, MaintenanceFailure) and error.operation:
            result["operation"] = error.operation
        code = 1
    result["receipt_written"] = False
    receipt_failed = False
    try:
        if output is not None and output.primary is not None and output.pending is not None:
            result["receipt_written"] = True
            output.finish(result)
    except OSError:
        receipt_failed = True
    finally:
        if output is not None:
            try:
                output.close()
            except OSError:
                receipt_failed = True
    if receipt_failed:
        result["receipt_written"] = False
        result["error_code"] = "G4_RECEIPT_WRITE_FAILED"
        state = result["database_state"]
        result["status"] = ("COMMITTED_RECEIPT_FAILED" if state == "committed" else
                            "OUTCOME_UNKNOWN_RECEIPT_FAILED" if state == "unknown" else "FAIL")
        code = 2 if state in {"committed", "unknown"} else 1
    print(json.dumps(result, ensure_ascii=False))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
