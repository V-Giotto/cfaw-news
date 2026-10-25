"""PR2 contracts. Importing this module performs no IO."""

import argparse
from datetime import date
from typing import Annotated, Literal

from pydantic import Field, model_validator

from evals.intelligence_g2.contracts import (
    PACKAGE,
    ArtifactDigest,
    ErrorCode,
    G2Error,
    G2ReplayInput,
    Relation,
    checked_relative_path,
    json_bytes,
)
from evals.intelligence_g2.contracts import (
    data as data,
)
from evals.intelligence_g2.contracts import (
    digest as digest,
)
from evals.intelligence_g2.contracts import (
    parse as parse,
)
from evals.intelligence_v1.contracts import Instant, NonEmpty, Sha256, StrictModel

SCHEMA_REVISION = "g2-pr2-1"
FEATURE_REVISION = "g2-event-features-v1"
RELATION_REVISION = "g2-relations-v1"
IDENTITY_REVISION = "g2-event-registry-v1"
PR1_CONFIG_PIN = "9ff868f34f58d5196979377f8697f11ad561d3b730a6eb849cbee72a459a3c84"
Strategy = Literal["r0", "r1", "r2"]
Positive = Annotated[int, Field(gt=0)]
NonNegative = Annotated[int, Field(ge=0)]
Unit = Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]
PR2Code = Literal[
    "G2_PR2_PAIR_SET_INVALID", "G2_PR2_FEATURE_PROVENANCE_INVALID",
    "G2_PR2_CANNOT_LINK_VIOLATION", "G2_PR2_STATE_CHAIN_INVALID",
    "G2_PR2_HISTORY_FUTURE", "G2_PR2_IDENTITY_GRAPH_INVALID",
    "G2_PR2_REVISION_MISMATCH", "G2_PR2_COMPARISON_POOL_MISMATCH",
    "G2_PR2_REFERENCE_CONFLICT",
]


def fail(code, stage, field, record_id=""):
    raise G2Error(code, stage=stage, field=field, record_id=record_id)


class PR2Record(StrictModel):
    schema_revision: Literal["g2-pr2-1"] = SCHEMA_REVISION


class PR2Config(StrictModel):
    config_revision: Literal["g2-pr2-config-v1"] = "g2-pr2-config-v1"
    feature_revision: Literal["g2-event-features-v1"] = FEATURE_REVISION
    relation_revision: Literal["g2-relations-v1"] = RELATION_REVISION
    identity_revision: Literal["g2-event-registry-v1"] = IDENTITY_REVISION
    pr1_config_file_sha256: Literal[PR1_CONFIG_PIN] = PR1_CONFIG_PIN
    default_strategy: Literal["r1"] = "r1"
    title_jaccard: Literal[0.60] = 0.60
    body_jaccard: Literal[0.80] = 0.80
    min_body_tokens: Literal[12] = 12
    window_days: Literal[14] = 14
    copy_title_jaccard: Literal[0.90] = 0.90
    copy_body_jaccard: Literal[0.98] = 0.98


class ReplayCursor(StrictModel):
    timeline_id: NonEmpty
    step_id: NonEmpty
    as_of: Instant
    ordinal: NonNegative
    previous_step_id: NonEmpty | None


class FeatureRef(StrictModel):
    doc_version_id: NonEmpty
    field: Literal["title", "canonical_url", "upstream_document_id", "paragraph"]
    paragraph_id: NonEmpty | None = None
    value_sha256: Sha256
    available_at: Instant


class DocumentEventFeatures(PR2Record):
    feature_revision: Literal["g2-event-features-v1"] = FEATURE_REVISION
    doc_version_id: NonEmpty
    document_id: NonEmpty
    available_at: Instant
    published_at: Instant | None
    canonical_url: NonEmpty | None
    content_sha256: Sha256 | None
    upstream_document_id: NonEmpty | None
    canonical_subject: NonEmpty | None
    subject_candidates: tuple[NonEmpty, ...]
    ambiguous: bool
    target_version: NonEmpty | None
    target_link: NonEmpty | None
    event_type: Literal["release", "capability", "benchmark", "safety", "correction",
                        "research", "tool", "other", "unknown"]
    action: NonEmpty | None
    action_object: NonEmpty | None
    material_role: Literal["announcement", "measurement", "correction", "reprint", "unknown"]
    event_date: date | None
    title_tokens: tuple[Sha256, ...]
    body_tokens: tuple[Sha256, ...]
    copy_cue: bool
    refs: tuple[FeatureRef, ...]


class PairDecision(PR2Record):
    left_doc_version_id: NonEmpty
    right_doc_version_id: NonEmpty
    predicted_relation: Relation
    as_of: Instant
    relation_revision: Literal["g2-relations-v1"] = RELATION_REVISION
    rule_id: NonEmpty
    evidence_reasons: tuple[NonEmpty, ...]
    feature_refs: tuple[FeatureRef, ...]
    cannot_link: tuple[NonEmpty, ...]
    title_similarity: Unit
    body_similarity: Unit
    confidence: None = None

    @model_validator(mode="after")
    def ordered(self):
        if self.left_doc_version_id >= self.right_doc_version_id:
            fail("G2_PR2_PAIR_SET_INVALID", "relations", "pair")
        return self


class BlockedMerge(StrictModel):
    left_members: tuple[NonEmpty, ...]
    right_members: tuple[NonEmpty, ...]
    blocking_pairs: tuple[tuple[NonEmpty, NonEmpty], ...]


class EventCluster(StrictModel):
    member_doc_version_ids: Annotated[tuple[NonEmpty, ...], Field(min_length=1)]
    r0_group_id: NonEmpty | None = None


class GroupingPartition(StrictModel):
    clusters: tuple[EventCluster, ...]
    blocked_merges: tuple[BlockedMerge, ...]


class IdentityTransition(PR2Record):
    transition_id: NonEmpty
    kind: Literal["birth", "merge", "split", "complex", "reactivate", "alias_retired"]
    from_keys: tuple[NonEmpty, ...]
    to_keys: tuple[NonEmpty, ...]
    effective_at: Instant
    step_id: NonEmpty
    trigger_doc_version_ids: tuple[NonEmpty, ...]
    reasons: tuple[NonEmpty, ...]
    previous_semantic_sha256: Sha256


class AliasRecord(StrictModel):
    alias_key: NonEmpty
    target_keys: Annotated[tuple[NonEmpty, ...], Field(min_length=1)]
    kind: Literal["created", "retired"]
    effective_at: Instant
    transition_id: NonEmpty


class RegisteredEvent(StrictModel):
    event_key: NonEmpty
    created_at: Instant
    anchor_doc_version_id: NonEmpty
    status: Literal["active", "dormant", "merged", "retired_split"]
    last_features: tuple[DocumentEventFeatures, ...]
    lineage_ids: tuple[NonEmpty, ...]


class EventSnapshot(PR2Record):
    event_key: NonEmpty
    event_revision: Sha256
    created_at: Instant
    anchor_doc_version_id: NonEmpty
    canonical_subject: NonEmpty | None
    event_type: NonEmpty
    target_version: NonEmpty | None
    action: NonEmpty | None
    action_object: NonEmpty | None
    event_date: date | None
    member_doc_version_ids: Annotated[tuple[NonEmpty, ...], Field(min_length=1)]
    related_event_keys: tuple[NonEmpty, ...]
    lineage_ids: tuple[NonEmpty, ...]


class SourcePointer(StrictModel):
    doc_version_id: NonEmpty
    source_id: NonEmpty
    upstream_document_id: NonEmpty | None
    dependency: Literal["duplicate_or_reprint", "unknown"]
    independence: Literal["unknown"] = "unknown"


class CompatibilityLink(StrictModel):
    kind: Literal["pr1_document_membership"] = "pr1_document_membership"
    pr1_event_key: NonEmpty
    event_key: NonEmpty
    document_id: NonEmpty
    as_of: Instant


class EventView(PR2Record):
    event_key: NonEmpty
    representative_doc_version_id: NonEmpty
    member_doc_version_ids: tuple[NonEmpty, ...]
    source_pointers: tuple[SourcePointer, ...]
    compatibility_links: tuple[CompatibilityLink, ...]


class IdentityState(PR2Record):
    namespace: Sha256
    identity_revision: Literal["g2-event-registry-v1"] = IDENTITY_REVISION
    strategy: Strategy
    grouping_config_sha256: Sha256
    input_manifest_sha256: Sha256
    cursor: ReplayCursor
    previous_state_sha256: Sha256 | None
    registry: tuple[RegisteredEvent, ...]
    transitions: tuple[IdentityTransition, ...]
    aliases: tuple[AliasRecord, ...]


class GroupingInput(PR2Record):
    replay_input: G2ReplayInput
    strategy: Strategy = "r1"
    grouping_config_sha256: Sha256
    cursor: ReplayCursor
    previous_state: IdentityState | None = None
    previous_state_sha256: Sha256 | None = None


class IdentityUpdate(StrictModel):
    events: tuple[EventSnapshot, ...]
    transitions: tuple[IdentityTransition, ...]
    state: IdentityState


class PR2Issue(StrictModel):
    code: ErrorCode | PR2Code
    stage: NonEmpty
    field: str = ""
    record_id: NonEmpty | None = None


class PR2Diagnostic(StrictModel):
    report_revision: Literal["g2-pr2-validation-v1"] = "g2-pr2-validation-v1"
    ok: bool
    counts: dict[str, NonNegative]
    errors: tuple[PR2Issue, ...] = ()
    semantic_support: Literal["not_evaluated"] = "not_evaluated"


class GroupingResult(PR2Record):
    input_sha256: Sha256
    cursor: ReplayCursor
    strategy: Strategy
    features: tuple[DocumentEventFeatures, ...]
    relations: tuple[PairDecision, ...]
    partition: GroupingPartition
    events: tuple[EventSnapshot, ...]
    views: tuple[EventView, ...]
    transitions: tuple[IdentityTransition, ...]
    next_state: IdentityState
    validation: PR2Diagnostic


class ReferencePair(StrictModel):
    timeline_id: NonEmpty
    step_id: NonEmpty
    as_of: Instant
    left_doc_version_id: NonEmpty
    right_doc_version_id: NonEmpty
    relation: Relation
    evidence_at: Instant
    case_id: NonEmpty
    label_origin: Literal["synthetic_fixture"] = "synthetic_fixture"


class PR2RunManifest(PR2Record):
    manifest_revision: Literal["g2-pr2-manifest-v1"] = "g2-pr2-manifest-v1"
    strategy: Strategy
    input_manifest_sha256: Sha256
    config_file_sha256: Sha256
    config_sha256: Sha256
    git_sha: Annotated[str, Field(pattern=r"^[0-9a-f]{40}$")]
    runtime_source_sha256: dict[str, Sha256]
    schema_sha256: dict[str, Sha256]
    dependency_lock_sha256: dict[str, Sha256]
    dependency_versions: dict[str, NonEmpty]
    candidate_pool_sha256: Sha256
    artifacts: tuple[ArtifactDigest, ...]
    validation_scope: Literal["pr2_event_grouping_identity"] = "pr2_event_grouping_identity"


class PR2Trace(PR2Record):
    run_manifest_sha256: Sha256
    generated_at: Instant
    execution_ms: Annotated[float, Field(ge=0, allow_inf_nan=False)]
    model_id: None = None
    model_calls: Literal[0] = 0
    token_usage: Literal[0] = 0
    model_cost: Literal[0] = 0
    usage_reason: Literal["not_called"] = "not_called"


class FixtureFile(StrictModel):
    path: NonEmpty
    role: Literal["prediction", "reference", "review"]
    sha256: Sha256


class FixtureManifest(StrictModel):
    format: Literal["g2-pr2-prediction-v1"] = "g2-pr2-prediction-v1"
    record_origin: Literal["synthetic"] = "synthetic"
    files: tuple[FixtureFile, ...]


class ContinuityReference(StrictModel):
    timeline_id: NonEmpty
    from_step_id: NonEmpty
    to_step_id: NonEmpty
    from_doc_version_id: NonEmpty
    to_doc_version_id: NonEmpty
    expected: Literal["same", "different"]
    case_id: NonEmpty


class ReferenceManifest(StrictModel):
    format: Literal["g2-pr2-reference-v1"] = "g2-pr2-reference-v1"
    record_origin: Literal["synthetic"] = "synthetic"
    label_origin: Literal["synthetic_fixture"] = "synthetic_fixture"
    review_origin: Literal["ai_development"] = "ai_development"
    non_blind: Literal[True] = True
    created_at: Instant
    prediction_manifest_sha256: tuple[Sha256, ...]
    pairs_path: NonEmpty
    pairs_sha256: Sha256
    continuity_path: NonEmpty
    continuity_sha256: Sha256


SCHEMA_MODELS = {cls.__name__: cls for cls in (
    PR2Config, GroupingInput, DocumentEventFeatures, PairDecision, GroupingPartition,
    EventSnapshot, IdentityTransition, IdentityState, EventView, GroupingResult,
    PR2Diagnostic, ReferencePair, PR2RunManifest, PR2Trace, FixtureManifest,
    ReferenceManifest, ContinuityReference,
)}


def schema_payloads():
    return {name + ".schema.json": json_bytes({**cls.model_json_schema(),
        "$schema": "https://json-schema.org/draft/2020-12/schema"})
        for name, cls in SCHEMA_MODELS.items()}


def check_schemas():
    directory = PACKAGE / "schema/v2"
    payloads = schema_payloads()
    return (set(p.name for p in directory.glob("*.schema.json")) == set(payloads)
            and all((directory / p).read_bytes() == raw for p, raw in payloads.items()))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check-schemas", action="store_true")
    mode.add_argument("--export-schemas", action="store_true")
    args = parser.parse_args(argv)
    if args.export_schemas:
        directory = PACKAGE / "schema/v2"
        directory.mkdir(parents=True, exist_ok=True)
        for name, raw in schema_payloads().items():
            path = directory / checked_relative_path(name)
            if path.exists() and path.read_bytes() != raw:
                fail("SCHEMA_INVALID", "schema", name)
            path.write_bytes(raw)
    ok = check_schemas()
    print(json_bytes({"ok": ok, "schema_revision": SCHEMA_REVISION}).decode().strip())
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
