"""Hash-bound source prefixes. No source text is copied into the trust journal."""

import hashlib
from typing import Literal

from pydantic import Field, ValidationError
from sqlalchemy import select

from .checkpoint import PersistenceError
from .contracts import CoverageWindow, Hash, SourcePolicy, Strict, canonical, digest, instant
from .document_store import enabled, read_version
from .models import G4Base, G4Capture, G4Coverage, G4Document, G4SourcePolicy, G4Version

TABLES = set(G4Base.metadata.tables) - {G4Document.__tablename__}


class DocumentWatermark(Strict):
    source_id: str
    canonical_url: str
    version_ids: tuple[str, ...] = Field(min_length=1)
    head_version_id: str
    last_observed_at: str


class CorpusPrefix(Strict):
    revision: Literal["g4-corpus-prefix-v1"] = "g4-corpus-prefix-v1"
    immutable: dict[str, dict[str, Hash]]
    documents: dict[str, DocumentWatermark]


def packed(prefix):
    value = prefix.model_dump(mode="json")
    return dict(value=value, sha256=digest(value))


def unpack(value):
    try:
        if set(value) != {"value", "sha256"} or digest(value["value"]) != value["sha256"]:
            raise ValueError
        prefix = CorpusPrefix.model_validate_json(canonical(value["value"]))
        if set(prefix.immutable) != TABLES:
            raise ValueError
        for doc in prefix.documents.values():
            if (doc.head_version_id != doc.version_ids[-1] or len(set(doc.version_ids)) != len(doc.version_ids)
                    or instant(doc.last_observed_at) != doc.last_observed_at):
                raise ValueError
        return prefix
    except (ValueError, TypeError, KeyError):
        raise PersistenceError("G4_CORPUS_BINDING_INVALID", status=503) from None


def extends(current, previous):
    """All accepted immutable rows and each exact version prefix must still exist."""
    for table, records in previous.immutable.items():
        if any(current.immutable[table].get(key) != pin for key, pin in records.items()):
            raise PersistenceError("G4_CORPUS_PREFIX_LOST", status=503)
    for key, old in previous.documents.items():
        new = current.documents.get(key)
        if (new is None or new.source_id != old.source_id or new.canonical_url != old.canonical_url
                or new.version_ids[:len(old.version_ids)] != old.version_ids
                or new.last_observed_at < old.last_observed_at):
            raise PersistenceError("G4_CORPUS_PREFIX_LOST", status=503)


def capture(session):
    """Read/validate the complete committed PR2 ledger in the caller's SQLite snapshot."""
    try:
        if not enabled(session):
            raise ValueError
        policies = {}
        for row in session.scalars(select(G4SourcePolicy)):
            policy = SourcePolicy.model_validate_json(canonical(row.data))
            if digest(row.data) != row.policy_sha256 or row.source_id != policy.source_id:
                raise ValueError
            instant(row.registered_at)
            policies[row.policy_sha256] = policy
        versions = {}
        for row in session.scalars(select(G4Version).order_by(G4Version.sequence)):
            version = read_version(row)
            policy = policies[version.source_policy_sha256]
            if (version.source_id != policy.source_id or version.rights != policy.rights
                    or version.record_origin != policy.record_origin or version.provenance_uri != policy.source_url):
                raise ValueError
            versions.setdefault(version.document_id, []).append(version)
        documents = {}
        for row in session.scalars(select(G4Document)):
            chain = versions.pop(row.document_id, [])
            prior = None
            for number, version in enumerate(chain, 1):
                if (version.sequence != number or version.source_id != row.source_id
                        or version.canonical_url != row.canonical_url
                        or version.supersedes_version_id != (prior.doc_version_id if prior else None)
                        or prior and (version.observed_at <= prior.observed_at or version.available_at < prior.available_at)):
                    raise ValueError
                prior = version
            if (prior is None or row.head_version_id != prior.doc_version_id
                    or row.last_observed_at is None or row.last_observed_at < prior.observed_at
                    or instant(row.last_observed_at) != row.last_observed_at):
                raise ValueError
            documents[row.document_id] = DocumentWatermark(source_id=row.source_id, canonical_url=row.canonical_url,
                version_ids=tuple(v.doc_version_id for v in chain), head_version_id=row.head_version_id,
                last_observed_at=row.last_observed_at)
        if versions:
            raise ValueError
        captures = {r.capture_id: r for r in session.scalars(select(G4Capture))}
        for row in captures.values():
            policy = policies[row.source_policy_sha256]
            if row.source_id != policy.source_id or row.data["observed_at"] != row.observed_at:
                raise ValueError
            for key in row.data["version_ids"]:
                version = session.get(G4Version, key)
                if version is None or version.data["source_id"] != row.source_id:
                    raise ValueError
        for row in session.scalars(select(G4Coverage)):
            window = CoverageWindow.model_validate_json(canonical(row.data))
            if (any(getattr(row, k) != getattr(window, k) for k in (
                    "coverage_window_id", "source_id", "start_at", "end_at", "observed_at", "status"))
                    or row.capture_id is not None and captures[row.capture_id].source_id != row.source_id):
                raise ValueError
        immutable = {}
        for name in sorted(TABLES):
            table = G4Base.metadata.tables[name]
            primary = next(iter(table.primary_key)).name
            immutable[name] = {row[primary]: digest(dict(row)) for row in session.execute(select(table)).mappings()}
        return CorpusPrefix(immutable=immutable, documents=documents)
    except (ValueError, KeyError, TypeError):
        raise PersistenceError("G4_CORPUS_CHAIN_INVALID", status=503) from None


def verify_legacy_inputs(session):
    """Explicit adoption also checks the evidence previously hash-bound by old runs."""
    from evals.intelligence_g2.contracts import json_bytes

    from .persistence_models import BriefingRun
    for run in session.scalars(select(BriefingRun)):
        if hashlib.sha256(json_bytes(run.input)).hexdigest() != run.input_sha256:
            raise PersistenceError("G4_RUNTIME_INPUT_PIN_MISMATCH", status=503)
        try:
            for value in run.input["versions"]:
                row = session.get(G4Version, value["doc_version_id"])
                if row is None or row.data != value:
                    raise ValueError
            for value in run.input["sources"]:
                row = session.get(G4SourcePolicy, digest(value))
                if row is None or row.data != value:
                    raise ValueError
            for value in run.input["coverage"]:
                row = session.get(G4Coverage, value["coverage_window_id"])
                if row is None or row.data != value:
                    raise ValueError
        except (ValueError, KeyError, TypeError, ValidationError):
            raise PersistenceError("G4_CORPUS_PREFIX_LOST", status=503) from None
