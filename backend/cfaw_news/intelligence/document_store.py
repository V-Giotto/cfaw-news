"""Atomic confirmed-feed capture. Callers own the transaction; never commits internally."""

from pathlib import Path
from uuid import uuid4

from sqlalchemy import select, text

from .contracts import (
    CoverageWindow,
    G4DocumentVersion,
    LedgerError,
    RetainedContent,
    SourcePolicy,
    canonical,
    check_capture_time,
    digest,
    instant,
    safe_url,
)
from .models import (
    G4Base,
    G4Capture,
    G4Coverage,
    G4Document,
    G4ServiceEvent,
    G4SourcePolicy,
    G4Version,
)
from .source_policy import policy_for


def write_lock(session):
    # SQLite serializes writers before we read a head (including separate processes).
    connection = session.connection()
    if not connection.connection.driver_connection.in_transaction:
        connection.exec_driver_sql("BEGIN IMMEDIATE")


def enabled(session):
    tables = set(session.scalars(text(
        "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'g4_%'")))
    if not tables:
        return False
    if tables != set(G4Base.metadata.tables):
        raise LedgerError("G4_MIGRATION_INCOMPLETE")
    from importlib import import_module
    revision = import_module(".migrations.001_g4_documents", __package__)
    installed = session.execute(text(
        "SELECT revision,source_sha256,schema_sha256 FROM g4_migrations")).all()
    if installed != [(revision.REVISION, revision.source_sha256(), revision.schema_sha256())]:
        raise LedgerError("G4_MIGRATION_PIN_MISMATCH")
    actual = session.execute(text(revision.SCHEMA_QUERY)).all()
    if actual != revision.expected_schema_rows(revision.source_sha256()):
        raise LedgerError("G4_MIGRATION_SCHEMA_MISMATCH")
    return True


def read_version(row):
    value = G4DocumentVersion.model_validate_json(canonical(row.data))
    pairs = {name: getattr(value, name) for name in (
        "doc_version_id", "document_id", "source_policy_sha256", "sequence",
        "supersedes_version_id", "observed_at", "available_at", "content_sha256", "payload_sha256")}
    if (any(getattr(row, k) != v for k, v in pairs.items())
            or row.record_sha256 != digest(row.data)):
        raise LedgerError("G4_CAPTURE_HASH_MISMATCH")
    return value


def register_policy(session, policy, now):
    policy = SourcePolicy.model_validate_json(policy.model_dump_json())
    data = policy.model_dump(mode="json")
    pin = digest(data)
    row = session.get(G4SourcePolicy, pin)
    if row is None:
        session.add(G4SourcePolicy(policy_sha256=pin, source_id=policy.source_id,
                                   registered_at=now, data=data))
        session.flush()
    elif row.data != data:
        raise LedgerError("G4_POLICY_HASH_MISMATCH")
    return pin


def retained(row, policy, legacy):
    if legacy or policy.rights in {"unknown", "metadata_only"} or not (
            {"excerpt", "fulltext"} & set(policy.allowed_use)):
        return "metadata_only", RetainedContent(title=policy.source_label)
    # Only the bounded RSS/API parser payload from THIS confirmed fetch is eligible.
    # ArticleReading/_reading, external web text and historical cache bodies are never read.
    limit = policy.max_excerpt_chars
    title = str(row["title"])[:min(512, limit)]
    remaining = limit - len(title)
    excerpt = str(row.get("summary") or "")[:remaining] or None
    remaining -= len(excerpt or "")
    paragraphs = []
    for part in row.get("paragraphs", []):
        value = str(part.get("text") or "")[:remaining]
        if value:
            paragraphs.append(value)
            remaining -= len(value)
    return ("bounded_feed_text" if "fulltext" in policy.allowed_use else "excerpt",
            RetainedContent(title=title, text_excerpt=excerpt, paragraphs=tuple(paragraphs)))


def capture_version(session, row, policy, *, observed_at, available_at, legacy=False):
    """Re-observing the current payload is idempotent; A→B→A is a new linear version."""
    write_lock(session)
    if row.get("source_id", policy.source_id) != policy.source_id:
        raise LedgerError("G4_CAPTURE_SOURCE_MISMATCH")
    observed, available = check_capture_time(observed_at, available_at)
    pin = register_policy(session, policy, observed)
    url = safe_url(row["source_url"])
    document_id = "g4doc:" + digest([policy.source_id, url])
    doc = session.get(G4Document, document_id)
    if doc is None:
        doc = G4Document(document_id=document_id, source_id=policy.source_id, canonical_url=url)
        session.add(doc)
        session.flush()
    versions = list(session.scalars(select(G4Version).where(
        G4Version.document_id == document_id).order_by(G4Version.sequence)))
    previous = None
    for number, version in enumerate(versions, 1):
        value = read_version(version)
        captured_policy = session.get(G4SourcePolicy, value.source_policy_sha256)
        if (captured_policy is None or digest(captured_policy.data) != value.source_policy_sha256
                or captured_policy.data["rights"] != value.rights
                or captured_policy.data["record_origin"] != value.record_origin
                or captured_policy.data["source_url"] != value.provenance_uri):
            raise LedgerError("G4_POLICY_HASH_MISMATCH")
        if value.sequence != number or value.supersedes_version_id != (
                previous.doc_version_id if previous else None):
            raise LedgerError("G4_CAPTURE_CHAIN_INVALID")
        previous = value
    if doc.head_version_id != (previous.doc_version_id if previous else None):
        raise LedgerError("G4_CAPTURE_CHAIN_INVALID")
    if doc.last_observed_at and observed < doc.last_observed_at:
        raise LedgerError("G4_CAPTURE_OUT_OF_ORDER")
    retention, content = retained(row, policy, legacy)
    # Hash current bounded parser input; do not persist forbidden source text.
    payload = {k: row.get(k) for k in ("title", "summary", "paragraphs", "published_at")}
    if legacy:
        payload = {"url": url, "source_id": policy.source_id, "legacy_metadata": True}
    payload_pin = digest(payload)
    content_pin = digest(content.model_dump(mode="json"))
    provenance = "legacy_cache_metadata_observed_now" if legacy else "confirmed_feed_capture"
    if previous and (previous.payload_sha256, previous.content_sha256,
                     previous.source_policy_sha256, previous.provenance) == (
                         payload_pin, content_pin, pin, provenance):
        doc.last_observed_at = observed
        session.flush()
        return previous
    if previous and (observed <= doc.last_observed_at or available < previous.available_at):
        raise LedgerError("G4_CAPTURE_OUT_OF_ORDER")
    data = dict(document_id=document_id, doc_version_id="g4ver:" + digest([
        document_id, doc.head_version_id, observed, available, payload_pin, content_pin, pin]),
        source_id=policy.source_id, source_policy_sha256=pin, source_article_id=row.get("id"),
        canonical_url=url, content_kind="synthetic_text" if policy.record_origin == "synthetic"
        else "feed_summary", rights=policy.rights, record_origin=policy.record_origin,
        provenance=provenance, provenance_uri=policy.source_url, observed_at=observed,
        available_at=available, published_at=row.get("published_at"),
        content_sha256=content_pin, payload_sha256=payload_pin,
        supersedes_version_id=doc.head_version_id, sequence=len(versions) + 1,
        retention=retention, content=content.model_dump(mode="json"))
    value = G4DocumentVersion.model_validate_json(canonical(data))
    data = value.model_dump(mode="json")
    session.add(G4Version(**{k: data[k] for k in (
        "doc_version_id", "document_id", "source_policy_sha256", "sequence",
        "supersedes_version_id", "observed_at", "available_at", "content_sha256", "payload_sha256")},
        record_sha256=digest(data), data=data))
    session.flush()  # Linear-chain SQL trigger and FK constraints run before head changes.
    doc.head_version_id, doc.last_observed_at = value.doc_version_id, observed
    session.flush()
    return value


def add_coverage(session, source_id, start, end, observed, status, reason, capture_id=None):
    data = dict(source_id=source_id, start_at=instant(start), end_at=instant(end),
                observed_at=instant(observed), status=status, reason_code=reason)
    data["coverage_window_id"] = "g4cov:" + digest([data, capture_id])
    value = CoverageWindow.model_validate_json(canonical(data))
    key = value.coverage_window_id
    if session.get(G4Coverage, key) is None:
        session.add(G4Coverage(**{k: getattr(value, k) for k in (
            "coverage_window_id", "source_id", "start_at", "end_at", "observed_at", "status")},
            capture_id=capture_id, data=value.model_dump(mode="json")))
        session.flush()
    return value


class DocumentLedger:
    def __init__(self, root: Path):
        self.registry = root / "data/g4_source_policies.json"

    def policy(self, source):
        return policy_for(source, self.registry)

    def has_snapshot(self, session, source):
        pin = digest(self.policy(source).model_dump(mode="json"))
        return session.scalar(select(G4Capture.capture_id).where(
            G4Capture.source_id == source["id"], G4Capture.source_policy_sha256 == pin,
            G4Capture.data["outcome"].as_string() == "success").limit(1)) is not None

    def record_poll(self, session, source, rows, *, started_at, observed_at, available_at,
                    failed=False):
        write_lock(session)
        policy = self.policy(source)
        start, now = instant(started_at), instant(observed_at)
        check_capture_time(now, available_at)
        if start > now:
            raise LedgerError("G4_CAPTURE_INVALID_TIME")
        pin = register_policy(session, policy, now)
        capture_id = "g4poll:" + digest([source["id"], start, now])
        old = session.get(G4Capture, capture_id)
        outcome = "failed" if failed else "not_modified" if rows is None else "success"
        row_pins = None if rows is None else [digest({k: r.get(k) for k in (
            "id", "source_url", "title", "summary", "paragraphs", "published_at")}) for r in rows]
        if old:
            if (old.data["row_pins"], old.data["outcome"], old.source_policy_sha256) != (
                    row_pins, outcome, pin):
                raise LedgerError("G4_CAPTURE_ID_CONFLICT")
            return old.data["version_ids"]
        previous = session.scalar(select(G4Capture).where(G4Capture.source_id == source["id"])
                                  .order_by(G4Capture.observed_at.desc()).limit(1))
        if previous and start < previous.observed_at:
            raise LedgerError("G4_CAPTURE_OUT_OF_ORDER")
        anchored = self.has_snapshot(session, source)
        versions = [] if failed else [capture_version(session, row, policy,
            observed_at=now, available_at=available_at).doc_version_id for row in rows or []]
        data = dict(schema_revision="g4-capture-receipt-v1", outcome=outcome,
                    version_ids=versions, row_pins=row_pins, started_at=start,
                    observed_at=now, available_at=instant(available_at))
        session.add(G4Capture(capture_id=capture_id, source_id=source["id"],
                             observed_at=now, source_policy_sha256=pin, data=data))
        session.flush()
        if previous and start > previous.observed_at:
            add_coverage(session, source["id"], previous.observed_at, start, now, "unknown",
                         "unobserved_between_polls", capture_id)
        status, reason = (("failed", "source_failed") if failed else (
            ("partial", "bounded_parse") if rows is not None else (
                ("covered", "conditional_confirmed") if anchored else
                ("unknown", "conditional_unanchored"))))
        add_coverage(session, source["id"], start if failed else now, now, now, status, reason,
                     capture_id)
        return versions

    def service_event(self, session, sources, kind, now):
        write_lock(session)
        now = instant(now)
        check_capture_time(now, now)
        previous = session.scalar(select(G4ServiceEvent).order_by(
            G4ServiceEvent.occurred_at.desc()).limit(1))
        if previous and now <= previous.occurred_at:
            raise LedgerError("G4_CAPTURE_OUT_OF_ORDER")
        if kind == "started" and previous:
            status = "service_offline" if previous.kind == "stopped" else "unknown"
            reason = "clean_service_downtime" if previous.kind == "stopped" else (
                "unclean_service_restart")
            for source in sources:
                add_coverage(session, source["id"], previous.occurred_at, now, now, status, reason)
        session.add(G4ServiceEvent(event_id=uuid4().hex, occurred_at=now, kind=kind))
