"""Offline provenance and permission checks; HTTPS syntax is not live verification."""

from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit

from .exceptions import ContractError

SENSITIVE = {".local", ".env", "dev-diaries", ".git"}


def controlled_path(root: Path, relative: str) -> Path:
    parts = PurePosixPath(relative).parts
    if (not parts or "\\" in relative or ":" in relative or relative.startswith("/")
            or relative != PurePosixPath(relative).as_posix()
            or any(part.casefold() in {".", "..", *SENSITIVE}
                   or part.casefold().startswith(".env") or part.endswith((".", " "))
                   for part in parts)
            or relative.lower().endswith((".db", ".db-wal", ".db-shm"))):
        raise ContractError("MANIFEST_PATH_INVALID")
    try:
        base = root.resolve()
        path = root.joinpath(*parts).resolve()
    except (OSError, ValueError, RuntimeError):
        raise ContractError("MANIFEST_PATH_INVALID") from None
    if not path.is_relative_to(base):
        raise ContractError("MANIFEST_PATH_INVALID")
    if any(part.casefold() in SENSITIVE or part.casefold().startswith(".env")
           for part in path.relative_to(base).parts):
        raise ContractError("MANIFEST_PATH_INVALID")
    return path


def https_host(value: str) -> str:
    try:
        parts = urlsplit(value)
        if (parts.scheme != "https" or not parts.hostname or parts.username is not None
                or parts.password is not None or parts.port not in {None, 443}
                or parts.hostname == "localhost"
                or parts.hostname.endswith((".invalid", ".test", ".example"))):
            raise ValueError
        return parts.hostname.lower()
    except ValueError:
        raise ContractError("PROVENANCE_INVALID") from None


def check_provenance(origin: str, uri: str | None, root: Path, controlled: set[str]):
    if not uri:
        raise ContractError("PROVENANCE_INVALID", field="provenance_uri")
    if origin == "synthetic":
        controlled_path(root, uri)
        if uri not in controlled:
            raise ContractError("PROVENANCE_INVALID", field="provenance_uri")
    else:
        if uri.startswith("synthetic:"):
            raise ContractError("ORIGIN_MISMATCH", field="provenance_uri")
        https_host(uri)


def check_source(source, root: Path, controlled: set[str]):
    check_provenance(source.record_origin, source.provenance_uri, root, controlled)
    if source.record_origin == "synthetic":
        if source.redistribution_rights != "synthetic" or source.domain is not None:
            raise ContractError("ORIGIN_MISMATCH", record_id=source.source_id)
    else:
        if source.redistribution_rights == "synthetic" or not source.domain:
            raise ContractError("ORIGIN_MISMATCH", record_id=source.source_id)
        if https_host("https://" + source.domain) != source.domain:
            raise ContractError("PROVENANCE_INVALID", field="domain")
        if source.redistribution_rights in {"unknown", "metadata_only"}:
            if set(source.allowed_use) != {"metadata"}:
                raise ContractError("RIGHTS_USE_NOT_ALLOWED", record_id=source.source_id)
        if source.redistribution_rights == "excerpt_only" and "fulltext" in source.allowed_use:
            raise ContractError("RIGHTS_USE_NOT_ALLOWED", record_id=source.source_id)


def check_document(document, sources, root: Path, controlled: set[str]):
    source = sources.get(document.source_id)
    if source is None:
        raise ContractError("SOURCE_NOT_FOUND", record_id=document.doc_version_id)
    if source.source_type != document.source_type:
        raise ContractError("SOURCE_TYPE_MISMATCH", record_id=document.doc_version_id)
    if source.record_origin != document.record_origin:
        raise ContractError("ORIGIN_MISMATCH", record_id=document.doc_version_id)
    check_provenance(document.record_origin, document.provenance_uri, root, controlled)
    has_body = bool(document.text_excerpt or document.paragraphs)
    if document.record_origin == "synthetic":
        try:
            parts = urlsplit(document.canonical_url or "")
        except ValueError:
            raise ContractError("PROVENANCE_INVALID", field="canonical_url",
                                record_id=document.doc_version_id) from None
        if (parts.scheme != "synthetic" or not parts.netloc
                or document.content_kind != "synthetic_text"
                or document.redistribution_rights != "synthetic"):
            raise ContractError("ORIGIN_MISMATCH", record_id=document.doc_version_id)
        if has_body and "fulltext" not in source.allowed_use:
            raise ContractError("RIGHTS_USE_NOT_ALLOWED", record_id=document.doc_version_id)
        return
    if document.content_kind == "synthetic_text" or document.redistribution_rights == "synthetic":
        raise ContractError("ORIGIN_MISMATCH", record_id=document.doc_version_id)
    if https_host(document.canonical_url or "") != source.domain:
        raise ContractError("PROVENANCE_INVALID", field="canonical_url")
    rights = document.redistribution_rights
    if has_body and "unknown" in {rights, source.redistribution_rights}:
        raise ContractError("RIGHTS_UNKNOWN_FULLTEXT", record_id=document.doc_version_id)
    allowed_rights = {
        "unknown": {"unknown", "metadata_only"},
        "metadata_only": {"metadata_only", "unknown"},
        "excerpt_only": {"excerpt_only", "metadata_only", "unknown"},
        "permitted": {"permitted", "excerpt_only", "metadata_only", "unknown"},
    }
    if rights not in allowed_rights[source.redistribution_rights]:
        raise ContractError("RIGHTS_USE_NOT_ALLOWED", record_id=document.doc_version_id)
    if not has_body:
        if "metadata" not in source.allowed_use:
            raise ContractError("SOURCE_NOT_ALLOWED", record_id=document.doc_version_id)
        return
    if rights == "metadata_only" or source.redistribution_rights == "metadata_only":
        raise ContractError("RIGHTS_USE_NOT_ALLOWED", record_id=document.doc_version_id)
    if rights == "excerpt_only" or source.redistribution_rights == "excerpt_only":
        # Check all stored text, without granting an exemption for duplicated excerpts.
        count = len(document.text_excerpt or "") + sum(len(p.text) for p in document.paragraphs)
        limit = source.restrictions.max_excerpt_chars
        if (document.content_kind != "quoted_excerpt" or "excerpt" not in source.allowed_use
                or limit is None or count > limit):
            raise ContractError("RIGHTS_USE_NOT_ALLOWED", record_id=document.doc_version_id)
    elif "fulltext" not in source.allowed_use:
        raise ContractError("RIGHTS_USE_NOT_ALLOWED", record_id=document.doc_version_id)
