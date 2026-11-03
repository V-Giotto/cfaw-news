"""Independent metadata: explicit PR4 migration, never legacy Base.create()."""

from sqlalchemy import JSON, Boolean, CheckConstraint, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class PersistenceBase(DeclarativeBase):
    pass


class Installation(PersistenceBase):
    __tablename__ = "intelligence_installation"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    database_id: Mapped[str] = mapped_column(String)
    revision: Mapped[str] = mapped_column(String)
    source_sha256: Mapped[str] = mapped_column(String)
    schema_sha256: Mapped[str] = mapped_column(String)


class TrustedHead(PersistenceBase):
    __tablename__ = "intelligence_heads"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    sequence: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String)
    latest_snapshot_id: Mapped[str | None] = mapped_column(String, nullable=True)
    publication_version: Mapped[int] = mapped_column(Integer, default=0)
    persona_version_id: Mapped[str | None] = mapped_column(String, nullable=True)
    __table_args__ = (CheckConstraint("sequence >= 0 AND publication_version >= 0"),)


class JournalEntry(PersistenceBase):
    __tablename__ = "intelligence_entries"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    stream_id: Mapped[str] = mapped_column(ForeignKey("intelligence_heads.id"), index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    previous_sha256: Mapped[str] = mapped_column(String)
    kind: Mapped[str] = mapped_column(String)
    created_at: Mapped[str] = mapped_column(String)
    data: Mapped[dict] = mapped_column(JSON)
    __table_args__ = (UniqueConstraint("stream_id", "sequence"), CheckConstraint("sequence > 0"))


class IdempotentRequest(PersistenceBase):
    __tablename__ = "intelligence_requests"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    stream_id: Mapped[str] = mapped_column(ForeignKey("intelligence_heads.id"), index=True)
    key: Mapped[str] = mapped_column(String)
    operation: Mapped[str] = mapped_column(String)
    request_sha256: Mapped[str] = mapped_column(String)
    data: Mapped[dict] = mapped_column(JSON)
    __table_args__ = (UniqueConstraint("stream_id", "key"),)


class PersonaVersionRow(PersistenceBase):
    __tablename__ = "intelligence_persona_versions"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    stream_id: Mapped[str] = mapped_column(ForeignKey("intelligence_heads.id"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    available_at: Mapped[str] = mapped_column(String)
    data: Mapped[dict] = mapped_column(JSON)
    __table_args__ = (UniqueConstraint("stream_id", "version"), CheckConstraint("version > 0"))


class BriefingRun(PersistenceBase):
    __tablename__ = "intelligence_runs"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    stream_id: Mapped[str] = mapped_column(ForeignKey("intelligence_heads.id"), index=True)
    status: Mapped[str] = mapped_column(String, index=True)
    version: Mapped[int] = mapped_column(Integer)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[str] = mapped_column(String)
    input_sha256: Mapped[str] = mapped_column(String)
    input: Mapped[dict] = mapped_column(JSON, deferred=True)
    data: Mapped[dict] = mapped_column(JSON)
    __table_args__ = (CheckConstraint("version > 0"), CheckConstraint(
        "status IN ('queued','running','completed','cancelled','failed','stale','timed_out',"
        "'interrupted','evidence_not_ready')"))


class BriefingSnapshot(PersistenceBase):
    __tablename__ = "intelligence_snapshots"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    stream_id: Mapped[str] = mapped_column(ForeignKey("intelligence_heads.id"), index=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("intelligence_runs.id"), unique=True)
    version: Mapped[int] = mapped_column(Integer)
    as_of: Mapped[str] = mapped_column(String)
    generated_at: Mapped[str] = mapped_column(String)
    runtime_sha256: Mapped[str] = mapped_column(String)
    runtime: Mapped[dict] = mapped_column(JSON, deferred=True)
    data: Mapped[dict] = mapped_column(JSON)
    __table_args__ = (UniqueConstraint("stream_id", "version"), CheckConstraint("version > 0"))


class DeliveryItem(PersistenceBase):
    __tablename__ = "intelligence_delivery_items"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    stream_id: Mapped[str] = mapped_column(ForeignKey("intelligence_heads.id"), index=True)
    snapshot_id: Mapped[str] = mapped_column(ForeignKey("intelligence_snapshots.id"), index=True)
    event_snapshot_id: Mapped[str] = mapped_column(String)
    ordinal: Mapped[int] = mapped_column(Integer)
    data: Mapped[dict] = mapped_column(JSON)
    __table_args__ = (UniqueConstraint("snapshot_id", "event_snapshot_id"),)


class ArchiveItem(PersistenceBase):
    __tablename__ = "intelligence_archive_items"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    stream_id: Mapped[str] = mapped_column(ForeignKey("intelligence_heads.id"), index=True)
    snapshot_id: Mapped[str] = mapped_column(ForeignKey("intelligence_snapshots.id"), index=True)
    event_snapshot_id: Mapped[str] = mapped_column(String)
    data: Mapped[dict] = mapped_column(JSON)
    __table_args__ = (UniqueConstraint("snapshot_id", "event_snapshot_id"),)


class InteractionRow(PersistenceBase):
    __tablename__ = "intelligence_interactions"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    stream_id: Mapped[str] = mapped_column(ForeignKey("intelligence_heads.id"), index=True)
    snapshot_id: Mapped[str] = mapped_column(ForeignKey("intelligence_snapshots.id"), index=True)
    target_id: Mapped[str] = mapped_column(String)
    kind: Mapped[str] = mapped_column(String)
    journal_sequence: Mapped[int] = mapped_column(Integer)
    ordinal: Mapped[int] = mapped_column(Integer)
    observation_key: Mapped[str | None] = mapped_column(String, unique=True, nullable=True)
    retracts_id: Mapped[str | None] = mapped_column(ForeignKey("intelligence_interactions.id"), unique=True, nullable=True)
    available_at: Mapped[str] = mapped_column(String)
    data: Mapped[dict] = mapped_column(JSON)
    __table_args__ = (UniqueConstraint("stream_id", "journal_sequence", "ordinal"),
                     CheckConstraint("journal_sequence > 0 AND ordinal >= 0"),
                     CheckConstraint("kind IN ('included','rendered','opened','ack','dismiss','retract')"))


RECORD_MODELS = (IdempotentRequest, PersonaVersionRow, BriefingRun, BriefingSnapshot,
                 DeliveryItem, ArchiveItem, InteractionRow)
MODELS = {m.__tablename__: m for m in RECORD_MODELS}
