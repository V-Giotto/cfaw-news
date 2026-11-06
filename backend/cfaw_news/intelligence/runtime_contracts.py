"""New runtime boundary. No G3 offline parent or synthetic journal is instantiated."""

from typing import Annotated, Literal

from pydantic import Field, ValidationInfo, model_serializer, model_validator

from .native import ENGINE_PIN, verify
from .runtime_control import model_control

verify()

from evals.intelligence_g2.contracts import G2ReplayInput, VersionIdentity, data, digest  # noqa: E402  # noqa: E402
from evals.intelligence_g2.pr2.contracts import GroupingResult, IdentityState  # noqa: E402
from evals.intelligence_g2.pr3.contracts import EvidenceResult  # noqa: E402
from evals.intelligence_g2.pr4.contracts import GenerationResult  # noqa: E402
from evals.intelligence_g2.pr5.contracts import IntelligencePresentation  # noqa: E402
from evals.intelligence_g3.budget_contracts import (  # noqa: E402
    BudgetConfig,
    BudgetDiagnostics,
    CoverageDiagnostics,
    PlannedEvent,
    Profile,
)
from evals.intelligence_g3.contracts import (  # noqa: E402
    DeliverySnapshot,
    G3Candidate,
    PersonaSnapshot,
    PublishedItemRef,
    ReplayObservation,
)
from evals.intelligence_g3.fact_signature import policy_sha256  # noqa: E402
from evals.intelligence_g3.history_contracts import HistoryConfig  # noqa: E402
from evals.intelligence_g3.ranking_contracts import RankingConfig  # noqa: E402
from evals.intelligence_g3.revisit import RevisitEvent  # noqa: E402
from evals.intelligence_v1.contracts import CoverageWindow as NativeCoverageWindow  # noqa: E402
from evals.intelligence_v1.contracts import Instant, NonEmpty, StrictModel  # noqa: E402

from .contracts import (  # noqa: E402
    CoverageWindow,
    G4DocumentVersion,
    Hash,
    LedgerError,
    SourcePolicy,
)
from .runtime_history import RuntimeJournal, RuntimePrefix, VisitWindow  # noqa: E402

FACT_PIN = "70565148fe436fa823ef6a4063cbba7abb4c994cc34f19dc44bdc2451e367450"
RANK_PIN = digest(dict(revision="g4-runtime-ranking-policy-v2", native_engine=ENGINE_PIN,
    material_projection="preserve-original-kind-v1", persona_replay="historical-prefix-required-v1",
    validation_control="request-scoped-cooperative-v1",
    base=data(RankingConfig()), history=data(HistoryConfig()), fact_signature_policy_sha256=FACT_PIN))
HISTORY_RANK_PIN = digest(dict(revision="g4-runtime-ranking-policy-v3", previous=RANK_PIN,
    persona_replay="actual-persona-chain-first-available-cold-start-v1",
    history="verified-sqlite-prefix-native-g3-protocol-v1", archive_feedback="metadata-only-not-delivery",
    window="confirmed-viewport-visits-and-session-sequence-boundary-v2"))


class ExplicitBudget(BudgetConfig):
    profile: Profile = Field(...)


class RuntimeConfig(StrictModel):
    schema_revision: Literal["g4-pr3-config-v1", "g4-h09-config-v2"] = "g4-pr3-config-v1"
    algorithm: Literal["b4", "p1"] = "b4"
    experiment: Literal["p1-explicit-development-v1"] | None = None
    native_engine_sha256: Hash = ENGINE_PIN
    ranking_policy_sha256: Hash = RANK_PIN
    fact_signature_revision: Literal["g3-grounded-fact-signature-v2"] = "g3-grounded-fact-signature-v2"
    fact_signature_policy_sha256: Hash = FACT_PIN
    budget_registration: Literal["g4-runtime-budget-v1"] = "g4-runtime-budget-v1"
    budget_status: Literal["uncalibrated_experimental_profile"] = "uncalibrated_experimental_profile"
    budget: ExplicitBudget
    attention_budget_seconds: Literal[180, 420, 900] = 420

    @model_validator(mode="after")
    def registered(self):
        expected = HISTORY_RANK_PIN if self.schema_revision == "g4-h09-config-v2" else RANK_PIN
        if (self.native_engine_sha256 != ENGINE_PIN or self.ranking_policy_sha256 != expected
                or self.fact_signature_policy_sha256 != FACT_PIN or policy_sha256() != FACT_PIN):
            raise LedgerError("G4_RUNTIME_CONFIG_PIN_MISMATCH")
        if (self.algorithm == "p1") != (self.experiment is not None):
            raise LedgerError("G4_EXPERIMENT_REQUIRED")
        if data(self.budget) != data(BudgetConfig(profile=self.budget.profile)):
            raise LedgerError("G4_RUNTIME_BUDGET_UNREGISTERED")
        return self


class RuntimeEnvelope(StrictModel):
    schema_revision: Literal["g4-pr3-runtime-envelope-v1", "g4-h09-runtime-envelope-v2"] = "g4-pr3-runtime-envelope-v1"
    kind: Literal["runtime_local_v1"] = "runtime_local_v1"
    record_origin: Literal["real", "synthetic"]
    stream_id: NonEmpty
    as_of: Instant
    time_window_start: Instant
    time_window_end: Instant
    persona: PersonaSnapshot
    versions: Annotated[tuple[G4DocumentVersion, ...], Field(max_length=128)]
    sources: Annotated[tuple[SourcePolicy, ...], Field(max_length=32)]
    coverage: Annotated[tuple[CoverageWindow, ...], Field(max_length=512)]
    synthetic_provenance_uri: NonEmpty | None = None
    config: RuntimeConfig
    persona_history: Annotated[tuple[PersonaSnapshot, ...], Field(max_length=128)] = ()
    history_prefix: RuntimePrefix | None = None
    visit_window: VisitWindow | None = None

    @model_serializer(mode="wrap")
    def legacy_wire(self, handler):
        result = handler(self)
        if self.schema_revision == "g4-pr3-runtime-envelope-v1":
            for name in ("persona_history", "history_prefix", "visit_window"):
                result.pop(name, None)
        return result

    @model_validator(mode="after")
    def bound(self):
        from .g2_adapter import validate_ledger
        validate_ledger(self)
        if self.schema_revision == "g4-pr3-runtime-envelope-v1":
            if self.persona_history or self.history_prefix is not None or self.visit_window is not None:
                raise LedgerError("G4_RUNTIME_HISTORY_VERSION_REQUIRED")
        elif (self.config.schema_revision != "g4-h09-config-v2" or not self.persona_history
                or self.persona_history[-1] != self.persona):
            raise LedgerError("G4_RUNTIME_PERSONA_HISTORY_REQUIRED")
        return self


class EmptyRuntimeJournal(StrictModel):
    schema_revision: Literal["g4-runtime-history-unintegrated-v1"] = "g4-runtime-history-unintegrated-v1"
    entries: tuple[()] = ()
    status: Literal["not_integrated_no_delivery_or_knowledge_inference"] = (
        "not_integrated_no_delivery_or_knowledge_inference")


class RuntimeReplay(StrictModel):
    """Already validated native steps, with an explicitly absent PR4 history integration."""
    as_of: Instant
    persona: PersonaSnapshot
    candidates: tuple[G3Candidate, ...]
    evidence: EvidenceResult
    identity_state: IdentityState
    observations: tuple[ReplayObservation, ...]
    document_archive: tuple[VersionIdentity, ...]
    source_coverage: tuple[NativeCoverageWindow, ...]
    deliveries: tuple[DeliverySnapshot, ...] = ()
    history: tuple[()] = ()
    published_refs: tuple[PublishedItemRef, ...] = ()
    time_window_start: Instant
    time_window_end: Instant
    attention_budget_seconds: Literal[180, 420, 900]

    @model_serializer(mode="wrap")
    def legacy_wire(self, handler):
        result = handler(self)
        if not self.published_refs:
            result.pop("published_refs", None)
        return result


class RuntimeHistoryInput(StrictModel):
    schema_revision: Literal["g4-runtime-history-context-v1"] = "g4-runtime-history-context-v1"
    envelope: RuntimeEnvelope
    replay: RuntimeReplay
    journal: EmptyRuntimeJournal | RuntimeJournal = EmptyRuntimeJournal()
    mappings: tuple[()] = ()


class NativeStep(StrictModel):
    schema_revision: Literal["g4-native-step-v1"] = "g4-native-step-v1"
    replay_input: G2ReplayInput
    grouping: GroupingResult
    evidence: EvidenceResult
    rule: GenerationResult
    presentations: tuple[IntelligencePresentation, ...]


class Projection(StrictModel):
    doc_version_id: NonEmpty
    ledger_record_sha256: Hash
    native_content_sha256: Hash | None
    native_canonical_url: NonEmpty
    native_content_kind: NonEmpty


class RuntimeRanking(StrictModel):
    schema_revision: Literal["g4-runtime-ranking-v1"] = "g4-runtime-ranking-v1"
    algorithm_id: Literal["b4", "p1"]
    input_sha256: Hash
    config_sha256: Hash
    candidate_pool_sha256: Hash
    fact_signature_policy_sha256: Hash
    events: tuple[RevisitEvent, ...]
    history_status: Literal["not_integrated", "validated_sqlite_prefix_native_rules_v1"] = "not_integrated"


class RuntimeBudgetInput(StrictModel):
    schema_revision: Literal["g4-runtime-budget-input-v1"] = "g4-runtime-budget-input-v1"
    history_input: RuntimeHistoryInput
    ranking: RuntimeRanking
    config: BudgetConfig


class RuntimePlan(StrictModel):
    schema_revision: Literal["g4-runtime-plan-v1"] = "g4-runtime-plan-v1"
    input: RuntimeBudgetInput
    input_sha256: Hash
    ranking_sha256: Hash
    config_sha256: Hash
    events: tuple[PlannedEvent, ...]
    display_order: tuple[NonEmpty, ...]
    archive_snapshot_ids: tuple[NonEmpty, ...]
    coverage: CoverageDiagnostics
    diagnostics: BudgetDiagnostics
    scope: Literal["calculated_not_published_no_user_value_claim"] = (
        "calculated_not_published_no_user_value_claim")

    @model_validator(mode="after")
    def bound(self, info: ValidationInfo):
        from .g3_adapter import plan_fields
        with model_control(info) as control:
            control.check("plan_validation")
            expected = plan_fields(self.input)
            actual = self.model_dump(mode="json", exclude={"input", "schema_revision", "scope"})
            if actual != expected:
                raise LedgerError("G4_PLAN_BINDING_INVALID")
            control.check("plan_validation_complete")
        return self


class RuntimeResult(StrictModel):
    schema_revision: Literal["g4-pr3-result-v1", "g4-h09-result-v2"] = "g4-pr3-result-v1"
    input: RuntimeEnvelope
    input_sha256: Hash
    state: Literal["plan_ready", "raw_news_only", "evidence_not_ready"]
    reason_codes: tuple[NonEmpty, ...]
    stages: tuple[NativeStep, ...]
    projections: tuple[Projection, ...]
    context: RuntimeHistoryInput | None
    ranking: RuntimeRanking | None
    plan: RuntimePlan | None
    coverage: CoverageDiagnostics
    archive_snapshot_ids: tuple[NonEmpty, ...]
    publishable: Literal[False] = False
    semantic_truth: Literal["not_evaluated"] = "not_evaluated"

    @model_validator(mode="after")
    def replay(self, info: ValidationInfo):
        from .runtime import derive
        with model_control(info) as control:
            control.check("result_validation")
            actual = self.model_dump(mode="json", exclude={"schema_revision", "input"})
            if actual != derive(self.input, self.input_sha256):
                raise LedgerError("G4_RUNTIME_OUTPUT_MISMATCH")
            control.check("result_validation_complete")
        return self
