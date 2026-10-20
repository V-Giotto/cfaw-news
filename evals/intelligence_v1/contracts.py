"""Strict immutable contracts; JSON Schema is derived, never maintained separately."""

import argparse
from datetime import datetime
from pathlib import Path
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    PlainSerializer,
    WithJsonSchema,
    model_validator,
)

from .exceptions import ContractError
from .hashing import canonical_json, content_sha256
from .temporal import INSTANT_PATTERN, format_instant, parse_instant, utc_instant

SCHEMA_REVISION = "g1-pr1-1"
NonEmpty = Annotated[str, Field(min_length=1, pattern=r"\S")]
Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
PositiveInt = Annotated[int, Field(gt=0)]
Score = Annotated[int, Field(ge=0, le=3)]
Origin = Literal["real", "synthetic"]
SourceType = Literal["official", "paper", "repository", "independent_test", "media",
                     "community", "other"]
ContentKind = Literal["publisher_text", "feed_summary", "archive_authored", "quoted_excerpt",
                      "synthetic_text"]
Rights = Literal["permitted", "excerpt_only", "metadata_only", "unknown", "synthetic"]
Split = Literal["train", "dev", "test"]


def _instant(value):
    return utc_instant(value) if isinstance(value, datetime) else parse_instant(value)


Instant = Annotated[
    datetime, BeforeValidator(_instant), PlainSerializer(format_instant, return_type=str),
    WithJsonSchema({"type": "string", "format": "date-time", "pattern": INSTANT_PATTERN}),
]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class Paragraph(StrictModel):
    paragraph_id: NonEmpty
    text: NonEmpty


class DocumentVersion(StrictModel):
    doc_version_id: NonEmpty
    document_id: NonEmpty
    canonical_url: NonEmpty | None
    source_id: NonEmpty
    source_type: SourceType
    content_kind: ContentKind
    record_origin: Origin
    provenance_uri: NonEmpty | None
    redistribution_rights: Rights
    title: NonEmpty
    language: NonEmpty
    text_excerpt: str | None = None
    paragraphs: tuple[Paragraph, ...] = ()
    content_sha256: Sha256 | None = None
    cleaner_revision: NonEmpty | None
    published_at: Instant | None = None
    submitted_at: Instant | None = None
    first_seen_at: Instant | None = None
    published_time_confidence: Literal["verified", "source_reported", "inferred", "unknown"]
    observed_at: Instant
    available_at: Instant
    supersedes_version_id: NonEmpty | None
    family_id: NonEmpty
    upstream_document_id: NonEmpty | None = None

    @model_validator(mode="after")
    def invariant(self):
        if self.available_at < self.observed_at:
            raise ContractError("AVAILABLE_BEFORE_OBSERVED", field="available_at")
        ids = [p.paragraph_id for p in self.paragraphs]
        if len(ids) != len(set(ids)):
            raise ContractError("DUPLICATE_ID", field="paragraphs")
        expected = content_sha256(self.title, self.text_excerpt, self.paragraphs)
        if expected != self.content_sha256:
            raise ContractError("SHA_MISMATCH", field="content_sha256")
        return self


class PersonaVersion(StrictModel):
    persona_id: NonEmpty
    persona_version_id: NonEmpty
    available_at: Instant
    persona_origin: Literal["constructed", "consented_real"]
    domain_interests: tuple[NonEmpty, ...]
    current_goals: tuple[NonEmpty, ...]
    hard_constraints: tuple[NonEmpty, ...]
    knowledge_known: tuple[NonEmpty, ...]
    attention_budget_seconds: PositiveInt
    exploration_preference: NonEmpty
    locale: NonEmpty


class ReplayStep(StrictModel):
    timeline_id: NonEmpty
    step_id: NonEmpty
    family_scope_ids: Annotated[tuple[NonEmpty, ...], Field(min_length=1)]
    as_of: Instant
    persona_version_id: NonEmpty
    previous_delivery_id: NonEmpty | None
    attention_budget_seconds: PositiveInt
    time_window_start: Instant
    time_window_end: Instant
    visible_doc_version_ids: tuple[NonEmpty, ...]
    coverage_window_ids: tuple[NonEmpty, ...]
    split: Split

    @model_validator(mode="after")
    def interval(self):
        if not self.time_window_start <= self.time_window_end <= self.as_of:
            raise ContractError("INVALID_INTERVAL", field="time_window_start")
        for name in ("family_scope_ids", "visible_doc_version_ids", "coverage_window_ids"):
            values = getattr(self, name)
            if len(values) != len(set(values)):
                raise ContractError("DUPLICATE_ID", field=name)
        return self


class Delivery(StrictModel):
    delivery_id: NonEmpty
    as_of: Instant
    generated_at: Instant

    @model_validator(mode="after")
    def interval(self):
        if self.as_of > self.generated_at:
            raise ContractError("INVALID_INTERVAL", field="generated_at")
        return self


class Exposure(StrictModel):
    exposure_id: NonEmpty
    delivery_id: NonEmpty
    event_prediction_id: NonEmpty | None = None
    reference_event_id_for_fixture: NonEmpty | None = None
    kind: Literal["included", "rendered", "opened", "acknowledged", "dismissed"]
    occurred_at: Instant
    source: NonEmpty

    @model_validator(mode="after")
    def target(self):
        if (self.event_prediction_id is None) == (self.reference_event_id_for_fixture is None):
            raise ContractError("SCHEMA_INVALID", field="event_prediction_id")
        return self


class CoverageWindow(StrictModel):
    coverage_window_id: NonEmpty
    source_id: NonEmpty
    start_at: Instant
    end_at: Instant
    status: Literal["covered", "partial", "failed", "unknown", "service_offline"]
    observed_at: Instant
    reason: str

    @model_validator(mode="after")
    def interval(self):
        if not self.start_at <= self.end_at <= self.observed_at:
            raise ContractError("INVALID_INTERVAL", field="observed_at")
        if self.status != "covered" and not self.reason.strip():
            raise ContractError("SCHEMA_INVALID", field="reason")
        return self


class ReferenceRecord(StrictModel):
    record_origin: Origin
    provenance_uri: NonEmpty


class EventGroup(ReferenceRecord):
    event_id: NonEmpty
    family_id: NonEmpty
    canonical_subject: NonEmpty
    event_type: Literal["release", "capability", "benchmark", "safety", "correction",
                        "research", "tool", "other"]
    first_observed_at: Instant
    document_version_ids: Annotated[tuple[NonEmpty, ...], Field(min_length=1)]
    related_event_ids: tuple[NonEmpty, ...]
    status: Literal["open", "updated", "corrected", "withdrawn", "archived"]
    identity_note: NonEmpty


class EvidenceRef(StrictModel):
    doc_version_id: NonEmpty
    paragraph_id: NonEmpty | None = None
    direction: Literal["supports", "refutes", "mentions", "unknown"]


class Claim(ReferenceRecord):
    claim_id: NonEmpty
    event_id: NonEmpty
    claim_text: NonEmpty
    claim_type: Literal["release_fact", "capability_claim", "measured_result", "constraint",
                        "risk", "other"]
    asserted_by: NonEmpty
    evidence_refs: Annotated[tuple[EvidenceRef, ...], Field(min_length=1)]
    verification_state: Literal["source_attributed", "independently_supported", "disputed",
                                "unverified", "retracted"]
    valid_as_of: Instant
    scope: NonEmpty
    limitations: tuple[NonEmpty, ...]


class GoldLabel(ReferenceRecord):
    timeline_id: NonEmpty
    step_id: NonEmpty
    persona_version_id: NonEmpty
    event_id: NonEmpty
    annotation_version: NonEmpty
    relevance: Score
    potential_value: Score
    novelty_to_persona: Score
    evidence_quality: Score
    graded_relevance: Score
    material_change: Literal["new", "meaningful_update", "no_change", "correction",
                             "withdrawal", "insufficient"]
    tier: Literal["focus", "radar", "archive", "hold"]
    supporting_doc_version_ids: tuple[NonEmpty, ...]
    rationale: NonEmpty
    uncertainty: tuple[NonEmpty, ...]
    adjudication_status: Literal["pending", "agreed", "adjudicated", "unresolved"]


class SourceRestrictions(StrictModel):
    max_excerpt_chars: PositiveInt | None
    note: NonEmpty


class SourceEntry(StrictModel):
    source_id: NonEmpty
    record_origin: Origin
    domain: NonEmpty | None
    source_type: SourceType
    publisher_or_upstream: NonEmpty
    independence_relation: NonEmpty
    allowed_use: Annotated[tuple[Literal["metadata", "excerpt", "fulltext"], ...],
                           Field(min_length=1)]
    redistribution_rights: Rights
    license_url_or_note: NonEmpty
    observed_scope: NonEmpty
    checked_at: Instant | None
    restrictions: SourceRestrictions
    provenance_uri: NonEmpty


class SourceRegistry(StrictModel):
    schema_revision: NonEmpty
    sources: Annotated[tuple[SourceEntry, ...], Field(min_length=1)]


class FamilySplit(StrictModel):
    family_id: NonEmpty
    split: Split


class OriginCounts(StrictModel):
    real: Annotated[int, Field(ge=0)]
    synthetic: Annotated[int, Field(ge=0)]


class SplitCounts(StrictModel):
    train: Annotated[int, Field(ge=0)]
    dev: Annotated[int, Field(ge=0)]
    test: Annotated[int, Field(ge=0)]


class FileEntry(StrictModel):
    path: NonEmpty
    role: Literal["documents", "personas", "steps", "deliveries", "exposures", "coverage",
                  "events", "claims", "gold", "families", "source_registry", "schema",
                  "code", "support", "baseline_config"]
    sha256: Sha256
    record_count: Annotated[int, Field(ge=0)] | None


class Manifest(StrictModel):
    dataset_id: NonEmpty
    dataset_revision: NonEmpty
    schema_revision: NonEmpty
    annotation_version: NonEmpty
    created_at: Instant
    frozen_at: Instant | None
    record_origin_breakdown: OriginCounts
    file_hashes: Annotated[tuple[FileEntry, ...], Field(min_length=1)]
    source_registry_sha256: Sha256
    persona_revision: NonEmpty
    split_policy: Literal["family_locked_v1"]
    family_split_counts: SplitCounts
    baseline_config_sha256: Sha256 | None
    legal_notes: NonEmpty
    limitations: Annotated[tuple[NonEmpty, ...], Field(min_length=1)]
    status: Literal["draft", "frozen", "superseded"]

    @model_validator(mode="after")
    def freeze(self):
        if self.status in {"frozen", "superseded"} and self.frozen_at is None:
            raise ContractError("SCHEMA_INVALID", field="frozen_at")
        if self.frozen_at is not None and self.frozen_at < self.created_at:
            raise ContractError("INVALID_INTERVAL", field="frozen_at")
        return self


class CandidateDocumentVersion(StrictModel):
    doc_version_id: NonEmpty
    document_id: NonEmpty
    canonical_url: NonEmpty | None
    source_id: NonEmpty
    source_type: SourceType
    content_kind: ContentKind
    title: NonEmpty
    language: NonEmpty
    text_excerpt: str | None
    paragraphs: tuple[Paragraph, ...]
    content_sha256: Sha256 | None
    published_at: Instant | None
    observed_at: Instant
    available_at: Instant
    upstream_document_id: NonEmpty | None


SCHEMA_MODELS = {
    "document_version": DocumentVersion, "persona_version": PersonaVersion,
    "replay_step": ReplayStep, "exposure": Exposure, "coverage_window": CoverageWindow,
    "manifest": Manifest, "source_registry": SourceRegistry, "event_group": EventGroup,
    "claim": Claim, "gold_label": GoldLabel, "delivery": Delivery,
    "family_split": FamilySplit, "candidate_document_version": CandidateDocumentVersion,
}


def schema_text(model) -> str:
    schema = model.model_json_schema()
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    return canonical_json(schema) + "\n"


def check_schemas(directory: Path | None = None) -> bool:
    directory = directory or Path(__file__).parent / "schema"
    expected = {name + ".schema.json" for name in SCHEMA_MODELS}
    if {p.name for p in directory.glob("*.schema.json")} != expected:
        return False
    return all((directory / (name + ".schema.json")).read_bytes()
               == schema_text(model).encode("utf-8") for name, model in SCHEMA_MODELS.items())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-schemas", action="store_true", required=True)
    parser.parse_args()
    ok = check_schemas()
    print(canonical_json({"ok": ok, "schema_revision": SCHEMA_REVISION}))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
