"""Pure historical selectors. Never access text until a version is selected."""

import re
from collections import defaultdict
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from .exceptions import ContractError, Issue

if TYPE_CHECKING:
    from .contracts import DocumentVersion

INSTANT_PATTERN = (
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})$"
)


def parse_instant(value: str) -> datetime:
    if not isinstance(value, str):
        raise ContractError("INVALID_DATETIME")
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?", value):
        raise ContractError("NAIVE_DATETIME")
    if not re.fullmatch(INSTANT_PATTERN, value) or value.endswith("-00:00"):
        raise ContractError("INVALID_DATETIME")
    if value[-6:-5] in {"+", "-"}:
        if int(value[-5:-3]) > 23 or int(value[-2:]) > 59:
            raise ContractError("INVALID_DATETIME")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except (ValueError, OverflowError):
        raise ContractError("INVALID_DATETIME") from None


def utc_instant(value: datetime) -> datetime:
    if not isinstance(value, datetime):
        raise ContractError("INVALID_DATETIME")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ContractError("NAIVE_DATETIME")
    return value.astimezone(timezone.utc)


def format_instant(value: datetime) -> str:
    return utc_instant(value).isoformat().replace("+00:00", "Z")


def version_chains(records):
    """Return linear chains using only identity, hash, availability and parent metadata."""
    by_id = {}
    groups = defaultdict(list)
    for row in records:
        if row.doc_version_id in by_id:
            raise ContractError("DUPLICATE_ID", record_id=row.doc_version_id)
        by_id[row.doc_version_id] = row
        groups[row.document_id].append(row)
    chains = {}
    for document_id, rows in groups.items():
        roots, children, hashes = [], {}, set()
        for row in rows:
            if row.content_sha256 is not None:
                if row.content_sha256 in hashes:
                    raise ContractError("DUPLICATE_CONTENT_VERSION", record_id=row.doc_version_id)
                hashes.add(row.content_sha256)
            parent_id = row.supersedes_version_id
            if parent_id is None:
                roots.append(row)
                continue
            parent = by_id.get(parent_id)
            if (parent is None or parent.document_id != document_id
                    or parent.available_at > row.available_at):
                raise ContractError("VERSION_CHAIN_INVALID", record_id=row.doc_version_id)
            if parent_id in children:
                raise ContractError("VERSION_CONFLICT", record_id=row.doc_version_id)
            children[parent_id] = row
        if not roots:
            raise ContractError("VERSION_CHAIN_INVALID", record_id=document_id)
        if len(roots) != 1:
            raise ContractError("VERSION_CONFLICT", record_id=document_id)
        chain, seen, current = [], set(), roots[0]
        while current is not None:
            if current.doc_version_id in seen:
                raise ContractError("VERSION_CHAIN_INVALID", record_id=current.doc_version_id)
            seen.add(current.doc_version_id)
            chain.append(current)
            current = children.get(current.doc_version_id)
        if len(chain) != len(rows):
            raise ContractError("VERSION_CHAIN_INVALID", record_id=document_id)
        chains[document_id] = chain
    return chains


def require_visible_version(record, *, as_of: datetime):
    if record.available_at > utc_instant(as_of):
        raise ContractError("FUTURE_VERSION", record_id=record.doc_version_id)
    return record


def visible_versions(records, *, as_of: datetime, allowed_source_ids=None) -> list["DocumentVersion"]:
    cutoff = utc_instant(as_of)
    chains = version_chains(records)
    result = []
    for document_id in sorted(chains):
        eligible = [row for row in chains[document_id] if row.available_at <= cutoff
                    and (allowed_source_ids is None or row.source_id in allowed_source_ids)]
        if eligible:
            result.append(eligible[-1])
    return result


def visible_persona(records, *, persona_id: str, as_of: datetime):
    cutoff = utc_instant(as_of)
    rows = [row for row in records if row.persona_id == persona_id]
    seen = set()
    for row in rows:
        if row.available_at in seen:
            raise ContractError("VERSION_CONFLICT", record_id=persona_id)
        seen.add(row.available_at)
    visible = [row for row in rows if row.available_at <= cutoff]
    if not visible:
        raise ContractError("FUTURE_PERSONA" if rows else "REFERENCE_NOT_FOUND",
                            record_id=persona_id)
    return max(visible, key=lambda row: row.available_at)


def visible_exposures(records, *, as_of: datetime, strict: bool = True):
    cutoff = utc_instant(as_of)
    visible, filtered = [], []
    for row in records:
        if row.occurred_at > cutoff:
            if strict:
                raise ContractError("FUTURE_EXPOSURE", record_id=row.exposure_id)
            filtered.append(Issue("FUTURE_EXPOSURE", record_id=row.exposure_id))
        else:
            visible.append(row)
    return tuple(sorted(visible, key=lambda x: (x.occurred_at, x.exposure_id))), tuple(filtered)


def previous_delivery(records, delivery_id: str | None, *, as_of: datetime):
    cutoff = utc_instant(as_of)
    if delivery_id is None:
        return None
    found = [row for row in records if row.delivery_id == delivery_id]
    if len(found) != 1:
        raise ContractError("REFERENCE_NOT_FOUND", record_id=delivery_id)
    row = found[0]
    if row.generated_at > cutoff or row.as_of > cutoff:
        raise ContractError("FUTURE_DELIVERY", record_id=delivery_id)
    return row


def project_candidate(version, *, as_of: datetime):
    from .contracts import CandidateDocumentVersion

    require_visible_version(version, as_of=as_of)
    fields = CandidateDocumentVersion.model_fields
    return CandidateDocumentVersion.model_validate_json(version.model_dump_json(include=set(fields)))
