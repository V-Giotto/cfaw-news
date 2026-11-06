"""G4 real-origin protocol adapter for the unchanged G3 history kernels.

SQLite rows and the complete trusted journal prefix are bound before projection.
Archive metadata feedback is retained for audit/visits, never turned into a delivery.
"""

from datetime import datetime, timedelta
from typing import Annotated, Literal

from pydantic import Field, model_validator

from evals.intelligence_g2.contracts import data, digest, json_bytes
from evals.intelligence_g3.contracts import DeliverySnapshot, PublishedItemRef
from evals.intelligence_v1.contracts import Delivery, Instant, NonEmpty, StrictModel
from evals.intelligence_v1.hashing import sha256_bytes

from .contracts import Hash, LedgerError

TABLES = ("intelligence_persona_versions", "intelligence_snapshots", "intelligence_delivery_items",
          "intelligence_interactions", "intelligence_requests")


class PrefixRecord(StrictModel):
    table: Literal["intelligence_persona_versions", "intelligence_snapshots", "intelligence_delivery_items",
                   "intelligence_interactions", "intelligence_requests"]
    row: dict


class SnapshotBasis(StrictModel):
    snapshot_id: NonEmpty
    basis: dict
    # Only pre-v2 snapshots need their original runtime as a witness. New snapshots
    # commit the native basis in their immutable, journal-bound view instead.
    legacy_runtime: dict | None = None


class RuntimePrefix(StrictModel):
    schema_revision: Literal["g4-runtime-persisted-prefix-v1"] = "g4-runtime-persisted-prefix-v1"
    database_id: NonEmpty
    stream_id: NonEmpty
    epoch: NonEmpty
    sequence: Annotated[int, Field(ge=0)]
    sha256: Hash
    entries: Annotated[tuple[dict, ...], Field(max_length=20000)]
    records: Annotated[tuple[PrefixRecord, ...], Field(max_length=12000)]
    snapshots: Annotated[tuple[SnapshotBasis, ...], Field(max_length=128)] = ()

    def rows(self, table):
        return tuple(r.row for r in self.records if r.table == table)


class VisitWindow(StrictModel):
    basis: Literal["explicit_request", "last_confirmed_interaction", "last_confirmed_home_visit", "first_visit_default", "clamped_last_visit"]
    last_confirmed_visit_at: Instant | None = None
    through_sequence: Annotated[int, Field(ge=0)] | None = None
    start_at: Instant
    end_at: Instant


class RuntimeHistoryEvent(StrictModel):
    interaction_id: NonEmpty
    persona_id: NonEmpty
    delivery_id: NonEmpty
    target: PublishedItemRef
    kind: Literal["included", "rendered", "opened", "acknowledged", "dismissed", "retract"]
    feedback: None = None
    retracts_id: NonEmpty | None = None
    occurred_at: Instant
    available_at: Instant
    source: Literal["server", "client", "explicit_user"]
    source_id: NonEmpty
    record_origin: Literal["real", "synthetic"]
    provenance_uri: NonEmpty


class RuntimeJournalEntry(StrictModel):
    sequence: int
    previous_sha256: Hash | None
    event: RuntimeHistoryEvent
    source_sequence: int
    source_ordinal: int
    sha256: Hash


class RuntimeJournal(StrictModel):
    schema_revision: Literal["g4-native-history-journal-v1"] = "g4-native-history-journal-v1"
    entries: tuple[RuntimeJournalEntry, ...] = ()
    ignored_archive_interaction_ids: tuple[NonEmpty, ...] = ()
    status: Literal["validated_sqlite_prefix_native_rules_v1"] = "validated_sqlite_prefix_native_rules_v1"

    @model_validator(mode="after")
    def chain(self):
        previous, seen, retracted = None, {}, set()
        for i, entry in enumerate(self.entries, 1):
            event = entry.event
            if (entry.sequence != i or entry.previous_sha256 != previous
                    or entry.sha256 != digest(entry.model_dump(mode="json", exclude={"sha256"}))
                    or event.interaction_id in seen or event.target.as_of > event.occurred_at
                    or event.occurred_at > event.available_at
                    or (self.entries[i - 2].event.available_at > event.available_at if i > 1 else False)):
                raise LedgerError("G4_NATIVE_HISTORY_CHAIN_INVALID")
            if event.kind == "retract":
                old = seen.get(event.retracts_id)
                if (old is None or old.kind not in {"acknowledged", "dismissed"}
                        or old.interaction_id in retracted or old.target != event.target
                        or old.delivery_id != event.delivery_id or old.persona_id != event.persona_id
                        or old.occurred_at > event.occurred_at):
                    raise LedgerError("G4_NATIVE_HISTORY_RETRACTION_INVALID")
                retracted.add(old.interaction_id)
            elif event.retracts_id is not None:
                raise LedgerError("G4_NATIVE_HISTORY_RETRACTION_INVALID")
            seen[event.interaction_id], previous = event, entry.sha256
        return self


def native_basis(value):
    result = data(value) if not isinstance(value, dict) else dict(value)
    result.pop("history_prefix", None)
    return result


def validate_prefix(value):
    try:
        return _validate_prefix(value)
    except LedgerError:
        raise
    except (KeyError, TypeError, ValueError, IndexError):
        raise LedgerError("G4_RUNTIME_HISTORY_PREFIX_INVALID") from None


def _validate_prefix(value):
    """Verify complete row membership against the queued transaction's trusted head."""
    from .history_store import entry_pin, genesis
    prefix = value.history_prefix
    if prefix is None:
        raise LedgerError("G4_RUNTIME_HISTORY_PREFIX_REQUIRED")
    if prefix.stream_id != value.stream_id:
        raise LedgerError("G4_RUNTIME_HISTORY_STREAM_MISMATCH")
    previous, expected, prior_time = genesis(prefix.database_id, prefix.stream_id), {}, None
    for i, entry in enumerate(prefix.entries, 1):
        when = datetime.fromisoformat(entry["created_at"])
        if (entry["stream_id"] != prefix.stream_id or entry["sequence"] != i
                or entry["previous_sha256"] != previous or when > value.as_of
                or prior_time is not None and when < prior_time
                or entry["id"] != entry_pin(prefix.stream_id, i, previous, entry["kind"], entry["created_at"], entry["data"])):
            raise LedgerError("G4_RUNTIME_HISTORY_PREFIX_INVALID")
        for row in entry["data"]["records"]:
            expected[(row["table"], row["id"])] = row["sha256"]
        previous, prior_time = entry["id"], when
    if len(prefix.entries) != prefix.sequence or prefix.sha256 != previous:
        raise LedgerError("G4_RUNTIME_HISTORY_PREFIX_INVALID")
    if not prefix.entries or prefix.entries[-1]["data"]["state"]["persona_version_id"] != value.persona.persona.persona_version_id:
        raise LedgerError("G4_RUNTIME_PERSONA_HISTORY_REQUIRED")
    actual = {}
    for proof in prefix.records:
        row = proof.row
        key = (proof.table, row["id"])
        if key in actual or row["stream_id"] != value.stream_id:
            raise LedgerError("G4_RUNTIME_HISTORY_RECORD_INVALID")
        actual[key] = digest(row)
    if actual != {k: v for k, v in expected.items() if k[0] in TABLES}:
        raise LedgerError("G4_RUNTIME_HISTORY_RECORD_INVALID")
    personas = sorted(prefix.rows(TABLES[0]), key=lambda p: p["version"])
    if (not personas or [p["version"] for p in personas] != list(range(1, len(personas) + 1))
            or [p["data"]["native"] for p in personas] != [data(p) for p in value.persona_history]):
        raise LedgerError("G4_RUNTIME_PERSONA_HISTORY_REQUIRED")
    prior = None
    for row, persona in zip(personas, value.persona_history, strict=True):
        p = persona.persona
        if (p.persona_version_id != row["id"] or p.available_at != datetime.fromisoformat(row["available_at"])
                or p.available_at > value.as_of or prior is not None and p.available_at < prior
                or persona.record_origin != value.record_origin or p.persona_id != value.persona.persona.persona_id):
            raise LedgerError("G4_RUNTIME_PERSONA_HISTORY_REQUIRED")
        prior = p.available_at
    if value.persona != value.persona_history[-1]:
        raise LedgerError("G4_RUNTIME_PERSONA_HISTORY_REQUIRED")
    snapshots = {p["id"]: p for p in prefix.rows(TABLES[1])}
    deliveries = {p["id"]: p for p in prefix.rows(TABLES[2])}
    for row in snapshots.values():
        if (not datetime.fromisoformat(row["as_of"]) <= datetime.fromisoformat(row["generated_at"]) <= value.as_of
                or row["data"]["id"] != row["id"] or row["data"]["version"] != row["version"]
                or row["data"]["mode"] != ("real" if value.record_origin == "real" else "synthetic_development")):
            raise LedgerError("G4_RUNTIME_HISTORY_SNAPSHOT_INVALID")
    for row in deliveries.values():
        snapshot = snapshots.get(row["snapshot_id"])
        if (snapshot is None or row["data"] not in snapshot["data"]["deliveries"]
                or row["data"]["id"] != row["id"] or row["event_snapshot_id"] != row["data"]["event_snapshot_id"]
                or row["ordinal"] != row["data"]["ordinal"]):
            raise LedgerError("G4_RUNTIME_HISTORY_DELIVERY_INVALID")
    interactions = {}
    for row in sorted(prefix.rows(TABLES[3]), key=lambda r: (r["journal_sequence"], r["ordinal"])):
        snapshot = snapshots.get(row["snapshot_id"])
        if snapshot is None or not datetime.fromisoformat(snapshot["generated_at"]) <= datetime.fromisoformat(row["available_at"]) <= value.as_of:
            raise LedgerError("G4_RUNTIME_HISTORY_RECORD_INVALID")
        target = deliveries.get(row["target_id"])
        archive = next((a for a in snapshot["data"]["archive"] if a["id"] == row["target_id"]), None)
        if (target is None and archive is None or target is not None and target["snapshot_id"] != snapshot["id"]
                or row["kind"] in {"included", "rendered"} and target is None):
            raise LedgerError("G4_RUNTIME_HISTORY_TARGET_INVALID")
        expected_source = "server_publication" if row["kind"] == "included" else "client_confirmation" if row["kind"] in {"rendered", "opened"} else "explicit_user"
        sequence = row["journal_sequence"]
        if (not 1 <= sequence <= prefix.sequence or row["data"]["source"] != expected_source
                or prefix.entries[sequence - 1]["data"]["state"]["persona_version_id"] != row["data"]["persona_version_id"]
                or row["id"] not in {r["id"] for r in prefix.entries[sequence - 1]["data"]["records"] if r["table"] == TABLES[3]}):
            raise LedgerError("G4_RUNTIME_HISTORY_SOURCE_INVALID")
        occurred = datetime.fromisoformat(row["data"].get("client_occurred_at") or row["available_at"])
        if not datetime.fromisoformat(snapshot["generated_at"]) <= occurred <= datetime.fromisoformat(row["available_at"]):
            raise LedgerError("G4_RUNTIME_HISTORY_RECORD_INVALID")
        if row["kind"] == "retract":
            old = interactions.get(row["retracts_id"])
            if old is None or old["kind"] not in {"ack", "dismiss"} or (old["snapshot_id"], old["target_id"]) != (row["snapshot_id"], row["target_id"]):
                raise LedgerError("G4_RUNTIME_HISTORY_TARGET_INVALID")
        interactions[row["id"]] = row
    needed = {d["snapshot_id"] for d in deliveries.values()}
    if {p.snapshot_id for p in prefix.snapshots} != needed or len(prefix.snapshots) != len(needed):
        raise LedgerError("G4_RUNTIME_HISTORY_SNAPSHOT_REQUIRED")
    return prefix


def confirmed_visits(entries, requests):
    by_id = {r["id"]: r for r in requests}
    visits = []
    for entry in entries:
        if entry["kind"] != "visit":
            continue
        for proof in entry["data"]["records"]:
            request = by_id.get(proof["id"]) if proof["table"] == TABLES[4] else None
            if request is None or request["operation"] != "visit" or request["data"].get("deduplicated"):
                continue
            visit = request["data"].get("visit")
            if not visit or visit.get("confirmation") != "home_visible":
                raise LedgerError("G4_RUNTIME_VISIT_CONFIRMATION_INVALID")
            visits.append(dict(id=request["data"]["resource_id"], available_at=entry["created_at"],
                sequence=entry["sequence"], briefing_id=visit.get("briefing_id")))
    return visits


def visit_window(prefix, as_of, explicit=None, through_sequence=None):
    upper = prefix.sequence if through_sequence is None else through_sequence
    if not 0 <= upper <= prefix.sequence:
        raise LedgerError("G4_RUNTIME_VISIT_SEQUENCE_INVALID")
    rows = [(r["available_at"], r["journal_sequence"], "last_confirmed_interaction") for r in prefix.rows(TABLES[3])
            if r["kind"] != "included" and r["journal_sequence"] <= upper]
    visits = [(v["available_at"], v["sequence"], "last_confirmed_home_visit")
              for v in confirmed_visits(prefix.entries, prefix.rows(TABLES[4])) if v["sequence"] <= upper]
    if visits:
        rows = visits  # New visibility receipts define visits; old interactions are a legacy fallback only.
    chosen = max(rows, key=lambda r: (datetime.fromisoformat(r[0]), r[1]), default=None)
    latest = datetime.fromisoformat(chosen[0]) if chosen else None
    start = explicit or latest or as_of - timedelta(days=1)
    reason = "explicit_request" if explicit is not None else chosen[2] if chosen else "first_visit_default"
    if explicit is None and start < as_of - timedelta(days=30):
        start, reason = as_of - timedelta(days=30), "clamped_last_visit"
    return VisitWindow(basis=reason, last_confirmed_visit_at=latest, through_sequence=through_sequence,
                       start_at=start, end_at=as_of)


def load_prefix(session, head, epoch):
    """Called inside the same verified SQLite transaction as run-input capture."""
    from sqlalchemy import select

    from .history_store import wire
    from .persistence_models import (
        BriefingSnapshot,
        DeliveryItem,
        IdempotentRequest,
        Installation,
        InteractionRow,
        JournalEntry,
        PersonaVersionRow,
    )
    records, proofs = [], []
    for model in (PersonaVersionRow, BriefingSnapshot, DeliveryItem, InteractionRow, IdempotentRequest):
        records.extend(PrefixRecord(table=model.__tablename__, row=wire(row)) for row in session.scalars(
            select(model).where(model.stream_id == head.id).order_by(model.id)))
    needed = {r.row["snapshot_id"] for r in records if r.table == TABLES[2]}
    for identifier in sorted(needed):
        row = session.get(BriefingSnapshot, identifier)
        body = row.runtime
        if sha256_bytes(json_bytes(body)) != row.runtime_sha256:
            raise LedgerError("G4_SNAPSHOT_PAYLOAD_MISMATCH")
        proofs.append(SnapshotBasis(snapshot_id=identifier, basis=native_basis(body["input"]),
            legacy_runtime=body if not row.data.get("native_basis_sha256") else None))
    entries = tuple(wire(e) for e in session.scalars(select(JournalEntry).where(
        JournalEntry.stream_id == head.id, JournalEntry.sequence <= head.sequence).order_by(JournalEntry.sequence)))
    return RuntimePrefix(database_id=session.get(Installation, "database").database_id,
        stream_id=head.id, epoch=epoch, sequence=head.sequence, sha256=head.sha256,
        entries=entries, records=tuple(records), snapshots=tuple(proofs))


def project_history(value, checkpoint):
    """Rebuild delivered evidence from its committed native basis, not current bodies."""
    from .g2_adapter import run_native
    from .runtime_contracts import RuntimeEnvelope
    prefix = validate_prefix(value)
    snapshots = {p["id"]: p for p in prefix.rows(TABLES[1])}
    observations, delivered, refs = [], [], {}
    for proof in prefix.snapshots:
        checkpoint("history_snapshot")
        row = snapshots[proof.snapshot_id]
        basis = RuntimeEnvelope.model_validate_json(json_bytes(proof.basis))
        if basis.as_of != datetime.fromisoformat(row["as_of"]) or basis.stream_id != value.stream_id or basis.record_origin != value.record_origin:
            raise LedgerError("G4_RUNTIME_HISTORY_SNAPSHOT_INVALID")
        if row["data"].get("native_basis_sha256"):
            if digest(native_basis(basis)) != row["data"]["native_basis_sha256"] or proof.legacy_runtime is not None:
                raise LedgerError("G4_RUNTIME_HISTORY_SNAPSHOT_INVALID")
        else:
            legacy = proof.legacy_runtime
            if (legacy is None or sha256_bytes(json_bytes(legacy)) != row["runtime_sha256"]
                    or legacy["input"] != proof.basis):
                raise LedgerError("G4_RUNTIME_HISTORY_SNAPSHOT_INVALID")
        stages, old, _, _ = run_native(basis, sha256_bytes(json_bytes(basis)), checkpoint)
        if proof.legacy_runtime is not None and [data(s) for s in stages] != proof.legacy_runtime["stages"]:
            raise LedgerError("G4_RUNTIME_HISTORY_SNAPSHOT_INVALID")
        observations.extend(old)
        candidates = {c.snapshot.snapshot_id: c for c in old[-1].candidates}
        items = []
        for record in prefix.rows(TABLES[2]):
            if record["snapshot_id"] != proof.snapshot_id:
                continue
            item = record["data"]
            candidate = candidates.get(item["event_snapshot_id"])
            if (candidate is None or candidate.event.event_key != item["event_key"]
                    or candidate.event.event_revision != item["event_revision"]
                    or candidate.rule_item.tier_candidate == "hold"):
                raise LedgerError("G4_RUNTIME_HISTORY_DELIVERY_INVALID")
            ref = PublishedItemRef(event_key=candidate.event.event_key, event_revision=candidate.event.event_revision,
                item_id=candidate.rule_item.item_id, snapshot_id=candidate.snapshot.snapshot_id, as_of=basis.as_of)
            refs[record["id"]] = ref
            items.append(ref)
        delivered.append(DeliverySnapshot(delivery=Delivery(delivery_id=row["id"], as_of=basis.as_of,
            generated_at=datetime.fromisoformat(row["generated_at"])), available_at=datetime.fromisoformat(row["generated_at"]),
            persona_id=value.persona.persona.persona_id, items=tuple(items), record_origin=value.record_origin,
            provenance_uri="local-sqlite:snapshot:" + row["id"]))
    entries, ignored, previous = [], [], None
    for row in sorted(prefix.rows(TABLES[3]), key=lambda r: (r["journal_sequence"], r["ordinal"])):
        if row["target_id"] not in refs:
            ignored.append(row["id"])
            continue
        kind = {"ack": "acknowledged", "dismiss": "dismissed"}.get(row["kind"], row["kind"])
        event = RuntimeHistoryEvent(interaction_id=row["id"], persona_id=value.persona.persona.persona_id,
            delivery_id=row["snapshot_id"], target=refs[row["target_id"]], kind=kind, retracts_id=row["retracts_id"],
            occurred_at=row["data"].get("client_occurred_at") or row["available_at"], available_at=row["available_at"],
            source="server" if kind == "included" else "client" if kind in {"rendered", "opened"} else "explicit_user",
            source_id=row["id"], record_origin=value.record_origin, provenance_uri="local-sqlite:interaction:" + row["id"])
        body = dict(sequence=len(entries) + 1, previous_sha256=previous, event=data(event),
                    source_sequence=row["journal_sequence"], source_ordinal=row["ordinal"])
        entry = RuntimeJournalEntry(**body, sha256=digest(body))
        entries.append(entry)
        previous = entry.sha256
    return (tuple(delivered), tuple(observations), RuntimeJournal(entries=tuple(entries),
        ignored_archive_interaction_ids=tuple(ignored)))
