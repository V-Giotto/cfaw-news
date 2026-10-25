"""PR3 strict wire contracts. Schema generation is an explicit developer action."""

import argparse
from typing import Annotated, Literal

from pydantic import Field

from evals.intelligence_g2.contracts import (
    PACKAGE,
    ArtifactDigest,
    ErrorCode,
    G2Error,
    json_bytes,
)
from evals.intelligence_g2.contracts import data as data
from evals.intelligence_g2.contracts import digest as digest
from evals.intelligence_g2.contracts import parse as parse
from evals.intelligence_g2.pr2.contracts import (
    GroupingInput,
    GroupingResult,
    PR2Code,
    PR2Config,
    ReplayCursor,
)
from evals.intelligence_v1.contracts import Instant, NonEmpty, Origin, Sha256, StrictModel

REVISION = "g2-pr3-1"
NonNegative = Annotated[int, Field(ge=0)]
Direction = Literal["supports", "refutes", "mentions", "unknown"]
PR3Code = Literal[
    "G2_PR3_PARENT_RUN_MISMATCH", "G2_PR3_EVIDENCE_NOT_IN_EVENT",
    "G2_PR3_HISTORICAL_REF_AS_CURRENT", "G2_PR3_SPAN_MISMATCH",
    "G2_PR3_FIELD_PROVENANCE_INVALID", "G2_PR3_UNSUPPORTED_DIRECTION",
    "G2_PR3_STATUS_INVALID", "G2_PR3_STATE_CHAIN_INVALID", "G2_PR3_HISTORY_FUTURE",
    "G2_PR3_LINEAGE_INVALID", "G2_PR3_BUDGET_EXCEEDED", "G2_PR3_REFERENCE_CONFLICT",
]


def fail(code, stage, field, record_id=""):
    raise G2Error(code, stage=stage, field=field, record_id=record_id)


class PR3Record(StrictModel):
    schema_revision: Literal["g2-pr3-1"] = REVISION


class PR3Config(StrictModel):
    config_revision: Literal["g2-pr3-config-v1"] = "g2-pr3-config-v1"
    extractor_revision: Literal["g2-paragraph-claims-v1"] = "g2-paragraph-claims-v1"
    scope_revision: Literal["g2-claim-scope-v1"] = "g2-claim-scope-v1"
    relation_revision: Literal["g2-evidence-relations-v1"] = "g2-evidence-relations-v1"
    history_revision: Literal["g2-claim-history-v1"] = "g2-claim-history-v1"
    parent_schema_revision: Literal["g2-pr2-1"] = "g2-pr2-1"
    granularity: Literal["whole_paragraph"] = "whole_paragraph"
    independent_support: Literal["disabled"] = "disabled"
    max_documents: Literal[256] = 256
    max_paragraphs: Literal[4096] = 4096
    max_visible_chars: Literal[1048576] = 1048576
    max_quote_chars: Literal[1024] = 1024
    max_claims_per_document: Literal[32] = 32
    max_claims_per_event: Literal[128] = 128
    max_comparisons: Literal[32768] = 32768
    max_archived_claims: Literal[4096] = 4096


class Citation(StrictModel):
    ref_id: NonEmpty
    doc_version_id: NonEmpty
    document_id: NonEmpty
    paragraph_id: NonEmpty
    start: NonNegative
    end: NonNegative
    quote: NonEmpty
    quote_sha256: Sha256
    source_id: NonEmpty
    available_at: Instant
    content_sha256: Sha256 | None
    record_origin: Origin


class GroundedValue(StrictModel):
    raw_value: NonEmpty
    normalized_value: NonEmpty | None
    ref_id: NonEmpty
    start: NonNegative
    end: NonNegative
    normalizer_revision: Literal["g2-claim-scope-v1"] = "g2-claim-scope-v1"


class Quantity(StrictModel):
    value: GroundedValue
    unit: Literal["percent", "percent_point", "ratio", "count"]
    quantifier: Literal["reported", "at_most", "at_least", "approx", "exact", "unknown"]


class ClaimScope(StrictModel):
    task: GroundedValue | None = None
    dataset: GroundedValue | None = None
    baseline: GroundedValue | None = None
    protocol: GroundedValue | None = None
    hardware: GroundedValue | None = None
    target_version: GroundedValue | None = None
    conditions: tuple[GroundedValue, ...] = ()
    unknown_dimensions: tuple[NonEmpty, ...]


class Proposition(StrictModel):
    subject: GroundedValue | None
    action: GroundedValue | None
    metric: GroundedValue | None
    quantities: tuple[Quantity, ...]
    polarity: Literal["positive", "negative", "unknown"]
    quantifier: Literal["reported", "at_most", "at_least", "approx", "exact", "unknown"]
    ambiguous: bool


class SourceAttribution(StrictModel):
    publisher_source_id: NonEmpty
    asserted_by_source_id: NonEmpty | None
    asserted_by_text: GroundedValue | None
    attribution_kind: Literal["publisher_statement", "reported_speech", "secondary_material"]


class ClaimCandidate(PR3Record):
    claim_key: NonEmpty
    origin_event_key: NonEmpty
    first_extracted_as_of: Instant
    doc_version_id: NonEmpty
    statement: NonEmpty
    claim_type: Literal["release_fact", "capability_claim", "measured_result", "constraint", "risk", "other"]
    attribution: SourceAttribution
    scope: ClaimScope
    proposition: Proposition
    evidence_ref_ids: Annotated[tuple[NonEmpty, ...], Field(min_length=1)]
    limitations: tuple[NonEmpty, ...]
    extractor_revision: Literal["g2-paragraph-claims-v1"] = "g2-paragraph-claims-v1"
    record_origin: Origin
    marker: Literal["none", "correction", "withdrawal"] = "none"


class CoverageGap(StrictModel):
    code: NonEmpty
    source_id: NonEmpty | None = None
    doc_version_id: NonEmpty | None = None
    coverage_window_id: NonEmpty | None = None


class EvidenceLink(StrictModel):
    link_key: NonEmpty
    target_claim_key: NonEmpty
    evidence_claim_key: NonEmpty
    ref_id: NonEmpty
    direction: Direction
    basis: Literal["source_excerpt", "rule_inferred", "unresolved"]
    rule_id: NonEmpty
    scope_relation: Literal["same_declared_scope", "scope_difference", "unknown"]
    support_check_status: Literal["not_evaluated", "rule_checked"]


class SourceLineage(StrictModel):
    doc_version_id: NonEmpty
    source_id: NonEmpty
    upstream_document_id: NonEmpty | None
    edge_kind: Literal["cites", "copy", "duplicate", "unknown"]
    dependency_group_key: NonEmpty
    independence: Literal["dependent", "unknown"]
    upstream_resolved: bool
    basis: tuple[NonEmpty, ...]


class ClaimAssessment(StrictModel):
    claim_key: NonEmpty
    event_key: NonEmpty
    as_of: Instant
    verification_state: Literal["source_attributed", "independently_supported", "disputed", "unverified", "retracted"]
    lifecycle: Literal["current", "historical", "superseded", "retracted"]
    evidence_link_ids: tuple[NonEmpty, ...]
    independent_support_count: Literal[0] = 0
    semantic_truth: Literal["not_evaluated"] = "not_evaluated"
    limitations: tuple[NonEmpty, ...]


class Conflict(StrictModel):
    conflict_id: NonEmpty
    claim_keys: Annotated[tuple[NonEmpty, ...], Field(min_length=2, max_length=2)]
    ref_ids: Annotated[tuple[NonEmpty, ...], Field(min_length=2)]
    scope_relation: Literal["same_declared_scope"] = "same_declared_scope"
    kind: Literal["opposite_reported_result"] = "opposite_reported_result"
    rule_id: Literal["opposite_polarity_same_scope"] = "opposite_polarity_same_scope"
    uncertainties: tuple[NonEmpty, ...] = ("unmodeled_conditions_unknown", "independence_unknown")


class ClaimTransition(StrictModel):
    transition_id: NonEmpty
    kind: Literal["corrects", "retracts"]
    from_claim_keys: tuple[NonEmpty, ...]
    to_claim_keys: tuple[NonEmpty, ...]
    effective_at: Instant
    trigger_ref_ids: tuple[NonEmpty, ...]
    reason: Literal["explicit_same_source_unique_target"] = "explicit_same_source_unique_target"


class ClaimMembership(StrictModel):
    claim_key: NonEmpty
    event_key: NonEmpty
    effective_at: Instant
    basis: Literal["visible_document", "visible_document_lineage", "pr2_identity_lineage", "prior_membership"]
    lineage_ids: tuple[NonEmpty, ...] = ()


class ExtractionResult(StrictModel):
    claims: tuple[ClaimCandidate, ...]
    citations: tuple[Citation, ...]
    coverage_gaps: tuple[CoverageGap, ...]


class LineageResult(StrictModel):
    sources: tuple[SourceLineage, ...]
    coverage_gaps: tuple[CoverageGap, ...]


class RelationResult(StrictModel):
    links: tuple[EvidenceLink, ...]
    conflicts: tuple[Conflict, ...]
    comparisons: NonNegative


class EvidenceState(PR3Record):
    namespace: Sha256
    config_sha256: Sha256
    cursor: ReplayCursor
    previous_state_sha256: Sha256 | None
    claims: tuple[ClaimCandidate, ...]
    citations: tuple[Citation, ...]
    transitions: tuple[ClaimTransition, ...]
    memberships: tuple[ClaimMembership, ...]
    assessments: tuple[ClaimAssessment, ...]
    grouping_state_sha256: Sha256


class EvidenceInput(PR3Record):
    grouping_input: GroupingInput
    grouping_result: GroupingResult
    grouping_config: PR2Config
    config_sha256: Sha256
    previous_state: EvidenceState | None = None
    previous_state_sha256: Sha256 | None = None


class EvidenceBundle(PR3Record):
    bundle_id: NonEmpty
    event_key: NonEmpty
    event_revision: Sha256
    as_of: Instant
    status: Literal["assembled", "insufficient"]
    current_doc_version_ids: tuple[NonEmpty, ...]
    current_claim_keys: tuple[NonEmpty, ...]
    historical_claim_keys: tuple[NonEmpty, ...]
    assessments: tuple[ClaimAssessment, ...]
    lineage: tuple[SourceLineage, ...]
    links: tuple[EvidenceLink, ...]
    conflicts: tuple[Conflict, ...]
    coverage_gaps: tuple[CoverageGap, ...]
    uncertainties: tuple[NonEmpty, ...]
    bundle_sha256: Sha256


class PR3Issue(StrictModel):
    code: ErrorCode | PR2Code | PR3Code
    stage: NonEmpty
    field: str
    record_id: NonEmpty | None = None


class PR3Diagnostic(PR3Record):
    ok: bool
    counts: dict[str, NonNegative]
    errors: tuple[PR3Issue, ...] = ()
    coverage_gaps: tuple[CoverageGap, ...] = ()
    locator_validation: Literal["passed", "failed"] = "passed"
    rule_contract_validation: Literal["passed", "failed"] = "passed"
    ai_development_review: Literal["not_evaluated"] = "not_evaluated"
    independent_validation: Literal["not_evaluated"] = "not_evaluated"


class EvidenceResult(PR3Record):
    cursor: ReplayCursor
    claims: tuple[ClaimCandidate, ...]
    citations: tuple[Citation, ...]
    assessments: tuple[ClaimAssessment, ...]
    memberships: tuple[ClaimMembership, ...]
    links: tuple[EvidenceLink, ...]
    lineage: tuple[SourceLineage, ...]
    conflicts: tuple[Conflict, ...]
    transitions: tuple[ClaimTransition, ...]
    bundles: tuple[EvidenceBundle, ...]
    next_state: EvidenceState
    validation: PR3Diagnostic


class PR3RunManifest(PR3Record):
    parent_manifest_sha256: Sha256
    parent_run_path: NonEmpty
    through_step: NonEmpty
    config_file_sha256: Sha256
    config_sha256: Sha256
    git_sha: Annotated[str, Field(pattern=r"^[0-9a-f]{40}$")]
    runtime_source_sha256: dict[str, Sha256]
    schema_sha256: dict[str, Sha256]
    dependency_lock_sha256: dict[str, Sha256]
    dependency_versions: dict[str, NonEmpty]
    selected_input_sha256: Sha256
    artifacts: tuple[ArtifactDigest, ...]
    validation_scope: Literal["pr3_claims_evidence"] = "pr3_claims_evidence"


class PR3Trace(PR3Record):
    run_manifest_sha256: Sha256
    generated_at: Instant
    execution_ms: Annotated[float, Field(ge=0, allow_inf_nan=False)]
    model_calls: Literal[0] = 0
    token_usage: Literal[0] = 0
    model_cost: Literal[0] = 0
    model_id: None = None
    usage_reason: Literal["not_called"] = "not_called"


class ExpectedClaim(StrictModel):
    doc_version_id: NonEmpty
    paragraph_id: NonEmpty
    statement: NonEmpty
    claim_type: Literal["release_fact", "capability_claim", "measured_result", "constraint", "risk", "other"]
    verification_state: Literal["source_attributed", "independently_supported", "disputed", "unverified", "retracted"]


class ReferenceCase(StrictModel):
    case_id: NonEmpty
    step_id: NonEmpty
    claims: tuple[ExpectedClaim, ...]
    conflict_count: NonNegative
    confirmed_independent_support_count: Literal[0]


SCHEMA_MODELS = (PR3Config, Citation, GroundedValue, ClaimScope, ClaimCandidate, Proposition,
    Quantity, SourceAttribution, EvidenceLink, SourceLineage, ClaimAssessment, Conflict,
    ClaimTransition, ClaimMembership, EvidenceState, EvidenceInput, EvidenceBundle,
    EvidenceResult, PR3Diagnostic, PR3RunManifest, PR3Trace, ReferenceCase)


def schema_payloads():
    return {m.__name__ + ".schema.json": json_bytes({**m.model_json_schema(),
        "$schema": "https://json-schema.org/draft/2020-12/schema"}) for m in SCHEMA_MODELS}


def check_schemas():
    directory = PACKAGE / "schema/v3"
    expected = schema_payloads()
    return ({p.name for p in directory.glob("*.schema.json")} == set(expected)
        and all((directory / name).read_bytes() == raw for name, raw in expected.items()))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-schemas", action="store_true")
    parser.add_argument("--write-schemas", action="store_true")
    args = parser.parse_args(argv)
    if args.write_schemas:
        directory = PACKAGE / "schema/v3"
        directory.mkdir(parents=True, exist_ok=True)
        for name, raw in schema_payloads().items():
            (directory / name).write_bytes(raw)
    ok = check_schemas()
    print(json_bytes({"ok": ok, "schema_revision": REVISION}).decode().strip())
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
