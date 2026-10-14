import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from sqlalchemy import JSON, Boolean, ForeignKey, Integer, String, Text, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from sqlalchemy.pool import StaticPool


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def identifier() -> str:
    return uuid4().hex


def fingerprint(value) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


class Base(DeclarativeBase):
    pass


class Goal(Base):
    __tablename__ = "goals"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=identifier)
    version: Mapped[int] = mapped_column(default=1)
    status: Mapped[str] = mapped_column(default="active")
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    data: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[str] = mapped_column(default=utcnow)


class Article(Base):
    __tablename__ = "articles"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    content_hash: Mapped[str] = mapped_column(String)
    origin: Mapped[str] = mapped_column(String)
    data: Mapped[dict] = mapped_column(JSON)


class Run(Base):
    __tablename__ = "runs"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=identifier)
    goal_id: Mapped[str] = mapped_column(ForeignKey("goals.id"), index=True)
    goal_version: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(default="queued", index=True)
    mode: Mapped[str] = mapped_column(String)
    snapshot: Mapped[dict] = mapped_column(JSON)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    basis_hash: Mapped[str] = mapped_column(String)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[str] = mapped_column(default=utcnow, index=True)
    finished_at: Mapped[str | None] = mapped_column(nullable=True)
    metrics: Mapped[dict] = mapped_column(JSON, default=dict)


class RunEvent(Base):
    __tablename__ = "run_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), index=True)
    kind: Mapped[str] = mapped_column(String)
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(default=utcnow)


class Decision(Base):
    __tablename__ = "decisions"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=identifier)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), unique=True)
    goal_id: Mapped[str] = mapped_column(ForeignKey("goals.id"), index=True)
    goal_version: Mapped[int] = mapped_column(Integer)
    basis_hash: Mapped[str] = mapped_column(String)
    choice: Mapped[str] = mapped_column(String)
    reason: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[str] = mapped_column(default=utcnow)


class Schedule(Base):
    __tablename__ = "schedules"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=identifier)
    proposal_key: Mapped[str] = mapped_column(String, unique=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"))
    title: Mapped[str] = mapped_column(String)
    content: Mapped[str] = mapped_column(Text)
    start: Mapped[str] = mapped_column(String)
    end: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(default="planned")
    created_at: Mapped[str] = mapped_column(default=utcnow)


class Meta(Base):
    __tablename__ = "meta"
    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[str] = mapped_column(String)


class Database:
    def __init__(self, url: str):
        options = {}
        if url.startswith("sqlite"):
            options["connect_args"] = {"check_same_thread": False, "timeout": 15}
            if ":memory:" in url:
                options["poolclass"] = StaticPool
            else:
                Path(url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_engine(url, **options)
        if url.startswith("sqlite"):

            @event.listens_for(self.engine, "connect")
            def configure_sqlite(connection, _):
                connection.execute("PRAGMA foreign_keys=ON")
                connection.execute("PRAGMA journal_mode=WAL")

        self.session = sessionmaker(self.engine, expire_on_commit=False)

    def create(self):
        Base.metadata.create_all(self.engine)


def add_event(session, run_id: str, kind: str, message: str):
    session.add(RunEvent(run_id=run_id, kind=kind, message=message))


def goal_dict(goal: Goal) -> dict:
    return {
        **goal.data,
        "id": goal.id,
        "version": goal.version,
        "status": goal.status,
        "is_demo": goal.is_demo,
        "created_at": goal.created_at,
    }


def run_dict(run: Run, *, include_snapshot=True) -> dict:
    result = {
        "id": run.id,
        "goal_id": run.goal_id,
        "goal_version": run.goal_version,
        "status": run.status,
        "mode": run.mode,
        "result": run.result,
        "error": run.error,
        "created_at": run.created_at,
        "finished_at": run.finished_at,
        "metrics": run.metrics,
    }
    if include_snapshot:
        result["snapshot"] = run.snapshot
    return result
