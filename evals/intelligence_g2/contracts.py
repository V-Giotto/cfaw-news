"""Versioned G2 contracts. Schema export is explicit; importing this module does no IO."""

import argparse
import json
from pathlib import Path, PurePosixPath
from typing import Annotated, Literal

from pydantic import Field, ValidationError, field_validator, model_validator

from evals.intelligence_v1.contracts import (
    CandidateDocumentVersion,
    CoverageWindow,
    Instant,
    NonEmpty,
    Origin,
    ReplayContext,
    Rights,
    Sha256,
    SourceType,
    StrictModel,
)
from evals.intelligence_v1.exceptions import ContractError
from evals.intelligence_v1.hashing import canonical_json, sha256_bytes

SCHEMA_REVISION = "g2-pr1-1"
PIPELINE_REVISION = "g2-pr1-rule-v1"
IDENTITY_REVISION = "g2-document-lineage-v1"
G1_PIN = "5608f6c9f20d283f9274308fa98a277c535eb0d8d828fd0d863d6e1faafde06f"
ROOT = Path(__file__).resolve().parents[2]
PACKAGE = Path(__file__).parent
NonNegative = Annotated[int, Field(ge=0)]
NonNegativeFloat = Annotated[float, Field(ge=0, allow_inf_nan=False)]
Relation = Literal["exact_duplicate", "syndicated", "same_event_different_evidence",
                   "related_distinct_event", "unrelated", "uncertain"]
Stage = Literal["input", "bridge", "identity", "evidence", "item", "output", "export"]
ErrorCode = Literal[
    "INVALID_JSON", "SCHEMA_INVALID", "UNSUPPORTED_REVISION", "DUPLICATE_ID",
    "MANIFEST_SHA_MISMATCH", "SHA_MISMATCH", "RUNTIME_CODE_MISMATCH",
    "CONFIG_SHA_MISMATCH", "CONFIG_NOT_PINNED", "NAIVE_DATETIME", "INVALID_DATETIME",
    "AVAILABLE_BEFORE_OBSERVED", "FUTURE_VERSION", "FUTURE_PERSONA", "FUTURE_EXPOSURE",
    "FUTURE_COVERAGE", "FUTURE_DELIVERY", "VISIBLE_SET_MISMATCH", "GROUP_MEMBERS_INVALID",
    "G2_CONTEXT_MISMATCH", "G2_IDENTITY_SEED_INVALID", "SOURCE_NOT_FOUND",
    "SOURCE_TYPE_MISMATCH", "ORIGIN_MISMATCH", "PROVENANCE_INVALID",
    "RIGHTS_USE_NOT_ALLOWED", "RIGHTS_UNKNOWN_FULLTEXT", "CITATION_NOT_FOUND",
    "G2_EVIDENCE_NOT_IN_EVENT", "G2_QUOTE_MISMATCH", "G2_PLACEHOLDER_STATUS_INVALID",
    "MANIFEST_PATH_INVALID", "PREDICTION_PATH_INVALID", "OUTPUT_PATH_INVALID",
    "OUTPUT_EXISTS", "EXPORT_IO_ERROR", "RECORD_COUNT_MISMATCH", "UNLISTED_INPUT",
    "CROSS_FAMILY_SPLIT", "REFERENCE_NOT_FOUND", "FUTURE_EVIDENCE",
    "VERSION_CHAIN_INVALID", "VERSION_CONFLICT", "DUPLICATE_CONTENT_VERSION",
    "INVALID_INTERVAL", "SOURCE_NOT_ALLOWED", "HISTORY_TARGET_NOT_FOUND",
    "HISTORY_SNAPSHOT_INVALID", "G2_INPUT_NOT_FROZEN",
    "FAMILY_NOT_FOUND", "DELIVERY_SCOPE_INVALID", "FUTURE_OR_STALE_HISTORY_VERSION",
    "HISTORY_SNAPSHOT_MISMATCH", "HISTORY_PREDICTION_ID_MISMATCH",
]


class G2Error(ContractError):
    def __init__(self, code, *, stage="input", field="", record_id=""):
        super().__init__(code, field=field, record_id=record_id)
        self.stage = stage


def data(value):
    return value.model_dump(mode="json", warnings="none") if isinstance(value, StrictModel) else value


def digest(value):
    """Semantic SHA: canonical JSON, UTF-8, without a trailing newline."""
    return sha256_bytes(canonical_json(data(value)).encode("utf-8"))


def json_bytes(value):
    return (canonical_json(data(value)) + "\n").encode("utf-8")


def read_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise G2Error("INVALID_JSON")
            result[key] = value
        return result

    try:
        if raw.startswith(b"\xef\xbb\xbf"):
            raise ValueError
        return json.loads(raw, object_pairs_hook=pairs,
                          parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except (ValueError, UnicodeError):
        raise G2Error("INVALID_JSON") from None


def checked_relative_path(value):
    if value is None:
        return None
    parts = PurePosixPath(value).parts
    if (not parts or value != PurePosixPath(value).as_posix() or value.startswith("/")
            or "\\" in value or ":" in value or any(
                p.casefold() in {".", "..", ".local", ".git", "dev-diaries"}
                or p.casefold().startswith(".env") or p.endswith((".", " ")) for p in parts)):
        raise G2Error("OUTPUT_PATH_INVALID", field="path")
    return value


def parse(model, value, *, stage="input"):
    """Round-trip even model instances: model_copy and nested instances are not trusted."""
    try:
        return model.model_validate_json(canonical_json(data(value)))
    except ValidationError as error:
        entry = error.errors(include_input=False)[0]
        cause = entry.get("ctx", {}).get("error")
        field = ".".join(str(x) for x in entry["loc"])
        if isinstance(cause, ContractError):
            raise G2Error(cause.code, stage=stage, field=cause.field or field,
                          record_id=cause.record_id) from None
        last = str(entry["loc"][-1]) if entry["loc"] else ""
        code = "SCHEMA_INVALID"
        if entry["type"] == "literal_error":
            if last.endswith("revision"):
                code = "UNSUPPORTED_REVISION"
            elif last in {"verification_state", "support_check_status", "tier_candidate",
                          "evidence_status", "event_type", "independence", "status",
                          "change_signal", "generator", "claim_type", "scope"}:
                code = "G2_PLACEHOLDER_STATUS_INVALID"
        raise G2Error(code, stage=stage, field=field) from None
    except (ValueError, TypeError):
        raise G2Error("SCHEMA_INVALID", stage=stage) from None


class G2Record(StrictModel):
    schema_revision: Literal["g2-pr1-1"] = SCHEMA_REVISION


class G2Config(StrictModel):
    config_revision: Literal["g2-config-v1"] = "g2-config-v1"
    pipeline_revision: Literal["g2-pr1-rule-v1"] = PIPELINE_REVISION
    identity_revision: Literal["g2-document-lineage-v1"] = IDENTITY_REVISION
    event_strategy: Literal["single_document_lineage_v1"] = "single_document_lineage_v1"
    claim_strategy: Literal["paragraph_excerpt_v1"] = "paragraph_excerpt_v1"
    generator_revision: Literal["hold_stub_v1"] = "hold_stub_v1"
    max_quote_chars: Literal[160] = 160


class VersionIdentity(StrictModel):
    """Visible historical identity metadata, never historical body text."""
    doc_version_id: NonEmpty
    document_id: NonEmpty
    available_at: Instant
    supersedes_version_id: NonEmpty | None
    content_sha256: Sha256 | None


class G2VisibleDocument(StrictModel):
    candidate: CandidateDocumentVersion
    record_origin: Origin
    redistribution_rights: Rights
    provenance_uri: NonEmpty
    visible_lineage: Annotated[tuple[VersionIdentity, ...], Field(min_length=1)]


class G2SourcePolicy(StrictModel):
    source_id: NonEmpty
    source_type: SourceType
    record_origin: Origin
    redistribution_rights: Rights
    allowed_use: Annotated[tuple[Literal["metadata", "excerpt", "fulltext"], ...],
                           Field(min_length=1)]
    max_excerpt_chars: Annotated[int, Field(gt=0)] | None


class IdentitySeed(StrictModel):
    document_id: NonEmpty
    anchor_doc_version_id: NonEmpty
    first_visible_at: Instant


class G2ReplayInput(G2Record):
    dataset_id: NonEmpty
    dataset_revision: NonEmpty
    input_manifest_sha256: Sha256
    context: ReplayContext
    visible_documents: tuple[G2VisibleDocument, ...]
    sources: tuple[G2SourcePolicy, ...]
    identity_seeds: tuple[IdentitySeed, ...]
    source_coverage_digest: Sha256
    pipeline_revision: Literal["g2-pr1-rule-v1"]
    config_sha256: Sha256


class EvidenceRef(StrictModel):
    doc_version_id: NonEmpty
    paragraph_id: NonEmpty
    quote: NonEmpty
    quote_sha256: Sha256
    direction: Literal["mentions", "unknown", "supports", "refutes"]


class PredictedRelation(G2Record):
    left_doc_version_id: NonEmpty
    right_doc_version_id: NonEmpty
    predicted_relation: Relation
    method: NonEmpty
    evidence_reasons: tuple[NonEmpty, ...]
    as_of: Instant
    confidence: Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)] | None = None

    @model_validator(mode="after")
    def ordered(self):
        if self.left_doc_version_id >= self.right_doc_version_id:
            raise G2Error("GROUP_MEMBERS_INVALID", field="right_doc_version_id")
        return self


class StableEventIdentity(G2Record):
    event_key: NonEmpty
    identity_revision: Literal["g2-document-lineage-v1"]
    first_visible_at: Instant
    anchor_doc_version_id: NonEmpty
    canonical_subject: NonEmpty | None = None
    event_type: Literal["unknown"] = "unknown"
    member_doc_version_ids: Annotated[tuple[NonEmpty, ...], Field(min_length=1)]
    related_event_keys: tuple[NonEmpty, ...] = ()
    previous_identity_key: NonEmpty | None = None
    identity_conflict: NonEmpty | None = None
    merge_lineage: tuple[NonEmpty, ...] = ()
    event_revision: Sha256


class ClaimCandidate(G2Record):
    claim_key: NonEmpty
    event_key: NonEmpty
    statement: NonEmpty
    claim_type: Literal["source_excerpt"] = "source_excerpt"
    asserted_by: NonEmpty
    scope: Literal["unknown"] = "unknown"
    evidence_refs: Annotated[tuple[EvidenceRef, ...], Field(min_length=1)]
    verification_state: Literal["unverified"] = "unverified"
    support_check_status: Literal["not_evaluated"] = "not_evaluated"
    limitations: tuple[NonEmpty, ...]
    extractor_revision: Literal["paragraph_excerpt_v1"] = "paragraph_excerpt_v1"


class SourceLineage(StrictModel):
    doc_version_id: NonEmpty
    source_id: NonEmpty
    upstream_document_id: NonEmpty | None
    independence: Literal["unknown"] = "unknown"


class EvidenceBundle(G2Record):
    bundle_id: NonEmpty
    event_key: NonEmpty
    as_of: Instant
    status: Literal["placeholder"] = "placeholder"
    doc_version_ids: Annotated[tuple[NonEmpty, ...], Field(min_length=1)]
    claim_candidates: tuple[ClaimCandidate, ...]
    source_lineage: tuple[SourceLineage, ...]
    supporting_refs: tuple[EvidenceRef, ...] = ()
    refuting_refs: tuple[EvidenceRef, ...] = ()
    unverified_refs: tuple[EvidenceRef, ...]
    coverage_gaps: tuple[NonEmpty, ...]
    uncertainties: tuple[NonEmpty, ...]
    bundle_sha256: Sha256


class IntelligenceItem(G2Record):
    item_id: NonEmpty
    content_revision: Sha256
    event_key: NonEmpty
    event_revision: Sha256
    bundle_id: NonEmpty
    as_of: Instant
    headline: NonEmpty
    what_happened: NonEmpty | None
    why_it_matters: NonEmpty | None = None
    claim_keys: tuple[NonEmpty, ...]
    evidence_refs: tuple[EvidenceRef, ...]
    evidence_status: Literal["attributed", "insufficient"]
    uncertainties: tuple[NonEmpty, ...]
    tier_candidate: Literal["hold"] = "hold"
    change_signal: Literal["unknown"] = "unknown"
    generator: Literal["rule"] = "rule"
    generator_revision: Literal["hold_stub_v1"] = "hold_stub_v1"
    source_coverage: tuple[CoverageWindow, ...]
    record_origin: Origin


class ValidationIssue(StrictModel):
    code: ErrorCode
    stage: Stage
    field: str = ""
    record_id: NonEmpty | None = None
    path: NonEmpty | None = None

    @field_validator("path")
    @classmethod
    def safe_relative(cls, value):
        return checked_relative_path(value)


class DiagnosticReport(StrictModel):
    report_revision: Literal["g2-validation-v1"] = "g2-validation-v1"
    ok: bool
    counts: dict[str, NonNegative]
    coverage_gaps: tuple[NonEmpty, ...] = ()
    errors: tuple[ValidationIssue, ...] = ()
    warnings: tuple[ValidationIssue, ...] = ()
    semantic_support: Literal["not_evaluated"] = "not_evaluated"


class G2Result(G2Record):
    run_id: NonEmpty
    input_sha256: Sha256
    timeline_id: NonEmpty
    step_id: NonEmpty
    as_of: Instant
    relations: tuple[PredictedRelation, ...]
    events: tuple[StableEventIdentity, ...]
    bundles: tuple[EvidenceBundle, ...]
    items: tuple[IntelligenceItem, ...]
    validation: DiagnosticReport


class GenerationTrace(G2Record):
    run_id: NonEmpty
    input_sha256: Sha256
    run_manifest_sha256: Sha256
    generated_at: Instant
    execution_ms: NonNegativeFloat
    stage_revisions: dict[str, NonEmpty]
    model_id: None = None
    model_calls: Literal[0] = 0
    token_usage: Literal[0] = 0
    model_cost: Literal[0] = 0
    usage_reason: Literal["not_called"] = "not_called"
    degradation: Literal["placeholder"] = "placeholder"
    errors: tuple[ValidationIssue, ...] = ()
    validation_ok: bool


class ArtifactDigest(StrictModel):
    path: NonEmpty
    sha256: Sha256
    byte_count: NonNegative
    record_count: NonNegative | None

    @field_validator("path")
    @classmethod
    def safe_relative(cls, value):
        return checked_relative_path(value)


class RunManifest(StrictModel):
    manifest_revision: Literal["g2-manifest-v1"] = "g2-manifest-v1"
    run_id: NonEmpty
    dataset_id: NonEmpty
    dataset_revision: NonEmpty
    g1_schema_revision: NonEmpty
    input_manifest_sha256: Sha256
    schema_revision: Literal["g2-pr1-1"] = SCHEMA_REVISION
    pipeline_revision: Literal["g2-pr1-rule-v1"] = PIPELINE_REVISION
    config_revision: Literal["g2-config-v1"] = "g2-config-v1"
    config_file_sha256: Sha256
    config_sha256: Sha256
    git_sha: Annotated[str, Field(pattern=r"^[0-9a-f]{40}$")]
    runtime_source_sha256: dict[str, Sha256]
    schema_sha256: dict[str, Sha256]
    dependency_lock_sha256: dict[str, Sha256]
    python_version: NonEmpty
    dependency_versions: dict[str, NonEmpty]
    input_sha256: Sha256
    context_sha256: Sha256
    candidate_sha256: Sha256
    source_coverage_digest: Sha256
    artifacts: tuple[ArtifactDigest, ...]
    validation_scope: Literal["pr1_contract_skeleton"] = "pr1_contract_skeleton"


SCHEMA_MODELS = {
    "g2_config": G2Config, "g2_replay_input": G2ReplayInput,
    "predicted_relation": PredictedRelation, "stable_event_identity": StableEventIdentity,
    "claim_candidate": ClaimCandidate, "evidence_ref": EvidenceRef,
    "evidence_bundle": EvidenceBundle, "intelligence_item": IntelligenceItem,
    "generation_trace": GenerationTrace, "g2_result": G2Result,
    "diagnostic_report": DiagnosticReport, "run_manifest": RunManifest,
}


def schema_payloads():
    payloads = {}
    for name, model in SCHEMA_MODELS.items():
        schema = model.model_json_schema()
        schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
        payloads[name + ".schema.json"] = json_bytes(schema)
    return payloads


def check_schemas():
    directory = PACKAGE / "schema/v1"
    payloads = schema_payloads()
    return (set(p.name for p in directory.glob("*.schema.json")) == set(payloads)
            and all((directory / name).read_bytes() == raw for name, raw in payloads.items()))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check-schemas", action="store_true")
    mode.add_argument("--export-schemas", action="store_true")
    args = parser.parse_args(argv)
    if args.export_schemas:
        directory = PACKAGE / "schema/v1"
        directory.mkdir(parents=True, exist_ok=True)
        # Existing frozen schemas must be kept; new revisions get a new directory.
        for name, raw in schema_payloads().items():
            target = directory / name
            if target.exists() and target.read_bytes() != raw:
                raise G2Error("SCHEMA_INVALID", field=name)
        for name, raw in schema_payloads().items():
            (directory / name).write_bytes(raw)
    ok = check_schemas()
    print(canonical_json({"ok": ok, "schema_revision": SCHEMA_REVISION}))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
