"""Explicit PR4 migration/backup/rollback and acknowledged restore to fresh paths."""

import argparse
import importlib
import json
from pathlib import Path
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from .checkpoint import Checkpoint, FileMutex, PersistenceError
from .contracts import LedgerError
from .corpus_trust import capture
from .history_store import MIGRATION, STREAMS, HistoryStore, genesis, installed, now
from .maintenance_io import (
    SIDECARS,
    MaintenanceFailure,
    Receipt,
    overlaps,
    resolve_paths,
    validate_paths,
)
from .migrate import backup_locked, check_installed, restore, sha, table_names, verify_backup
from .persistence_models import PersistenceBase


def paths_for(database, anchor, backup=None, receipt=None):
    paths = validate_paths(resolve_paths(database, backup, receipt))
    checkpoint = Checkpoint(resolve_paths(anchor).database)
    products = [p for p in (paths.database, paths.backup, paths.manifest, paths.receipt, paths.staging) if p]
    reserved = [Path(str(p) + suffix).resolve() for p in (paths.database, paths.backup) if p for suffix in SIDECARS]
    anchors = (checkpoint.path, checkpoint.lock_path, checkpoint.worker_path)
    for item in anchors:
        if any(overlaps(item, p) for p in (*products, *reserved)):
            raise MaintenanceFailure("G4_CHECKPOINT_PATH_CONFLICT")
        for base in (paths.database, paths.backup):
            if base and item.parent == base.parent and item.name.startswith(base.name + "-mj"):
                raise MaintenanceFailure("G4_PATH_RESERVED")
    for i, left in enumerate(anchors):
        if any(overlaps(left, right) for right in anchors[i + 1:]):
            raise MaintenanceFailure("G4_CHECKPOINT_PATH_CONFLICT")
    return paths, checkpoint


def maintain(database, anchor, action, *, backup=None, acknowledge_restore=False):
    paths, checkpoint = paths_for(database, anchor, backup)
    existed = paths.database.exists() and paths.database.stat().st_size > 0
    if action not in {"upgrade", "backup", "rollback", "adopt-restore"}:
        raise MaintenanceFailure("G4_MIGRATION_ACTION_INVALID")
    if existed and backup is None:
        raise MaintenanceFailure("G4_BACKUP_REQUIRED")
    if action != "upgrade" and not existed:
        raise MaintenanceFailure("G4_DATABASE_NOT_FOUND")
    if backup and (paths.backup.exists() or paths.manifest.exists()):
        raise MaintenanceFailure("G4_BACKUP_TARGET_EXISTS")
    if action == "adopt-restore" and not acknowledge_restore:
        raise MaintenanceFailure("G4_RESTORE_ACKNOWLEDGEMENT_REQUIRED")
    if action == "adopt-restore" and checkpoint.path.exists():
        raise MaintenanceFailure("G4_CHECKPOINT_TARGET_EXISTS")
    paths.database.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(URL.create("sqlite", database=paths.database.as_posix()), connect_args={"timeout": 15})
    receipt = dict(action=action, migration=MIGRATION.REVISION, migration_sha256=MIGRATION.source_sha256(),
                   schema_sha256=MIGRATION.schema_sha256(), started_at=now())
    committed = False
    try:
        with FileMutex(checkpoint.worker_path), FileMutex(checkpoint.lock_path), engine.connect() as connection:
            connection.exec_driver_sql("PRAGMA foreign_keys=ON")
            connection.exec_driver_sql("BEGIN IMMEDIATE")
            if backup:
                receipt["backup"] = backup_locked(paths.database, paths.backup)
            names = set(connection.exec_driver_sql(
                "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'intelligence_%'").scalars())
            if not names:
                if action != "upgrade":
                    raise MaintenanceFailure("G4_PERSISTENCE_MIGRATION_REQUIRED")
                if checkpoint.path.exists():
                    raise MaintenanceFailure("G4_CHECKPOINT_TARGET_EXISTS")
                if table_names(connection):
                    check_installed(connection)
                else:
                    previous = importlib.import_module(".migrations.001_g4_documents", __package__)
                    for sql in previous.statements():
                        connection.exec_driver_sql(sql)
                    connection.exec_driver_sql("INSERT INTO g4_migrations VALUES (?,?,?,?)", (
                        previous.REVISION, previous.source_sha256(), previous.schema_sha256(), now()))
                for sql in MIGRATION.statements():
                    connection.exec_driver_sql(sql)
                database_id = uuid4().hex
                connection.exec_driver_sql("INSERT INTO intelligence_installation VALUES (?,?,?,?,?)", (
                    "database", database_id, MIGRATION.REVISION, MIGRATION.source_sha256(), MIGRATION.schema_sha256()))
                heads = {}
                for stream in STREAMS:
                    head = genesis(database_id, stream)
                    connection.exec_driver_sql("INSERT INTO intelligence_heads VALUES (?,?,?,NULL,0,NULL)", (stream, 0, head))
                    heads[stream] = dict(sequence=0, sha256=head)
                with Session(bind=connection, join_transaction_mode="rollback_only") as session:
                    checkpoint.initialize(database_id, heads, capture(session))
                receipt["result"] = "upgraded_genesis_no_history_backfill"
            else:
                with Session(bind=connection, join_transaction_mode="rollback_only") as session:
                    installation = installed(session)
                    from sqlalchemy import select

                    from .persistence_models import TrustedHead
                    heads = {h.id: h for h in session.scalars(select(TrustedHead))}
                    tokens = {key: dict(sequence=h.sequence, sha256=h.sha256) for key, h in heads.items()}
                    store = HistoryStore(type("Binding", (), {})(), checkpoint.path)
                    if action == "adopt-restore":
                        store.verify(session, installation, heads)
                        checkpoint.initialize(installation.database_id, tokens, session.info["verified_corpus"])
                        receipt["result"] = "restored_history_explicitly_acknowledged_new_checkpoint_epoch"
                    else:
                        checkpoint.reconcile(installation.database_id, tokens,
                                             lambda corpus: store.verify(session, installation, heads, corpus))
                        receipt["result"] = "already_current" if action == "upgrade" else "backed_up"
                if action == "rollback":
                    for table in reversed(PersistenceBase.metadata.sorted_tables):
                        connection.exec_driver_sql(f'DROP TABLE "{table.name}"')
                    receipt["result"] = "pr4_tables_removed_pr2_legacy_untouched_anchor_retained"
            if connection.exec_driver_sql("PRAGMA foreign_key_check").all():
                raise MaintenanceFailure("G4_DATABASE_FOREIGN_KEY_FAILED")
            try:
                connection.commit()
            except SQLAlchemyError:
                raise MaintenanceFailure("G4_COMMIT_OUTCOME_UNKNOWN", database_state="unknown") from None
            committed = True
    except (OSError, SQLAlchemyError) as error:
        raise MaintenanceFailure("G4_PERSISTENCE_MAINTENANCE_FAILED",
                                 database_state="committed" if committed else "unknown") from error
    finally:
        engine.dispose()
    try:
        if backup:
            verify_backup(paths, receipt["backup"])
            receipt["backup_verified_after_commit"] = True
        receipt.update(finished_at=now(), database_state="committed", database_sha256=sha(paths.database),
                       checkpoint_sha256=sha(checkpoint.path), restored_history_inferred=False)
    except (LedgerError, OSError):
        raise MaintenanceFailure("G4_POSTCOMMIT_VERIFICATION_FAILED", database_state="committed",
                                 operation=receipt) from None
    return receipt


def restore_with_epoch(backup, database, anchor, *, expected_sha256, acknowledge_restore):
    paths, checkpoint = paths_for(database, anchor, backup)
    if not acknowledge_restore:
        raise MaintenanceFailure("G4_RESTORE_ACKNOWLEDGEMENT_REQUIRED")
    if paths.database.exists() or checkpoint.path.exists():
        raise MaintenanceFailure("G4_RESTORE_TARGET_EXISTS")
    result = restore(paths.backup, paths.database, expected_sha256=expected_sha256)
    # No DB mutation is needed to acknowledge a new independently kept checkpoint epoch.
    engine = create_engine(URL.create("sqlite", database=paths.database.as_posix()))
    try:
        with FileMutex(checkpoint.worker_path), FileMutex(checkpoint.lock_path), Session(engine) as session:
            installation = installed(session)
            if installation is None:
                raise PersistenceError("G4_PERSISTENCE_MIGRATION_REQUIRED")
            if session.connection().exec_driver_sql("PRAGMA foreign_key_check").all():
                raise PersistenceError("G4_DATABASE_FOREIGN_KEY_FAILED")
            from sqlalchemy import select

            from .persistence_models import TrustedHead
            heads = {h.id: h for h in session.scalars(select(TrustedHead))}
            HistoryStore(type("Binding", (), {})(), checkpoint.path).verify(session, installation, heads)
            checkpoint.initialize(installation.database_id,
                {key: dict(sequence=h.sequence, sha256=h.sha256) for key, h in heads.items()}, session.info["verified_corpus"])
    except (LedgerError, OSError, SQLAlchemyError) as error:
        raise MaintenanceFailure("G4_RESTORED_CHECKPOINT_NOT_READY", database_state="committed") from error
    finally:
        engine.dispose()
    return {**result, "continuity": "administrator_acknowledged_restore_epoch",
            "checkpoint_sha256": sha(checkpoint.path)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("upgrade", "backup", "rollback", "adopt-restore", "restore"))
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--anchor", type=Path, required=True)
    parser.add_argument("--backup", type=Path)
    parser.add_argument("--backup-pin")
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--acknowledge-restored-history", action="store_true")
    args = parser.parse_args()
    output, started = None, False
    try:
        paths, _ = paths_for(args.database, args.anchor, args.backup, args.receipt)
        output = Receipt(paths)
        output.prepare(args.action)
        started = True
        if args.action == "restore":
            if not args.backup or not args.backup_pin:
                raise MaintenanceFailure("G4_BACKUP_PIN_REQUIRED")
            result = restore_with_epoch(paths.backup, paths.database, args.anchor,
                expected_sha256=args.backup_pin, acknowledge_restore=args.acknowledge_restored_history)
        else:
            result = maintain(paths.database, args.anchor, args.action, backup=paths.backup,
                              acknowledge_restore=args.acknowledge_restored_history)
        result["status"], code = "PASS", 0
    except (LedgerError, OSError, SQLAlchemyError) as error:
        result = dict(status="FAIL", database_state=getattr(error, "database_state", "unknown" if started else "not_started"),
                      error_code=getattr(error, "code", "G4_PERSISTENCE_MAINTENANCE_FAILED"))
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
        if output:
            try:
                output.close()
            except OSError:
                receipt_failed = True
    if receipt_failed:
        result["receipt_written"], result["error_code"] = False, "G4_RECEIPT_WRITE_FAILED"
        result["status"] = "COMMITTED_RECEIPT_FAILED" if result["database_state"] == "committed" else "FAIL"
        code = 2 if result["database_state"] in {"committed", "unknown"} else 1
    print(json.dumps(result))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
