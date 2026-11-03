"""Real SQLite journal, materialized-row verification, CAS and crash-recoverable anchor."""

import importlib
from contextlib import contextmanager
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.exc import SQLAlchemyError

from .checkpoint import Checkpoint, FileMutex, PersistenceError
from .contracts import digest, instant
from .corpus_trust import capture, extends, packed, unpack, verify_legacy_inputs
from .persistence_models import (
    MODELS,
    RECORD_MODELS,
    BriefingRun,
    BriefingSnapshot,
    IdempotentRequest,
    Installation,
    JournalEntry,
    TrustedHead,
)

MIGRATION = importlib.import_module(".migrations.002_g4_briefings", __package__)
STREAMS = ("real:local", "synthetic:local")


def now():
    return instant(datetime.now(timezone.utc).isoformat())


def genesis(database_id, stream):
    return digest(dict(revision="g4-history-genesis-v1", database_id=database_id, stream_id=stream))


def token(head):
    return dict(sequence=head.sequence, sha256=head.sha256)


def state(head):
    return dict(latest_snapshot_id=head.latest_snapshot_id, publication_version=head.publication_version,
                persona_version_id=head.persona_version_id)


def wire(row):
    deferred = {"input"} if isinstance(row, BriefingRun) else {"runtime"} if isinstance(row, BriefingSnapshot) else set()
    # Large immutable bodies are hash-bound here and verified when actually read. Polling
    # status must not repeatedly deserialize every historical 8 MB computation payload.
    return {c.name: getattr(row, c.name) for c in row.__table__.columns if c.name not in deferred}


def entry_pin(stream, sequence, previous, kind, created_at, body):
    return digest(dict(stream_id=stream, sequence=sequence, previous_sha256=previous,
                       kind=kind, created_at=created_at, data=body))


def installed(session):
    names = set(session.connection().exec_driver_sql(
        "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'intelligence_%'").scalars())
    if not names:
        return None
    from .persistence_models import PersistenceBase
    if names != set(PersistenceBase.metadata.tables):
        raise PersistenceError("G4_PERSISTENCE_MIGRATION_INCOMPLETE", status=503)
    record = session.get(Installation, "database")
    if (record is None or record.revision != MIGRATION.REVISION
            or record.source_sha256 != MIGRATION.source_sha256()
            or record.schema_sha256 != MIGRATION.schema_sha256()
            or session.connection().exec_driver_sql(MIGRATION.QUERY).all() !=
            MIGRATION.expected(MIGRATION.source_sha256())):
        raise PersistenceError("G4_PERSISTENCE_SCHEMA_MISMATCH", status=503)
    return record


class HistoryStore:
    def __init__(self, database, anchor, *, clock=now, fault=lambda _: None, max_entries=20000):
        self.database, self.clock, self.fault = database, clock, fault
        self.checkpoint = Checkpoint(anchor, fault=fault)
        self.max_entries = max_entries

    def verify(self, session, installation, heads, corpus_baseline=None):
        expected = {}
        entries = list(session.scalars(select(JournalEntry).order_by(JournalEntry.stream_id, JournalEntry.sequence)))
        if len(entries) > self.max_entries:
            raise PersistenceError("G4_HISTORY_CAPACITY_EXCEEDED", status=503)
        actual_heads = {key: dict(sequence=0, sha256=genesis(installation.database_id, key)) for key in STREAMS}
        states = {key: dict(latest_snapshot_id=None, publication_version=0, persona_version_id=None) for key in STREAMS}
        times = {}
        for entry in entries:
            prior = actual_heads.get(entry.stream_id)
            if (prior is None or entry.sequence != prior["sequence"] + 1 or entry.previous_sha256 != prior["sha256"]
                    or instant(entry.created_at) != entry.created_at
                    or entry.created_at < times.get(entry.stream_id, entry.created_at)
                    or entry.id != entry_pin(entry.stream_id, entry.sequence, entry.previous_sha256,
                                             entry.kind, entry.created_at, entry.data)):
                raise PersistenceError("G4_HISTORY_CHAIN_INVALID", status=503)
            try:
                for record in entry.data["records"]:
                    if record["table"] not in MODELS:
                        raise ValueError
                    expected[(record["table"], record["id"])] = record["sha256"]
                states[entry.stream_id] = entry.data["state"]
            except (TypeError, KeyError, ValueError):
                raise PersistenceError("G4_HISTORY_CHAIN_INVALID", status=503) from None
            actual_heads[entry.stream_id] = dict(sequence=entry.sequence, sha256=entry.id)
            times[entry.stream_id] = entry.created_at
        if {key: token(h) for key, h in heads.items()} != actual_heads:
            raise PersistenceError("G4_HISTORY_HEAD_INVALID", status=503)
        if any(state(heads[key]) != states[key] for key in STREAMS):
            raise PersistenceError("G4_HISTORY_POINTER_INVALID", status=503)
        observed = {}
        for model in RECORD_MODELS:
            for row in session.scalars(select(model)):
                observed[(model.__tablename__, row.id)] = digest(wire(row))
        if observed != expected:
            raise PersistenceError("G4_HISTORY_RECORD_MISMATCH", status=503)
        corpus = capture(session)
        if corpus_baseline is not None:
            extends(corpus, unpack(corpus_baseline))
        for entry in entries:
            if "corpus" in entry.data:
                extends(corpus, unpack(entry.data["corpus"]))
        if any("corpus" not in e.data for e in entries):
            verify_legacy_inputs(session)
        session.info["verified_corpus"] = corpus

    def _checked(self, session):
        if (session.connection().exec_driver_sql("PRAGMA foreign_keys").scalar() != 1
                or session.connection().exec_driver_sql("PRAGMA synchronous").scalar() < 2):
            raise PersistenceError("G4_SQLITE_DURABILITY_REQUIRED", status=503)
        installation = installed(session)
        if installation is None:
            raise PersistenceError("G4_PERSISTENCE_MIGRATION_REQUIRED", status=503)
        heads = {h.id: h for h in session.scalars(select(TrustedHead))}
        tokens = {key: token(h) for key, h in heads.items()}
        anchor = self.checkpoint.reconcile(installation.database_id, tokens,
                                           lambda corpus: self.verify(session, installation, heads, corpus))
        session.info["checkpoint_epoch"] = anchor["epoch"]
        return heads, anchor

    @contextmanager
    def read(self):
        try:
            with FileMutex(self.checkpoint.lock_path, timeout=2), self.database.session() as session:
                session.connection().exec_driver_sql("BEGIN")
                heads, _ = self._checked(session)
                yield session, heads
        except PersistenceError:
            raise
        except (OSError, SQLAlchemyError):
            raise PersistenceError("G4_PERSISTENCE_UNAVAILABLE", status=503) from None

    def mutate(self, stream, *, key, operation, payload, expected_head, apply, expected_epoch=None,
               before_commit=lambda: None, namespace="client"):
        """apply returns (resource reply, changed/new ORM rows, new pointer-state fields)."""
        committed = False
        prepared = None
        try:
            with FileMutex(self.checkpoint.lock_path, timeout=2), self.database.session() as session:
                session.connection().exec_driver_sql("BEGIN IMMEDIATE")
                heads, anchor = self._checked(session)
                head = heads.get(stream)
                if head is None:
                    raise PersistenceError("G4_STREAM_INVALID")
                if expected_epoch is not None and expected_epoch != anchor["epoch"]:
                    raise PersistenceError("G4_RECOVERY_EPOCH_CONFLICT")
                if namespace not in {"client", "system"}:
                    raise PersistenceError("G4_REQUEST_NAMESPACE_INVALID")
                stored_key = namespace + "|" + key  # '|' is outside the public Key grammar.
                request_id, request_sha = digest([stream, namespace, key]), digest(dict(operation=operation, payload=payload))
                prior = session.get(IdempotentRequest, request_id)
                if prior is None:
                    legacy = session.get(IdempotentRequest, digest([stream, key]))
                    # Preserve old client retries. Internal code only reuses a matching
                    # old operation; an old client cancellation cannot reserve its key.
                    if legacy and (namespace == "client" or legacy.operation == operation):
                        prior = legacy
                if prior:
                    if prior.request_sha256 != request_sha or prior.operation != operation:
                        raise PersistenceError("G4_IDEMPOTENCY_CONFLICT")
                    return dict(resource_id=prior.data["resource_id"], deduplicated=True,
                                head=dict(id=head.id, epoch=anchor["epoch"], **token(head), **state(head)))
                if expected_head is not None and head.sha256 != expected_head:
                    raise PersistenceError("G4_EXPECTED_HEAD_CONFLICT")
                if sum(h.sequence for h in heads.values()) >= self.max_entries:
                    raise PersistenceError("G4_HISTORY_CAPACITY_EXCEEDED", status=503)
                reply, records, pointer_updates = apply(session, head)
                if set(pointer_updates) - set(state(head)):
                    raise PersistenceError("G4_HISTORY_POINTER_INVALID")
                pointers = {**state(head), **pointer_updates}
                request = IdempotentRequest(id=request_id, stream_id=stream, key=stored_key, operation=operation,
                                            request_sha256=request_sha, data=reply)
                session.add(request)
                records = [*records, request]
                session.flush()
                corpus = capture(session)
                extends(corpus, session.info["verified_corpus"])
                body = dict(corpus=packed(corpus), state=pointers,
                    records=[dict(table=r.__tablename__, id=r.id, sha256=digest(wire(r)))
                                                     for r in records])
                created_at = self.clock()
                previous_entry = session.get(JournalEntry, head.sha256)
                if instant(created_at) != created_at or previous_entry and created_at < previous_entry.created_at:
                    raise PersistenceError("G4_CLOCK_ROLLBACK")
                sequence = head.sequence + 1
                sha = entry_pin(stream, sequence, head.sha256, operation, created_at, body)
                session.add(JournalEntry(id=sha, stream_id=stream, sequence=sequence,
                    previous_sha256=head.sha256, kind=operation, created_at=created_at, data=body))
                session.flush()
                before = token(head)
                changed = session.execute(update(TrustedHead).where(TrustedHead.id == stream,
                    TrustedHead.sequence == before["sequence"], TrustedHead.sha256 == before["sha256"])
                    .values(sequence=sequence, sha256=sha, **pointers))
                if changed.rowcount != 1:
                    raise PersistenceError("G4_EXPECTED_HEAD_CONFLICT")
                before_commit()
                prepared = self.checkpoint.prepare(anchor, stream, before, dict(sequence=sequence, sha256=sha))
                self.fault("before_db_commit")
                before_commit()
                try:
                    session.commit()
                except SQLAlchemyError:
                    raise PersistenceError("G4_COMMIT_OUTCOME_UNKNOWN", database_state="unknown", status=503) from None
                committed = True
                self.fault("after_db_commit")
                self.checkpoint.finish(prepared)
                return dict(resource_id=reply["resource_id"], deduplicated=bool(reply.get("deduplicated", False)),
                            head=dict(id=stream, epoch=anchor["epoch"], sequence=sequence, sha256=sha, **pointers))
        except PersistenceError:
            raise
        except (OSError, SQLAlchemyError):
            code = "G4_COMMITTED_ANCHOR_PENDING" if committed else "G4_PERSISTENCE_UNAVAILABLE"
            raise PersistenceError(code, database_state="committed" if committed else "unchanged", status=503) from None
