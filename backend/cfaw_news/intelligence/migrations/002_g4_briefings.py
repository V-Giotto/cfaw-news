"""Independent PR4 DDL; PR2 fixed metadata and schema pins remain unchanged."""

import hashlib
import sqlite3
from functools import lru_cache
from pathlib import Path

from sqlalchemy.dialects.sqlite import dialect
from sqlalchemy.schema import CreateIndex, CreateTable

from ..contracts import digest
from ..persistence_models import PersistenceBase

REVISION = "002_g4_briefings_v1"
QUERY = ("SELECT type,name,tbl_name,sql FROM sqlite_master "
         "WHERE tbl_name LIKE 'intelligence_%' ORDER BY type,name")


def source_sha256():
    root = Path(__file__).resolve().parents[1]
    return digest({p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                   for p in (Path(__file__), root / "persistence_models.py")})


def statements():
    tables = PersistenceBase.metadata.sorted_tables
    output = [str(CreateTable(t).compile(dialect=dialect())) for t in tables]
    output += [str(CreateIndex(i).compile(dialect=dialect())) for t in tables
               for i in sorted(t.indexes, key=lambda x: x.name)]
    for table in sorted(set(PersistenceBase.metadata.tables) - {"intelligence_heads", "intelligence_runs"}):
        for operation in ("UPDATE", "DELETE"):
            output.append(f"CREATE TRIGGER {table}_no_{operation.lower()} BEFORE {operation} ON {table} "
                          "BEGIN SELECT RAISE(ABORT,'G4_APPEND_ONLY'); END")
    output += ["""CREATE TRIGGER intelligence_entries_linear BEFORE INSERT ON intelligence_entries
      BEGIN SELECT CASE WHEN NOT EXISTS (SELECT 1 FROM intelligence_heads h
        WHERE h.id=NEW.stream_id AND NEW.sequence=h.sequence+1 AND NEW.previous_sha256=h.sha256)
        THEN RAISE(ABORT,'G4_HISTORY_CHAIN_INVALID') END; END""",
      """CREATE TRIGGER intelligence_head_cas BEFORE UPDATE ON intelligence_heads
      BEGIN SELECT CASE WHEN NEW.id<>OLD.id OR NEW.sequence<>OLD.sequence+1 OR NOT EXISTS
        (SELECT 1 FROM intelligence_entries e WHERE e.stream_id=OLD.id AND e.sequence=NEW.sequence
         AND e.previous_sha256=OLD.sha256 AND e.id=NEW.sha256)
        THEN RAISE(ABORT,'G4_HEAD_CAS_REQUIRED') END; END""",
      """CREATE TRIGGER intelligence_head_no_delete BEFORE DELETE ON intelligence_heads
      BEGIN SELECT RAISE(ABORT,'G4_APPEND_ONLY'); END""",
      """CREATE TRIGGER intelligence_run_no_delete BEFORE DELETE ON intelligence_runs
      BEGIN SELECT RAISE(ABORT,'G4_APPEND_ONLY'); END""",
      """CREATE TRIGGER intelligence_run_version BEFORE UPDATE ON intelligence_runs
      BEGIN SELECT CASE WHEN NEW.id<>OLD.id OR NEW.stream_id<>OLD.stream_id OR NEW.version<>OLD.version+1
        OR NEW.created_at<>OLD.created_at OR NEW.input_sha256<>OLD.input_sha256 OR NEW.input<>OLD.input
        OR OLD.status IN ('completed','cancelled','failed','stale','timed_out','interrupted','evidence_not_ready')
        THEN RAISE(ABORT,'G4_RUN_TRANSITION_INVALID') END; END"""]
    return output


@lru_cache(maxsize=2)
def expected(source_pin):
    with sqlite3.connect(":memory:") as connection:
        for statement in statements():
            connection.execute(statement)
        return connection.execute(QUERY).fetchall()


def schema_sha256():
    return digest(statements())
