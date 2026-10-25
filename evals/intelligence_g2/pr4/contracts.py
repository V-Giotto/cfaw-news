"""PR4 wire contracts and explicit, versioned Schema generation."""

import argparse
from typing import Annotated, Literal, Protocol

from pydantic import Field, model_validator

from evals.intelligence_g2.contracts import (
    PACKAGE,
    ArtifactDigest,
    ErrorCode,
    G2Error,
    G2SourcePolicy,
    json_bytes,
)
from evals.intelligence_g2.contracts import data as data
from evals.intelligence_g2.contracts import digest as digest
from evals.intelligence_g2.contracts import parse as parse_base
from evals.intelligence_g2.pr2.contracts import PR2Code, ReplayCursor
from evals.intelligence_g2.pr3.contracts import (
    Citation,
    ClaimAssessment,
    ClaimCandidate,
    ClaimScope,
    ClaimTransition,
    CoverageGap,
    EvidenceBundle,
    PR3Code,
)
from evals.intelligence_v1.contracts import (
    ContentKind,
    CoverageWindow,
    Instant,
    NonEmpty,
    Origin,
    Rights,
    Sha256,
    StrictModel,
)

REVISION = "g2-pr4-1"
Tier = Literal["focus", "radar", "hold"]
NonNegative = Annotated[int, Field(ge=0)]
PR4Code = Literal[
    "G2_PR4_PARENT_RUN_MISMATCH", "G2_PR4_FACT_PROVENANCE_INVALID",
    "G2_PR4_INFERENCE_IN_FACT", "G2_PR4_SCOPE_RISK_MISSING", "G2_PR4_LIFECYCLE_INVALID",
    "G2_PR4_DUPLICATE_EVENT", "G2_PR4_TIER_INVALID", "G2_PR4_BUDGET_EXCEEDED",
    "G2_PR4_SNAPSHOT_CHAIN_INVALID", "G2_PR4_HISTORY_FUTURE", "G2_PR4_REFERENCE_CONFLICT",
]


def fail(code, stage, field, record_id=""):
    raise G2Error(code, stage=stage, field=field, record_id=record_id)


def parse(model, value, stage="input"):
    try:
        return parse_base(model, value, stage=stage)
    except G2Error as error:
        if error.code == "G2_PLACEHOLDER_STATUS_INVALID":
            fail("SCHEMA_INVALID", stage, error.field, error.record_id)
        raise


class Record(StrictModel):
    schema_revision: Literal["g2-pr4-1"] = REVISION


class TierBudget(StrictModel):
    focus: Annotated[int, Field(gt=0)]
    radar: Annotated[int, Field(gt=0)]
    hold: Literal[160] = 160


class PR4Config(StrictModel):
    config_revision: Literal["g2-pr4-config-v1"] = "g2-pr4-config-v1"
    generator_revision: Literal["g2-rule-items-v1"] = "g2-rule-items-v1"
    template_revision: Literal["g2-zh-templates-v1"] = "g2-zh-templates-v1"
    policy_revision: Literal["g2-candidate-tier-v1"] = "g2-candidate-tier-v1"
    budget_profile: Literal["low", "standard", "high"] = "standard"
    budgets: dict[str, TierBudget] = Field(default_factory=lambda: {
        "low": TierBudget(focus=800, radar=220), "standard": TierBudget(focus=1200, radar=320),
        "high": TierBudget(focus=1800, radar=480)})
    max_display_claims: Literal[3] = 3
    focus_read_seconds: Literal[90] = 90
    radar_read_seconds: Literal[12] = 12

    @model_validator(mode="after")
    def fixed_budgets(self):
        if {k: (v.focus, v.radar, v.hold) for k, v in self.budgets.items()} != {
                "low": (800, 220, 160), "standard": (1200, 320, 160), "high": (1800, 480, 160)}:
            raise ValueError("budget revision required")
        return self


class SourcePointer(StrictModel):
    doc_version_id: NonEmpty
    document_id: NonEmpty
    source_id: NonEmpty
    canonical_url: NonEmpty | None
    available_at: Instant
    content_sha256: Sha256 | None
    content_kind: ContentKind
    record_origin: Origin
    redistribution_rights: Rights
    provenance_uri: NonEmpty
    policy: G2SourcePolicy


class EventEvidenceView(StrictModel):
    bundle: EvidenceBundle
    claims: tuple[ClaimCandidate, ...]
    citations: tuple[Citation, ...]
    transitions: tuple[ClaimTransition, ...]
    source_pointers: tuple[SourcePointer, ...]
    lineage_ids: tuple[NonEmpty, ...]
    predecessor_event_keys: tuple[NonEmpty, ...]


class Binding(StrictModel):
    slot: NonEmpty
    claim_key: NonEmpty
    field: Literal["statement", "publisher_source_id"]
    ref_id: NonEmpty
    start: NonNegative
    end: NonNegative
    value: NonEmpty


class FactText(StrictModel):
    text: NonEmpty
    template_id: Literal["attributed_headline", "attributed_quote", "secondary_quote", "lifecycle", "conflict"]
    claim_keys: tuple[NonEmpty, ...]
    bindings: tuple[Binding, ...]


class ClaimSummary(StrictModel):
    claim_key: NonEmpty
    statement: FactText
    attribution: NonEmpty
    scope: ClaimScope
    verification_state: Literal["source_attributed", "disputed", "unverified", "retracted"]
    lifecycle: Literal["current", "historical", "superseded", "retracted"]
    ref_ids: tuple[NonEmpty, ...]
    limitations: tuple[NonEmpty, ...]


class Inference(StrictModel):
    text: NonEmpty
    kind: Literal["inference"] = "inference"
    rule_id: Literal["conditional_same_scope_evaluation"] = "conditional_same_scope_evaluation"
    premise_claim_keys: tuple[NonEmpty, ...]
    limitations: tuple[NonEmpty, ...]


class RiskNote(StrictModel):
    code: NonEmpty
    text: NonEmpty
    basis_type: Literal["claim_status", "conflict", "coverage", "permission", "budget"]
    basis_ids: tuple[NonEmpty, ...]


class IntelligenceItem(Record):
    item_id: NonEmpty
    content_revision: Sha256
    fact_revision: Sha256
    event_key: NonEmpty
    event_revision: Sha256
    headline: FactText | None
    what_happened: FactText | None
    why_it_matters: Inference | None
    claim_summaries: tuple[ClaimSummary, ...]
    selected_claim_keys: tuple[NonEmpty, ...]
    omitted_claim_keys: tuple[NonEmpty, ...]
    evidence_ref_ids: tuple[NonEmpty, ...]
    source_pointers: tuple[SourcePointer, ...]
    evidence_status: Literal["attributed", "disputed", "insufficient"]
    risks: tuple[RiskNote, ...]
    uncertainties: tuple[NonEmpty, ...]
    source_coverage: tuple[CoverageWindow, ...]
    tier_candidate: Tier
    tier_reason_codes: tuple[NonEmpty, ...]
    status_text: NonEmpty | None
    estimated_read_seconds: NonNegative
    reading_cost_basis: Literal["legacy_g1_coarse_90_12_seconds"] = "legacy_g1_coarse_90_12_seconds"
    generator: Literal["rule"] = "rule"
    generator_revision: Literal["g2-rule-items-v1"] = "g2-rule-items-v1"
    template_revision: Literal["g2-zh-templates-v1"] = "g2-zh-templates-v1"
    record_origin: Origin


class ItemSnapshot(Record):
    snapshot_id: NonEmpty
    item_id: NonEmpty
    event_key: NonEmpty
    as_of: Instant
    bundle_id: NonEmpty
    bundle_sha256: Sha256
    change_signal: Literal["first_observed", "content_changed", "same_content_observed", "identity_transition"]
    previous_snapshot_ids: tuple[NonEmpty, ...]
    lineage_ids: tuple[NonEmpty, ...]


class SnapshotState(Record):
    namespace: Sha256
    config_sha256: Sha256
    cursor: ReplayCursor
    previous_state_sha256: Sha256 | None
    source_metadata: tuple[SourcePointer, ...]
    snapshots: tuple[ItemSnapshot, ...]


class GenerationInput(Record):
    namespace: Sha256
    cursor: ReplayCursor
    events: tuple[EventEvidenceView, ...]
    source_coverage: tuple[CoverageWindow, ...]
    coverage_gaps: tuple[CoverageGap, ...]
    previous_state: SnapshotState | None
    previous_state_sha256: Sha256 | None
    config_sha256: Sha256


class GenerationRequest(StrictModel):
    """Presentation adapter gets approved claims only; no tier/identity assignment API."""
    claims: tuple[ClaimCandidate, ...]
    assessments: tuple[ClaimAssessment, ...]
    citations: tuple[Citation, ...]
    transitions: tuple[ClaimTransition, ...]
    mode: Literal["ordinary", "secondary", "corrects", "retracts", "conflict"]
    required_risks: tuple[RiskNote, ...]
    max_visible_chars: Annotated[int, Field(gt=0)]


class GenerationDraft(StrictModel):
    headline: FactText
    what_happened: FactText
    why_it_matters: Inference | None
    claim_summaries: tuple[ClaimSummary, ...]


class ItemGenerator(Protocol):
    def generate(self, request: GenerationRequest) -> GenerationDraft: ...


class Issue(StrictModel):
    code: ErrorCode | PR2Code | PR3Code | PR4Code
    stage: NonEmpty
    field: str
    record_id: NonEmpty | None = None


class Diagnostic(Record):
    ok: bool
    counts: dict[str, NonNegative]
    errors: tuple[Issue, ...] = ()
    coverage_gaps: tuple[CoverageGap, ...] = ()
    independent_validation: Literal["not_evaluated"] = "not_evaluated"
    semantic_truth: Literal["not_evaluated"] = "not_evaluated"


class GenerationResult(Record):
    cursor: ReplayCursor
    items: tuple[IntelligenceItem, ...]
    snapshots: tuple[ItemSnapshot, ...]
    citations: tuple[Citation, ...]
    next_state: SnapshotState
    validation: Diagnostic


class RunManifest(Record):
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
    validation_scope: Literal["pr4_deterministic_candidate_items"] = "pr4_deterministic_candidate_items"


class GenerationTrace(Record):
    run_manifest_sha256: Sha256
    generated_at: Instant
    execution_ms: Annotated[float, Field(ge=0, allow_inf_nan=False)]
    model_calls: Literal[0] = 0
    token_usage: Literal[0] = 0
    model_cost: Literal[0] = 0
    model_id: None = None
    usage_reason: Literal["not_called"] = "not_called"
    degradation: Literal["rule_templates"] = "rule_templates"


SCHEMA_MODELS = (PR4Config, SourcePointer, EventEvidenceView, Binding, FactText, ClaimSummary,
    Inference, RiskNote, IntelligenceItem, ItemSnapshot, SnapshotState, GenerationInput,
    GenerationRequest, GenerationDraft, GenerationResult, Diagnostic, RunManifest, GenerationTrace)


def schema_payloads():
    return {m.__name__ + ".schema.json": json_bytes({**m.model_json_schema(),
        "$schema": "https://json-schema.org/draft/2020-12/schema"}) for m in SCHEMA_MODELS}


def check_schemas():
    directory = PACKAGE / "schema/v4"
    expected = schema_payloads()
    return ({p.name for p in directory.glob("*.schema.json")} == set(expected)
        and all((directory / name).read_bytes() == raw for name, raw in expected.items()))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-schemas", action="store_true")
    parser.add_argument("--write-schemas", action="store_true")
    args = parser.parse_args(argv)
    if args.write_schemas:
        folder = PACKAGE / "schema/v4"
        folder.mkdir(parents=True, exist_ok=True)
        for name, raw in schema_payloads().items():
            (folder / name).write_bytes(raw)
    ok = check_schemas()
    print(json_bytes(dict(ok=ok, schema_revision=REVISION)).decode().strip())
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
