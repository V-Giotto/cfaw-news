"""Separate metadata: legacy Database.create() never silently migrates a user DB."""

from sqlalchemy import JSON, CheckConstraint, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class G4Base(DeclarativeBase):
    pass


class G4Migration(G4Base):
    __tablename__ = "g4_migrations"
    revision: Mapped[str] = mapped_column(String, primary_key=True)
    source_sha256: Mapped[str] = mapped_column(String)
    schema_sha256: Mapped[str] = mapped_column(String)
    installed_at: Mapped[str] = mapped_column(String)


class G4SourcePolicy(G4Base):
    __tablename__ = "g4_source_policies"
    policy_sha256: Mapped[str] = mapped_column(String, primary_key=True)
    source_id: Mapped[str] = mapped_column(String, index=True)
    registered_at: Mapped[str] = mapped_column(String)
    data: Mapped[dict] = mapped_column(JSON)


class G4Document(G4Base):
    __tablename__ = "g4_documents"
    document_id: Mapped[str] = mapped_column(String, primary_key=True)
    source_id: Mapped[str] = mapped_column(String)
    canonical_url: Mapped[str] = mapped_column(String)
    head_version_id: Mapped[str | None] = mapped_column(String, nullable=True)
    last_observed_at: Mapped[str | None] = mapped_column(String, nullable=True)
    __table_args__ = (UniqueConstraint("source_id", "canonical_url"),)


class G4Version(G4Base):
    __tablename__ = "g4_document_versions"
    doc_version_id: Mapped[str] = mapped_column(String, primary_key=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("g4_documents.document_id"), index=True)
    source_policy_sha256: Mapped[str] = mapped_column(ForeignKey("g4_source_policies.policy_sha256"))
    sequence: Mapped[int] = mapped_column(Integer)
    supersedes_version_id: Mapped[str | None] = mapped_column(
        ForeignKey("g4_document_versions.doc_version_id"), nullable=True, unique=True)
    observed_at: Mapped[str] = mapped_column(String)
    available_at: Mapped[str] = mapped_column(String)
    content_sha256: Mapped[str] = mapped_column(String)
    payload_sha256: Mapped[str] = mapped_column(String)
    record_sha256: Mapped[str] = mapped_column(String)
    data: Mapped[dict] = mapped_column(JSON)
    __table_args__ = (
        UniqueConstraint("document_id", "sequence"),
        CheckConstraint("sequence > 0 AND available_at >= observed_at"),
    )


class G4Capture(G4Base):
    __tablename__ = "g4_captures"
    capture_id: Mapped[str] = mapped_column(String, primary_key=True)
    source_id: Mapped[str] = mapped_column(String, index=True)
    observed_at: Mapped[str] = mapped_column(String)
    source_policy_sha256: Mapped[str] = mapped_column(ForeignKey("g4_source_policies.policy_sha256"))
    data: Mapped[dict] = mapped_column(JSON)


class G4Coverage(G4Base):
    __tablename__ = "g4_coverage_windows"
    coverage_window_id: Mapped[str] = mapped_column(String, primary_key=True)
    source_id: Mapped[str] = mapped_column(String, index=True)
    start_at: Mapped[str] = mapped_column(String)
    end_at: Mapped[str] = mapped_column(String)
    observed_at: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String)
    capture_id: Mapped[str | None] = mapped_column(ForeignKey("g4_captures.capture_id"))
    data: Mapped[dict] = mapped_column(JSON)
    __table_args__ = (CheckConstraint(
        "start_at <= end_at AND end_at <= observed_at AND "
        "status IN ('covered','partial','failed','unknown','service_offline')"),)


class G4ServiceEvent(G4Base):
    __tablename__ = "g4_service_events"
    event_id: Mapped[str] = mapped_column(String, primary_key=True)
    occurred_at: Mapped[str] = mapped_column(String, index=True)
    kind: Mapped[str] = mapped_column(String)
    __table_args__ = (CheckConstraint("kind IN ('started','stopped')"),)
