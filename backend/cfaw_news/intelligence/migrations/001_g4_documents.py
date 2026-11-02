"""G4-only additive SQLite DDL. Never edits a legacy business table."""

import hashlib
import sqlite3
from functools import lru_cache
from pathlib import Path

from sqlalchemy.dialects.sqlite import dialect
from sqlalchemy.schema import CreateIndex, CreateTable

from ..contracts import digest
from ..models import G4Base

REVISION = "001_g4_documents_v1"


def source_sha256():
    folder = Path(__file__).resolve().parents[1]
    return digest({p.relative_to(folder).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                   for p in (Path(__file__), folder / "models.py", folder / "contracts.py")})


def statements():
    result = [str(CreateTable(t).compile(dialect=dialect()))
              for t in G4Base.metadata.sorted_tables]
    result += [str(CreateIndex(i).compile(dialect=dialect()))
               for t in G4Base.metadata.sorted_tables for i in sorted(t.indexes, key=lambda i: i.name)]
    immutable = set(G4Base.metadata.tables) - {"g4_documents"}
    for table in sorted(immutable):
        for operation in ("UPDATE", "DELETE"):
            result.append(f"CREATE TRIGGER {table}_no_{operation.lower()} BEFORE {operation} "
                          f"ON {table} BEGIN SELECT RAISE(ABORT, 'G4_IMMUTABLE_RECORD'); END")
    result += ["""CREATE TRIGGER g4_version_linear BEFORE INSERT ON g4_document_versions
        BEGIN
          SELECT CASE WHEN NOT EXISTS (
            SELECT 1 FROM g4_documents d WHERE d.document_id=NEW.document_id
            AND (d.last_observed_at IS NULL OR NEW.observed_at > d.last_observed_at)
            AND ((d.head_version_id IS NULL AND NEW.sequence=1
                  AND NEW.supersedes_version_id IS NULL)
              OR (d.head_version_id=NEW.supersedes_version_id AND EXISTS (
                SELECT 1 FROM g4_document_versions v WHERE v.doc_version_id=d.head_version_id
                AND v.document_id=NEW.document_id AND NEW.sequence=v.sequence+1
                AND NEW.available_at >= v.available_at))))
          THEN RAISE(ABORT, 'G4_DOCUMENT_CHAIN_INVALID') END;
        END""", """CREATE TRIGGER g4_document_head BEFORE UPDATE ON g4_documents BEGIN
          SELECT CASE WHEN NEW.document_id<>OLD.document_id OR NEW.source_id<>OLD.source_id
            OR NEW.canonical_url<>OLD.canonical_url OR NEW.last_observed_at IS NULL
            OR NEW.last_observed_at < OLD.last_observed_at
            OR NOT EXISTS (SELECT 1 FROM g4_document_versions v
              WHERE v.document_id=NEW.document_id AND v.doc_version_id=NEW.head_version_id
              AND v.observed_at <= NEW.last_observed_at)
            OR (NEW.head_version_id<>OLD.head_version_id AND NOT EXISTS (
              SELECT 1 FROM g4_document_versions v WHERE v.doc_version_id=NEW.head_version_id
              AND v.supersedes_version_id IS OLD.head_version_id))
          THEN RAISE(ABORT, 'G4_DOCUMENT_HEAD_INVALID') END;
        END""", """CREATE TRIGGER g4_document_no_delete BEFORE DELETE ON g4_documents
          BEGIN SELECT RAISE(ABORT, 'G4_IMMUTABLE_RECORD'); END"""]
    return result


def schema_sha256():
    return digest(statements())


SCHEMA_QUERY = ("SELECT type,name,tbl_name,sql FROM sqlite_master "
                "WHERE tbl_name LIKE 'g4_%' ORDER BY type,name")


@lru_cache(maxsize=2)
def expected_schema_rows(source_pin):
    with sqlite3.connect(":memory:") as connection:
        for statement in statements():
            connection.execute(statement)
        return connection.execute(SCHEMA_QUERY).fetchall()
