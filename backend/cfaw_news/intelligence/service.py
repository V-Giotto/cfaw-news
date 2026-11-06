"""Local persistent lifecycle. No providers, network, notifications or legacy goal rules."""

import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

from pydantic import ValidationError
from sqlalchemy import func, select

from evals.intelligence_g2.contracts import json_bytes
from evals.intelligence_g3.contracts import PersonaSnapshot
from evals.intelligence_v1.hashing import sha256_bytes

from .checkpoint import FileMutex, PersistenceError
from .contracts import LedgerError, canonical, digest, instant
from .history_store import HistoryStore, installed, now
from .persistence_contracts import (
    TERMINAL,
    EventDetailView,
    InteractionView,
    PersonaView,
    SnapshotPage,
    StatusView,
    VisitView,
)
from .persistence_migrate import paths_for
from .persistence_models import (
    ArchiveItem,
    BriefingRun,
    BriefingSnapshot,
    DeliveryItem,
    IdempotentRequest,
    InteractionRow,
    JournalEntry,
    PersonaVersionRow,
)
from .publication import (
    corpus_basis,
    head_view,
    latest_assessments,
    mutation_view,
    parse,
    qualification,
    read_snapshot,
    run_view,
    snapshot_view,
)
from .runtime import from_ledger
from .runtime import run as calculate
from .runtime_contracts import FACT_PIN, ExplicitBudget, RuntimeConfig, RuntimeResult
from .runtime_contracts import HISTORY_RANK_PIN as RANK_PIN
from .runtime_control import Control


def error_code(error):
    if isinstance(error, LedgerError):
        return error.code
    if isinstance(error, ValidationError):
        codes = {getattr(e.get("ctx", {}).get("error"), "code", "G4_RUNTIME_REJECTED") for e in error.errors(include_input=False)}
        for code in ("G4_RUNTIME_CANCELLED", "G4_RUNTIME_TIMEOUT"):
            if code in codes:
                return code
        if len(codes) == 1:
            return next(iter(codes))
    return "G4_RUNTIME_REJECTED"


class IntelligenceService:
    def __init__(self, database, settings, *, clock=now, runtime=calculate, fault=lambda _: None):
        self.database, self.settings, self.clock, self.runtime = database, settings, clock, runtime
        self.mode = settings.intelligence_mode
        self.origin = "real" if self.mode == "real" else "synthetic"
        self.stream = self.origin + ":local"
        anchor = settings.intelligence_anchor or settings.root / ".local/intelligence-head.json"
        if database.engine.dialect.name != "sqlite" or database.engine.url.database == ":memory:":
            raise PersistenceError("G4_FILE_SQLITE_REQUIRED")
        paths_for(Path(database.engine.url.database), anchor)
        self.store = HistoryStore(database, anchor, clock=clock, fault=fault)
        self.tasks, self.events = {}, {}
        self.owner_id, self.worker_lock = uuid4().hex, None
        self.worker_available, self.closed, self.code = False, False, None
        self.loop = None
        self.semaphore = asyncio.Semaphore(settings.intelligence_max_workers)
        self.compute_pool = ThreadPoolExecutor(max_workers=settings.intelligence_max_workers,
                                               thread_name_prefix="g4-native")
        self.computations, self.computation_lock = set(), threading.Lock()
        self.close_drained = False

    async def start(self):
        self.loop = asyncio.get_running_loop()
        try:
            with self.database.session() as session:
                if installed(session) is None:
                    self.code = "G4_PERSISTENCE_MIGRATION_REQUIRED"
                    return
            with self.store.read():
                pass
            self.worker_lock = FileMutex(self.store.checkpoint.worker_path)
            try:
                self.worker_lock.__enter__()
            except (OSError, PersistenceError):
                self.worker_lock = None
                return  # Another local instance owns computation; persistent reads/cancel still work.
            self.worker_available = True
            await asyncio.to_thread(self.recover)
        except (OSError, LedgerError) as error:
            self.code = getattr(error, "code", "G4_PERSISTENCE_UNAVAILABLE")
            if self.worker_lock:
                self.worker_lock.__exit__(None, None, None)
                self.worker_lock = None
            self.worker_available = False

    def require_ready(self, *, worker=False):
        if self.closed or self.code:
            raise PersistenceError(self.code or "G4_SERVICE_STOPPED", status=503)
        if worker and not self.worker_available:
            raise PersistenceError("G4_WORKER_UNAVAILABLE", status=503)

    def profiles(self):
        return [dict(profile=p, config_sha256=digest(RuntimeConfig(schema_revision="g4-h09-config-v2",
            ranking_policy_sha256=RANK_PIN, budget=ExplicitBudget(profile=p)).model_dump(mode="json")))
                for p in ("focus60-radar40-v1", "focus70-radar30-v1", "focus80-radar20-v1")]

    def status(self):
        head = None
        code = self.code
        try:
            if code is None:
                with self.store.read() as (session, heads):
                    head = head_view(heads[self.stream], session.info["checkpoint_epoch"]).model_dump(mode="json")
        except LedgerError as error:
            code = error.code
        state = "ready" if code is None else "migration_required" if code == "G4_PERSISTENCE_MIGRATION_REQUIRED" else "unavailable"
        return parse(StatusView, dict(enabled=True, state=state, mode=self.mode, head=head,
            worker_available=self.worker_available and code is None, code=code,
            runtime_policy_sha256=RANK_PIN, profiles=self.profiles()))

    def _write(self, body, operation, apply):
        self.require_ready()
        payload = body.model_dump(mode="json", exclude={"idempotency_key", "expected_head", "expected_epoch"})
        result = self.store.mutate(self.stream, key=body.idempotency_key, operation=operation, payload=payload,
            expected_head=body.expected_head, expected_epoch=body.expected_epoch, apply=apply)
        return mutation_view(result)

    def persona_write(self, body):
        def apply(session, head):
            previous = session.get(PersonaVersionRow, head.persona_version_id) if head.persona_version_id else None
            version = previous.version if previous else 0
            if version != body.expected_persona_version:
                raise PersistenceError("G4_PERSONA_VERSION_CONFLICT")
            if version >= self.settings.intelligence_max_persona_versions:
                raise PersistenceError("G4_PERSONA_CAPACITY_EXCEEDED", status=429)
            identifier, timestamp = uuid4().hex, self.clock()
            fields = body.model_dump(mode="json", exclude={"schema_revision", "idempotency_key", "expected_head",
                                                          "expected_epoch", "expected_persona_version"})
            native = dict(persona=dict(persona_id="local", persona_version_id=identifier, available_at=timestamp,
                persona_origin="consented_real" if self.origin == "real" else "constructed", **fields),
                record_origin=self.origin, provenance_uri="local-sqlite:persona:" + identifier)
            parsed = PersonaSnapshot.model_validate_json(canonical(native))
            view = parse(PersonaView, dict(id=identifier, version=version + 1, available_at=timestamp,
                                          record_origin=self.origin, **fields))
            row = PersonaVersionRow(id=identifier, stream_id=self.stream, version=version + 1,
                available_at=timestamp, data=dict(view=view.model_dump(mode="json"), native=parsed.model_dump(mode="json")))
            session.add(row)
            return dict(resource_id=identifier), [row], dict(persona_version_id=identifier)
        return self._write(body, "persona", apply)

    def persona(self, as_of=None, *, all_versions=False, limit=200, offset=0):
        self.require_ready()
        cutoff = self.cutoff(as_of)
        with self.store.read() as (session, _):
            query = select(PersonaVersionRow).where(PersonaVersionRow.stream_id == self.stream,
                PersonaVersionRow.available_at <= cutoff)
            query = query.order_by(PersonaVersionRow.version).offset(offset).limit(limit) if all_versions else (
                query.order_by(PersonaVersionRow.version.desc()).limit(1))
            rows = list(session.scalars(query))
            if all_versions:
                return [parse(PersonaView, row.data["view"]) for row in rows]
            if not rows:
                raise PersistenceError("G4_PERSONA_NOT_FOUND", status=404)
            return parse(PersonaView, rows[0].data["view"])

    def cutoff(self, value=None):
        try:
            cutoff = instant(value.isoformat() if isinstance(value, datetime) else value) if value else self.clock()
        except LedgerError:
            raise PersistenceError("G4_TIME_INVALID", status=422) from None
        if cutoff > self.clock():
            raise PersistenceError("G4_RUNTIME_FUTURE_INPUT", status=422)
        return cutoff

    def start_run(self, body):
        self.require_ready(worker=True)
        def apply(session, head):
            if head.publication_version != body.expected_latest_version:
                raise PersistenceError("G4_LATEST_VERSION_CONFLICT")
            persona = session.get(PersonaVersionRow, body.persona_version_id)
            if persona is None or persona.stream_id != self.stream or head.persona_version_id != persona.id:
                raise PersistenceError("G4_PERSONA_VERSION_CONFLICT")
            active = list(session.scalars(select(BriefingRun.id).where(BriefingRun.stream_id == self.stream,
                BriefingRun.status.in_(["queued", "running"]))))
            if len(active) >= self.settings.intelligence_queue_limit:
                raise PersistenceError("G4_RUN_CAPACITY_EXCEEDED", status=429)
            if session.scalar(select(func.count()).select_from(BriefingRun).where(
                    BriefingRun.stream_id == self.stream)) >= self.settings.intelligence_max_runs:
                raise PersistenceError("G4_RUN_STORAGE_CAPACITY_EXCEEDED", status=429)
            timestamp = self.clock()
            as_of = datetime.fromisoformat(timestamp)
            from .runtime_history import load_prefix, visit_window
            prefix = load_prefix(session, head, session.info["checkpoint_epoch"])
            window = visit_window(prefix, as_of,
                datetime.fromisoformat(body.time_window_start) if body.time_window_start else None,
                body.visit_before_sequence)
            start = window.start_at
            if not as_of - timedelta(days=30) <= start <= as_of:
                raise PersistenceError("G4_RUNTIME_INTERVAL_INVALID", status=422)
            profile = PersonaSnapshot.model_validate_json(canonical(persona.data["native"]))
            config = RuntimeConfig(schema_revision="g4-h09-config-v2", ranking_policy_sha256=RANK_PIN,
                algorithm=body.algorithm, experiment=body.experiment,
                budget=ExplicitBudget(profile=body.profile), attention_budget_seconds=profile.persona.attention_budget_seconds)
            value = from_ledger(session, stream_id=self.stream, as_of=as_of, time_window_start=start,
                persona=profile, config=config, record_origin=self.origin,
                persona_history=tuple(PersonaSnapshot.model_validate_json(canonical(p["data"]["native"]))
                    for p in sorted(prefix.rows("intelligence_persona_versions"), key=lambda p: p["version"])),
                history_prefix=prefix, visit_window=window,
                synthetic_provenance_uri=self.settings.intelligence_synthetic_provenance if self.origin == "synthetic" else None)
            raw = json_bytes(value)
            if len(raw) > 4_000_000:
                raise PersistenceError("G4_RUNTIME_RESOURCE_LIMIT", status=413)
            identifier = uuid4().hex
            row = BriefingRun(id=identifier, stream_id=self.stream, status="queued", version=1,
                cancel_requested=False, created_at=timestamp, input_sha256=sha256_bytes(raw),
                input=value.model_dump(mode="json"), data=dict(started_at=None, finished_at=None,
                    as_of=timestamp, persona_version_id=persona.id, snapshot_id=None, reason_codes=[],
                    input_sha256=sha256_bytes(raw), corpus_basis=corpus_basis(session),
                    expected_latest_version=head.publication_version, owner_id=self.owner_id))
            session.add(row)
            return dict(resource_id=identifier), [row], {}
        try:
            receipt = self._write(body, "briefing", apply)
        except (LedgerError, ValidationError) as error:
            if isinstance(error, PersistenceError):
                raise
            raise PersistenceError(error_code(error), status=422) from None
        self.loop.call_soon_threadsafe(self.launch, receipt.resource_id)
        return receipt

    def get_run(self, identifier):
        self.require_ready()
        with self.store.read() as (session, _):
            return run_view(self.row(session, BriefingRun, identifier))

    def row(self, session, model, identifier):
        row = session.get(model, identifier)
        if row is None or row.stream_id != self.stream:
            raise PersistenceError("G4_NOT_FOUND", status=404)
        return row

    def cancel(self, identifier, body):
        def apply(session, head):
            row = self.row(session, BriefingRun, identifier)
            if row.version != body.expected_run_version:
                raise PersistenceError("G4_RUN_VERSION_CONFLICT")
            if row.status in TERMINAL:
                raise PersistenceError("G4_RUN_TERMINAL")
            row.status, row.cancel_requested, row.version = "cancelled", True, row.version + 1
            row.data = {**row.data, "finished_at": self.clock(), "reason_codes": ["G4_RUNTIME_CANCELLED"]}
            return dict(resource_id=row.id), [row], {}
        receipt = self._write(body, "cancel:" + identifier, apply)
        event = self.events.get(identifier)
        if event:
            event.set()
        return receipt

    def launch(self, identifier):
        if not self.closed and identifier not in self.tasks:
            task = asyncio.create_task(self.execute(identifier))
            self.tasks[identifier] = task
            task.add_done_callback(lambda _: self.tasks.pop(identifier, None))

    def _running(self, identifier):
        def apply(session, head):
            row = self.row(session, BriefingRun, identifier)
            if row.status != "queued":
                raise PersistenceError("G4_RUN_TERMINAL")
            if (head.persona_version_id != row.data["persona_version_id"]
                    or head.publication_version != row.data["expected_latest_version"]
                    or corpus_basis(session) != row.data["corpus_basis"]):
                raise PersistenceError("G4_RUN_BASIS_STALE")
            row.status, row.version = "running", row.version + 1
            row.data = {**row.data, "started_at": self.clock(), "owner_id": self.owner_id}
            return dict(resource_id=row.id), [row], {}
        result = self.store.mutate(self.stream, key="run:" + identifier + ":start", operation="run-start",
            payload=dict(run_id=identifier), expected_head=None, apply=apply, namespace="system")
        with self.store.read() as (session, _):
            row = self.row(session, BriefingRun, identifier)
            value = {**row.data, "input": row.input}
            if sha256_bytes(json_bytes(value["input"])) != row.input_sha256:
                raise PersistenceError("G4_RUNTIME_INPUT_PIN_MISMATCH")
        return value, result["head"]

    def is_cancelled(self, identifier, event):
        if event.is_set() or self.closed:
            return True
        try:
            with self.database.session() as session:
                row = session.execute(select(BriefingRun.cancel_requested, BriefingRun.status)
                                      .where(BriefingRun.id == identifier)).first()
                return row is None or row.cancel_requested or row.status in TERMINAL
        except Exception:
            return True  # Storage failure cannot authorize continued computation/publication.

    def _terminal(self, identifier, status, codes):
        def apply(session, head):
            row = self.row(session, BriefingRun, identifier)
            if row.status in TERMINAL:
                raise PersistenceError("G4_RUN_TERMINAL")
            row.status, row.version = status, row.version + 1
            row.data = {**row.data, "finished_at": self.clock(), "reason_codes": codes}
            return dict(resource_id=row.id), [row], {}
        try:
            return self.store.mutate(self.stream, key="run:" + identifier + ":terminal", operation="run-terminal",
                payload=dict(run_id=identifier, status=status, codes=codes), expected_head=None, apply=apply, namespace="system")
        except PersistenceError as error:
            if error.code != "G4_RUN_TERMINAL":
                raise

    async def execute(self, identifier):
        event = self.events.setdefault(identifier, threading.Event())
        owns_permit = False
        try:
            await self.semaphore.acquire()
            owns_permit = True
            ready = asyncio.Event()
            runtime = self.runtime
            def compute_and_publish():
                # The actual Future owns the reservation even if its asyncio waiter
                # is cancelled while run-start is committing or returning.
                value, head = self._running(identifier)
                with self.computation_lock:
                    if self.closed or self.worker_lock is None:
                        raise PersistenceError("G4_RUNTIME_CANCELLED")
                control = Control(cancelled=lambda: self.is_cancelled(identifier, event),
                                  timeout_seconds=self.settings.intelligence_timeout_seconds)
                self.loop.call_soon_threadsafe(ready.set)
                raw = json_bytes(value["input"])
                result = runtime(raw, expected_sha256=value["input_sha256"], control=control)
                return self._publish(identifier, result, head, control)
            with self.computation_lock:
                if self.closed:
                    raise PersistenceError("G4_RUNTIME_CANCELLED")
                self.require_ready(worker=True)
                if self.worker_lock is None:
                    raise PersistenceError("G4_WORKER_UNAVAILABLE", status=503)
                future = self.compute_pool.submit(compute_and_publish)
                self.computations.add(future)
                owns_permit = False  # Admission/submit/register are atomic with close.
            # A completed Future may invoke callbacks inline; never register under the lock.
            future.add_done_callback(lambda done: self.computation_done(done, ready))
            waiting = asyncio.wrap_future(future)
            # Consume late exceptions, while shield prevents timeout/cancellation from
            # cancelling a queued/running concurrent Future and faking its completion.
            waiting.add_done_callback(lambda f: f.exception() if not f.cancelled() else None)
            await ready.wait()  # Preserve native timeout's start after run-start.
            await asyncio.wait_for(asyncio.shield(waiting), self.settings.intelligence_timeout_seconds)
        except asyncio.TimeoutError:
            event.set()
            await self.finish(identifier, "timed_out", ["G4_RUNTIME_TIMEOUT"])
        except asyncio.CancelledError:
            event.set()
            await self.finish(identifier, "interrupted", ["G4_SERVICE_STOPPED"])
            raise
        except (LedgerError, ValidationError) as error:
            code = error_code(error)
            status = ("interrupted" if self.closed and code == "G4_RUNTIME_CANCELLED"
                      else "cancelled" if code == "G4_RUNTIME_CANCELLED" else "timed_out" if code == "G4_RUNTIME_TIMEOUT"
                      else "stale" if code in {"G4_EXPECTED_HEAD_CONFLICT", "G4_RUN_BASIS_STALE", "G4_RECOVERY_EPOCH_CONFLICT"}
                      else "evidence_not_ready" if code.startswith(("G4_SOURCE_", "G4_EVIDENCE_", "G4_NATIVE_", "G4_RUNTIME_PERSONA_"))
                      or code in {"G4_RUNTIME_NO_ELIGIBLE_BUDGET_FIT", "G4_RUNTIME_POLICY_TRANSITION_UNSUPPORTED",
                                  "G4_RUNTIME_RIGHTS_OR_LEGACY_NOT_EVIDENCE", "G4_RUNTIME_SOURCE_UNRESOLVED"}
                      else "failed")
            await self.finish(identifier, status, [code])
        except Exception:
            await self.finish(identifier, "failed", ["G4_EXECUTION_FAILED"])
        finally:
            if owns_permit:
                self.semaphore.release()
            self.events.pop(identifier, None)

    def computation_done(self, future, ready):
        with self.computation_lock:
            self.computations.discard(future)
            self.release_owner_if_drained()
        try:
            self.loop.call_soon_threadsafe(ready.set)  # Also wakes waiters on run-start failure/cancellation.
            self.loop.call_soon_threadsafe(self.semaphore.release)
        except RuntimeError:
            pass  # Closed loop has no waiters; actual completion still releases owner.

    def release_owner_if_drained(self):
        # Caller holds computation_lock. Never permit a replacement service to run
        # concurrently with run-start reservations or timed-out work from this instance.
        if self.closed and self.close_drained and not self.computations and self.worker_lock:
            self.worker_lock.__exit__(None, None, None)
            self.worker_lock = None

    async def finish(self, identifier, status, codes):
        for _ in range(20):
            try:
                await asyncio.to_thread(self._terminal, identifier, status, codes)
                return
            except PersistenceError as error:
                if error.code not in {"G4_STORE_BUSY", "G4_PERSISTENCE_UNAVAILABLE"}:
                    self.code = error.code
                    return
                await asyncio.sleep(0.01)
        self.code = "G4_PERSISTENCE_UNAVAILABLE"

    def _publish(self, identifier, result, expected, control):
        result = RuntimeResult.model_validate_json(json_bytes(result), context={"control": control})
        qualification(result, self.mode)
        if len(json_bytes(result)) > 8_000_000:
            raise PersistenceError("G4_SNAPSHOT_RESOURCE_LIMIT")
        def apply(session, head):
            control.check("publication")
            row = self.row(session, BriefingRun, identifier)
            if row.status != "running" or row.cancel_requested or self.closed:
                raise PersistenceError("G4_RUNTIME_CANCELLED")
            if (head.persona_version_id != row.data["persona_version_id"]
                    or head.publication_version != row.data["expected_latest_version"]
                    or corpus_basis(session) != row.data["corpus_basis"]
                    or result.input_sha256 != row.data["input_sha256"]
                    or result.input.config.fact_signature_policy_sha256 != FACT_PIN):
                raise PersistenceError("G4_RUN_BASIS_STALE")
            generated_at = self.clock()
            if session.scalar(select(func.count()).select_from(BriefingSnapshot).where(
                    BriefingSnapshot.stream_id == self.stream)) >= self.settings.intelligence_max_snapshots:
                raise PersistenceError("G4_SNAPSHOT_CAPACITY_EXCEEDED", status=429)
            view = snapshot_view(result, run=row, version=head.publication_version + 1,
                                 generated_at=generated_at, mode=self.mode)
            snapshot = BriefingSnapshot(id=view.id, stream_id=self.stream, run_id=row.id, version=view.version,
                as_of=instant(view.as_of.isoformat()), generated_at=generated_at,
                runtime_sha256=view.runtime_sha256, runtime=result.model_dump(mode="json"), data=view.model_dump(mode="json"))
            session.add(snapshot)
            session.flush()  # Parent exists before immutable Archive/Delivery/Interaction inserts.
            records = [snapshot]
            for item in view.archive:
                record = ArchiveItem(id=item.id, stream_id=self.stream, snapshot_id=view.id,
                    event_snapshot_id=item.event_snapshot_id, data=item.model_dump(mode="json"))
                session.add(record)
                records.append(record)
            for item in view.deliveries:
                record = DeliveryItem(id=item.id, stream_id=self.stream, snapshot_id=view.id,
                    event_snapshot_id=item.event_snapshot_id, ordinal=item.ordinal, data=item.model_dump(mode="json"))
                session.add(record)
                records.append(record)
                included = InteractionRow(id=uuid4().hex, stream_id=self.stream, snapshot_id=view.id,
                    target_id=item.id, kind="included", observation_key=digest([view.id, item.id, "included"]),
                    journal_sequence=head.sequence + 1, ordinal=item.ordinal,
                    retracts_id=None, available_at=generated_at, data=dict(client_occurred_at=None,
                        persona_version_id=row.data["persona_version_id"], source="server_publication"))
                session.add(included)
                records.append(included)
            row.status, row.version = "completed", row.version + 1
            row.data = {**row.data, "snapshot_id": view.id, "finished_at": generated_at, "reason_codes": list(result.reason_codes)}
            records.append(row)
            return dict(resource_id=view.id), records, dict(latest_snapshot_id=view.id, publication_version=view.version)
        expected_head = expected["sha256"]
        for attempt in range(8):
            try:
                return self.store.mutate(self.stream, key="run:" + identifier + ":publish", operation="publication",
                    payload=dict(run_id=identifier, runtime_sha256=sha256_bytes(json_bytes(result))),
                    expected_head=expected_head, expected_epoch=expected["epoch"], apply=apply,
                    before_commit=lambda: control.check("publication_commit"), namespace="system")
            except PersistenceError as error:
                prefix = result.input.history_prefix
                if error.code != "G4_EXPECTED_HEAD_CONFLICT" or prefix is None or attempt == 7:
                    raise
                # Later confirmations do not belong to this immutable as-of prefix.
                # Keep CAS and all persona/corpus/latest/cancel guards in apply().
                control.check("publication_head_retry")
                with self.store.read() as (session, heads):
                    if session.info["checkpoint_epoch"] != expected["epoch"]:
                        raise PersistenceError("G4_RECOVERY_EPOCH_CONFLICT") from None
                    old = session.scalar(select(JournalEntry.id).where(JournalEntry.stream_id == self.stream,
                        JournalEntry.sequence == prefix.sequence))
                    if old != prefix.sha256:
                        raise PersistenceError("G4_RUNTIME_HISTORY_PREFIX_INVALID") from None
                    expected_head = heads[self.stream].sha256

    def briefing(self, identifier=None):
        self.require_ready()
        with self.store.read() as (session, heads):
            key = identifier or heads[self.stream].latest_snapshot_id
            if not key:
                raise PersistenceError("G4_BRIEFING_NOT_FOUND", status=404)
            return read_snapshot(self.row(session, BriefingSnapshot, key))

    def briefings(self, *, limit=20, before_version=None, through_version=None):
        """Publication directory, independent of exposure or interaction history."""
        self.require_ready()
        with self.store.read() as (session, heads):
            upper = heads[self.stream].publication_version if through_version is None else through_version
            if not 0 <= upper <= heads[self.stream].publication_version:
                raise PersistenceError("G4_SNAPSHOT_DIRECTORY_VERSION_CONFLICT")
            query = select(BriefingSnapshot.id, BriefingSnapshot.version, BriefingSnapshot.as_of,
                BriefingSnapshot.generated_at, BriefingSnapshot.data["evidence_status"].as_string()).where(
                BriefingSnapshot.stream_id == self.stream, BriefingSnapshot.version <= upper)
            if before_version is not None:
                query = query.where(BriefingSnapshot.version < before_version)
            rows = list(session.execute(query.order_by(BriefingSnapshot.version.desc()).limit(limit + 1)))
            items = [dict(id=r[0], version=r[1], as_of=r[2], generated_at=r[3], evidence_status=r[4]) for r in rows[:limit]]
            return parse(SnapshotPage, dict(stream_id=self.stream, through_version=upper, items=items,
                next_before_version=items[-1]["version"] if len(rows) > limit else None))

    def visit(self, body):
        def apply(session, head):
            if body.briefing_id is not None:
                self.row(session, BriefingSnapshot, body.briefing_id)
            prior = session.scalar(select(IdempotentRequest).where(IdempotentRequest.stream_id == self.stream,
                IdempotentRequest.operation == "visit",
                IdempotentRequest.data["visit"]["session_key"].as_string() == body.session_key))
            if prior:
                return dict(resource_id=prior.data["resource_id"], deduplicated=True), [], {}
            return dict(resource_id=uuid4().hex, visit=dict(confirmation=body.confirmation,
                session_key=body.session_key, briefing_id=body.briefing_id)), [], {}
        return self._write(body, "visit", apply)

    def last_visit(self, *, through_sequence=None):
        from .history_store import wire
        from .runtime_history import confirmed_visits
        self.require_ready()
        with self.store.read() as (session, heads):
            upper = heads[self.stream].sequence if through_sequence is None else through_sequence
            if not 0 <= upper <= heads[self.stream].sequence:
                raise PersistenceError("G4_RUNTIME_VISIT_SEQUENCE_INVALID", status=422)
            entries = tuple(wire(e) for e in session.scalars(select(JournalEntry).where(
                JournalEntry.stream_id == self.stream, JournalEntry.sequence <= upper, JournalEntry.kind == "visit").order_by(JournalEntry.sequence)))
            requests = tuple(wire(r) for r in session.scalars(select(IdempotentRequest).where(
                IdempotentRequest.stream_id == self.stream, IdempotentRequest.operation == "visit")))
            visits = confirmed_visits(entries, requests)
            return parse(VisitView, visits[-1]) if visits else None

    def detail(self, briefing_id, event_snapshot_id):
        self.require_ready()
        with self.store.read() as (session, _):
            snapshot = self.row(session, BriefingSnapshot, briefing_id)
            if sha256_bytes(json_bytes(snapshot.runtime)) != snapshot.runtime_sha256:
                raise PersistenceError("G4_SNAPSHOT_PAYLOAD_MISMATCH", status=503)
            matches = [a for a in snapshot.data["archive"] if a["event_snapshot_id"] == event_snapshot_id]
            if len(matches) != 1:
                raise PersistenceError("G4_EVENT_SNAPSHOT_NOT_FOUND", status=404)
            candidates = snapshot.runtime["context"]["replay"]["candidates"]
            candidate = next(c for c in candidates if c["snapshot"]["snapshot_id"] == event_snapshot_id)
            keys = set(candidate["bundle"]["current_claim_keys"] + candidate["bundle"]["historical_claim_keys"])
            evidence = snapshot.runtime["stages"][-1]["evidence"]["next_state"]
            claims = [c for c in evidence["claims"] if c["claim_key"] in keys]
            refs = {ref for c in claims for ref in c["evidence_ref_ids"]}
            citations = [c for c in evidence["citations"] if c["ref_id"] in refs]
            assessments = latest_assessments(
                [a for a in evidence["assessments"] if a["claim_key"] in keys], snapshot.as_of)
            members = set(candidate["event"]["member_doc_version_ids"]) | {c["doc_version_id"] for c in claims}
            document_ids = {d["document_id"] for d in snapshot.runtime["input"]["versions"] if d["doc_version_id"] in members}
            documents = [d for d in snapshot.runtime["input"]["versions"] if d["document_id"] in document_ids]
            return parse(EventDetailView, dict(briefing_id=briefing_id, snapshot_version=snapshot.version,
                as_of=snapshot.as_of, event=matches[0], candidate=candidate, documents=documents,
                claims=claims, citations=citations, assessments=assessments))

    def interaction(self, body):
        def apply(session, head):
            snapshot = self.row(session, BriefingSnapshot, body.briefing_id)
            if snapshot.version != body.expected_snapshot_version:
                raise PersistenceError("G4_SNAPSHOT_VERSION_CONFLICT")
            timestamp = self.clock()
            if body.client_occurred_at and not snapshot.generated_at <= body.client_occurred_at <= timestamp:
                raise PersistenceError("G4_INTERACTION_TIME_INVALID", status=422)
            target = session.get(DeliveryItem, body.target_id) or session.get(ArchiveItem, body.target_id)
            if target is None or target.snapshot_id != snapshot.id or target.stream_id != self.stream:
                raise PersistenceError("G4_INTERACTION_TARGET_INVALID")
            if body.kind == "rendered" and not isinstance(target, DeliveryItem):
                raise PersistenceError("G4_RENDERED_REQUIRES_DELIVERY")
            retracts = None
            if body.kind == "retract":
                retracts = self.row(session, InteractionRow, body.retracts_id)
                if (retracts.snapshot_id != snapshot.id or retracts.target_id != target.id
                        or retracts.kind not in {"ack", "dismiss"}):
                    raise PersistenceError("G4_RETRACTION_TARGET_INVALID")
                duplicate = session.scalar(select(InteractionRow).where(InteractionRow.retracts_id == retracts.id))
            elif body.kind in {"rendered", "opened"}:
                duplicate = session.scalar(select(InteractionRow).where(InteractionRow.stream_id == self.stream,
                    InteractionRow.observation_key == digest([snapshot.id, target.id, body.kind])))
            else:
                prior = list(session.scalars(select(InteractionRow).where(InteractionRow.stream_id == self.stream,
                    InteractionRow.snapshot_id == snapshot.id, InteractionRow.target_id == target.id,
                    InteractionRow.kind == body.kind).order_by(InteractionRow.available_at)))
                retracted = set(session.scalars(select(InteractionRow.retracts_id).where(
                    InteractionRow.stream_id == self.stream, InteractionRow.retracts_id.is_not(None))))
                duplicate = next((r for r in reversed(prior) if r.id not in retracted), None)
            if duplicate:
                return dict(resource_id=duplicate.id, deduplicated=True), [], {}
            row = InteractionRow(id=uuid4().hex, stream_id=self.stream, snapshot_id=snapshot.id,
                target_id=target.id, kind=body.kind,
                journal_sequence=head.sequence + 1, ordinal=0,
                observation_key=digest([snapshot.id, target.id, body.kind]) if body.kind in {"rendered", "opened"} else None,
                retracts_id=retracts.id if retracts else None, available_at=timestamp,
                data=dict(client_occurred_at=body.client_occurred_at,
                          persona_version_id=head.persona_version_id,
                          source="client_confirmation" if body.kind in {"rendered", "opened"} else "explicit_user"))
            session.add(row)
            return dict(resource_id=row.id), [row], {}
        return self._write(body, "interaction", apply)

    def interactions(self, as_of=None, *, limit=200, offset=0):
        self.require_ready()
        cutoff = self.cutoff(as_of)
        with self.store.read() as (session, _):
            rows = list(session.scalars(select(InteractionRow).where(InteractionRow.stream_id == self.stream,
                InteractionRow.available_at <= cutoff).order_by(InteractionRow.journal_sequence, InteractionRow.ordinal)
                .offset(offset).limit(limit)))
            return [parse(InteractionView, dict(id=r.id, briefing_id=r.snapshot_id, target_id=r.target_id,
                kind=r.kind, sequence=r.journal_sequence, ordinal=r.ordinal, available_at=r.available_at,
                retracts_id=r.retracts_id, **r.data)) for r in rows]

    def recover(self):
        with self.store.read() as (session, _):
            ids = list(session.scalars(select(BriefingRun.id).where(BriefingRun.stream_id == self.stream,
                BriefingRun.status.in_(["queued", "running"]))))
        for identifier in ids:
            self._terminal(identifier, "interrupted", ["G4_PROCESS_INTERRUPTED"])

    async def close(self):
        with self.computation_lock:
            self.closed = True
            self.worker_available = False
        for event in self.events.values():
            event.set()
        tasks = list(self.tasks.values())
        if tasks:
            done, pending = await asyncio.wait(tasks, timeout=self.settings.intelligence_timeout_seconds + 2)
            for task in pending:
                task.cancel()
            await asyncio.gather(*pending, return_exceptions=True)
        self.compute_pool.shutdown(wait=False, cancel_futures=True)
        with self.computation_lock:
            self.close_drained = True
            self.release_owner_if_drained()
        self.worker_available = False
