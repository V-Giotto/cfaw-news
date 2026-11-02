"""Versioned storage contracts, independent of offline evaluation packages."""

import hashlib
import json
from datetime import datetime, timezone
from typing import Annotated, Literal
from urllib.parse import urlsplit, urlunsplit

from pydantic import BaseModel, ConfigDict, Field, model_validator

REVISION = "g4-document-ledger-v1"
Hash = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
Name = Annotated[str, Field(min_length=1, max_length=512)]
Rights = Literal["permitted", "excerpt_only", "metadata_only", "unknown", "synthetic"]
CoverageStatus = Literal["covered", "partial", "failed", "unknown", "service_offline"]


class LedgerError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)  # No captured publisher text in diagnostics.


def instant(value: str) -> str:
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if stamp.tzinfo is None:
            raise ValueError
        return stamp.astimezone(timezone.utc).isoformat(timespec="microseconds")
    except (ValueError, TypeError, AttributeError):
        raise LedgerError("G4_CAPTURE_INVALID_TIME") from None


def check_capture_time(observed, available):
    observed, available = instant(observed), instant(available)
    if not observed <= available <= instant(datetime.now(timezone.utc).isoformat()):
        raise LedgerError("G4_CAPTURE_INVALID_TIME")
    return observed, available


def canonical(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                      allow_nan=False).encode("utf-8")


def digest(value) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def safe_url(value: str, *, https=False) -> str:
    try:
        p = urlsplit(value)
        if (p.scheme not in (("https",) if https else ("https", "http"))
                or not p.hostname or p.username or p.password or p.port not in (None, 80, 443)):
            raise ValueError
        # Keep semantic query IDs; never silently collapse distinct articles to one identity.
        from urllib.parse import parse_qsl, urlencode
        query = parse_qsl(p.query, keep_blank_values=True)
        if any(any(word in k.lower() for word in ("token", "secret", "password", "api_key",
                                                  "authorization")) for k, _ in query):
            raise ValueError
        return urlunsplit((p.scheme, p.netloc.lower(), p.path, urlencode(query), ""))
    except (ValueError, TypeError, AttributeError):
        raise LedgerError("G4_CAPTURE_UNSAFE_URL") from None


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class SourcePolicy(Strict):
    schema_revision: Literal["g4-source-policy-v1"] = "g4-source-policy-v1"
    source_id: Name
    source_url: Name
    source_label: Name
    source_role: Literal["media", "community", "official", "other"] = "other"
    record_origin: Literal["real", "synthetic"] = "real"
    rights: Rights = "unknown"
    allowed_use: tuple[Literal["metadata", "excerpt", "fulltext"], ...] = ("metadata",)
    max_excerpt_chars: Annotated[int, Field(gt=0, le=16000)] | None = None
    rights_evidence_uri: Name | None = None
    policy_revision: Name = "unreviewed-metadata-v1"

    @model_validator(mode="after")
    def valid(self):
        if safe_url(self.source_url, https=True) != self.source_url:
            raise LedgerError("G4_POLICY_URL_NOT_CANONICAL")
        if ((self.record_origin == "synthetic") != (self.rights == "synthetic")):
            raise LedgerError("G4_POLICY_ORIGIN_MISMATCH")
        uses = set(self.allowed_use)
        if len(uses) != len(self.allowed_use) or "metadata" not in uses:
            raise LedgerError("G4_POLICY_INVALID_USE")
        if self.rights in {"unknown", "metadata_only"}:
            if uses != {"metadata"}:
                raise LedgerError("G4_POLICY_RIGHTS_INVALID")
        else:
            if not self.rights_evidence_uri or not self.max_excerpt_chars:
                raise LedgerError("G4_POLICY_EVIDENCE_REQUIRED")
            safe_url(self.rights_evidence_uri, https=True)
            if self.rights == "excerpt_only" and "fulltext" in uses:
                raise LedgerError("G4_POLICY_RIGHTS_INVALID")
        return self


class RetainedContent(Strict):
    title: Annotated[str, Field(min_length=1, max_length=512)]
    text_excerpt: Annotated[str, Field(max_length=16000)] | None = None
    paragraphs: tuple[Annotated[str, Field(min_length=1, max_length=16000)], ...] = ()


class G4DocumentVersion(Strict):
    schema_revision: Literal["g4-document-ledger-v1"] = REVISION
    document_id: Name
    doc_version_id: Name
    source_id: Name
    source_policy_sha256: Hash
    source_article_id: Name | None
    canonical_url: Name
    content_kind: Literal["feed_summary", "publisher_text", "synthetic_text"]
    rights: Rights
    record_origin: Literal["real", "synthetic"]
    provenance: Literal["confirmed_feed_capture", "legacy_cache_metadata_observed_now"]
    provenance_uri: Name
    observed_at: Name
    available_at: Name
    published_at: Name | None
    content_sha256: Hash  # RetainedContent canonical JSON, including metadata-only title.
    payload_sha256: Hash  # Bounded parser payload; never proof of full publisher body.
    supersedes_version_id: Name | None
    sequence: Annotated[int, Field(gt=0)]
    retention: Literal["metadata_only", "excerpt", "bounded_feed_text"]
    content: RetainedContent

    @model_validator(mode="after")
    def valid(self):
        if (instant(self.observed_at) != self.observed_at
                or instant(self.available_at) != self.available_at
                or self.available_at < self.observed_at):
            raise LedgerError("G4_CAPTURE_INVALID_TIME")
        if self.published_at is not None:
            instant(self.published_at)  # Source-reported time; never used as availability.
        safe_url(self.canonical_url)
        safe_url(self.provenance_uri, https=True)
        if self.content_sha256 != digest(self.content.model_dump(mode="json")):
            raise LedgerError("G4_CAPTURE_HASH_MISMATCH")
        if self.rights in {"unknown", "metadata_only"} or self.provenance.startswith("legacy"):
            if self.retention != "metadata_only":
                raise LedgerError("G4_CAPTURE_RIGHTS_INVALID")
        if self.retention == "metadata_only" and (
                self.content.text_excerpt is not None or self.content.paragraphs):
            raise LedgerError("G4_CAPTURE_RIGHTS_INVALID")
        if (self.sequence == 1) != (self.supersedes_version_id is None):
            raise LedgerError("G4_CAPTURE_CHAIN_INVALID")
        return self


class CoverageWindow(Strict):
    schema_revision: Literal["g4-coverage-ledger-v1"] = "g4-coverage-ledger-v1"
    coverage_window_id: Name
    source_id: Name
    start_at: Name
    end_at: Name
    observed_at: Name
    status: CoverageStatus
    scope: Literal["bounded_feed_poll"] = "bounded_feed_poll"
    reason_code: Literal["bounded_parse", "conditional_confirmed", "conditional_unanchored",
                         "source_failed", "unobserved_between_polls", "clean_service_downtime",
                         "unclean_service_restart"]

    @model_validator(mode="after")
    def valid(self):
        stamps = [instant(t) for t in (self.start_at, self.end_at, self.observed_at)]
        if stamps != [self.start_at, self.end_at, self.observed_at] or not (
                self.start_at <= self.end_at <= self.observed_at):
            raise LedgerError("G4_COVERAGE_INVALID_TIME")
        if self.status in {"covered", "partial"} and self.start_at != self.end_at:
            raise LedgerError("G4_COVERAGE_CONTINUITY_UNPROVEN")
        return self
