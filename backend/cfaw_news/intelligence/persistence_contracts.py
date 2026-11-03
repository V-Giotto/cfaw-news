"""Versioned local API. Shape validation never grants evidence or publication eligibility."""

from typing import Annotated, Literal

from pydantic import AfterValidator, Field, model_validator

from evals.intelligence_g2.pr3.contracts import Citation, ClaimAssessment, ClaimCandidate
from evals.intelligence_g3.budget_contracts import BudgetDiagnostics, CoverageDiagnostics, Profile
from evals.intelligence_g3.contracts import G3Candidate
from evals.intelligence_v1.contracts import Instant, StrictModel

from .boundary import BoundaryError as ErrorView
from .contracts import G4DocumentVersion, Hash, LedgerError, instant
from .runtime_contracts import RANK_PIN

Name = Annotated[str, Field(min_length=1, max_length=512)]
Text = Annotated[str, Field(min_length=1, max_length=512)]
Key = Annotated[str, Field(pattern=r"^[A-Za-z0-9_.:-]{1,128}$")]
Mode = Literal["real", "synthetic_development"]
RunState = Literal["queued", "running", "completed", "cancelled", "failed", "stale", "timed_out",
                   "interrupted", "evidence_not_ready"]
RequestTime = Annotated[str, AfterValidator(instant), Field(json_schema_extra={"format": "date-time"})]
TERMINAL = {"completed", "cancelled", "failed", "stale", "timed_out", "interrupted", "evidence_not_ready"}


class WriteRequest(StrictModel):
    schema_revision: Literal["g4-pr4-write-v1"] = "g4-pr4-write-v1"
    idempotency_key: Key
    expected_head: Hash
    expected_epoch: Key


class PersonaWrite(WriteRequest):
    expected_persona_version: Annotated[int, Field(ge=0)]
    domain_interests: Annotated[list[Text], Field(max_length=32)]
    current_goals: Annotated[list[Text], Field(max_length=32)] = Field(default_factory=list)
    hard_constraints: Annotated[list[Text], Field(max_length=32)] = Field(default_factory=list)
    knowledge_known: Annotated[list[Text], Field(max_length=32)] = Field(default_factory=list)
    attention_budget_seconds: Literal[180, 420, 900] = 420
    exploration_preference: Literal["off", "bounded"] = "off"
    locale: Annotated[str, Field(min_length=1, max_length=32)] = "und"


class BriefingWrite(WriteRequest):
    expected_latest_version: Annotated[int, Field(ge=0)]
    persona_version_id: Name
    runtime_policy_sha256: Hash = Field(json_schema_extra={"const": RANK_PIN})
    profile: Profile
    algorithm: Literal["b4", "p1"] = "b4"
    experiment: Literal["p1-explicit-development-v1"] | None = None
    time_window_start: RequestTime | None = None

    @model_validator(mode="after")
    def registered(self):
        if self.runtime_policy_sha256 != RANK_PIN:
            raise LedgerError("G4_RUNTIME_CONFIG_PIN_MISMATCH")
        if (self.algorithm == "p1") != (self.experiment is not None):
            raise LedgerError("G4_EXPERIMENT_REQUIRED")
        return self


class CancelWrite(WriteRequest):
    expected_run_version: Annotated[int, Field(gt=0)]


class InteractionWrite(WriteRequest):
    briefing_id: Name
    expected_snapshot_version: Annotated[int, Field(gt=0)]
    target_id: Name
    kind: Literal["rendered", "opened", "ack", "dismiss", "retract"]
    confirmation: Literal["viewport_visible", "detail_opened", "explicit_user"]
    client_occurred_at: RequestTime | None = None
    retracts_id: Name | None = None

    @model_validator(mode="after")
    def explicit(self):
        expected = {"rendered": "viewport_visible", "opened": "detail_opened"}.get(self.kind, "explicit_user")
        if self.confirmation != expected or (self.kind == "retract") != (self.retracts_id is not None):
            raise LedgerError("G4_INTERACTION_CONFIRMATION_REQUIRED")
        return self


class HeadView(StrictModel):
    stream_id: Name
    sequence: Annotated[int, Field(ge=0)]
    sha256: Hash
    epoch: Key
    latest_snapshot_id: Name | None
    publication_version: Annotated[int, Field(ge=0)]
    persona_version_id: Name | None


class PersonaView(StrictModel):
    id: Name
    version: Annotated[int, Field(gt=0)]
    available_at: Instant
    record_origin: Literal["real", "synthetic"]
    domain_interests: tuple[Text, ...]
    current_goals: tuple[Text, ...]
    hard_constraints: tuple[Text, ...]
    knowledge_known: tuple[Text, ...]
    attention_budget_seconds: Literal[180, 420, 900]
    exploration_preference: Literal["off", "bounded"]
    locale: str


class RunView(StrictModel):
    id: Name
    version: Annotated[int, Field(gt=0)]
    status: RunState
    cancel_requested: bool
    created_at: Instant
    started_at: Instant | None
    finished_at: Instant | None
    as_of: Instant
    persona_version_id: Name
    snapshot_id: Name | None
    reason_codes: tuple[Name, ...]
    input_sha256: Hash


class ArchiveView(StrictModel):
    id: Name
    event_key: Name
    event_revision: Name
    event_snapshot_id: Name
    title: Annotated[str, Field(max_length=16000)]
    source_ids: tuple[Name, ...]
    rights: tuple[Literal["permitted", "excerpt_only", "metadata_only", "unknown", "synthetic"], ...]
    content_kinds: tuple[Name, ...]
    evidence_status: Name
    native_tier: Literal["focus", "radar", "hold"]
    reason_codes: tuple[Name, ...]


class DeliveryView(StrictModel):
    id: Name
    event_snapshot_id: Name
    event_key: Name
    event_revision: Name
    ordinal: Annotated[int, Field(ge=0)]
    tier: Literal["focus", "radar"]
    status: Literal["focus", "radar", "truncated"]
    reason_codes: tuple[Name, ...]
    estimated_reading_seconds: Annotated[int, Field(ge=0)]
    reading_time_status: Literal["uncalibrated_estimate_not_behavior"] = "uncalibrated_estimate_not_behavior"


class BriefingView(StrictModel):
    schema_revision: Literal["g4-pr4-briefing-v1"] = "g4-pr4-briefing-v1"
    id: Name
    run_id: Name
    version: Annotated[int, Field(gt=0)]
    etag: Name
    as_of: Instant
    generated_at: Instant
    pipeline_mode: Literal["runtime_local_v1"] = "runtime_local_v1"
    mode: Mode
    evidence_status: Literal["plan_ready", "raw_news_only"]
    persona_version_id: Name
    runtime_sha256: Hash
    runtime_policy_sha256: Hash
    reason_codes: tuple[Name, ...]
    coverage: CoverageDiagnostics
    archive_snapshot_ids: tuple[Name, ...]
    unmet_protected_event_keys: tuple[Name, ...]
    display_order: tuple[Name, ...]
    deliveries: tuple[DeliveryView, ...]
    archive: tuple[ArchiveView, ...]
    budget_diagnostics: BudgetDiagnostics | None
    history_scoring: Literal["not_applied_pr3_v2"] = "not_applied_pr3_v2"
    semantic_truth: Literal["not_evaluated"] = "not_evaluated"


class InteractionView(StrictModel):
    id: Name
    briefing_id: Name
    target_id: Name
    kind: Literal["included", "rendered", "opened", "ack", "dismiss", "retract"]
    sequence: Annotated[int, Field(gt=0)]
    ordinal: Annotated[int, Field(ge=0)]
    available_at: Instant
    client_occurred_at: Instant | None
    persona_version_id: Name
    retracts_id: Name | None
    source: Literal["server_publication", "client_confirmation", "explicit_user"]
    learned: Literal[False] = False


class EventDetailView(StrictModel):
    schema_revision: Literal["g4-pr4-event-detail-v1"] = "g4-pr4-event-detail-v1"
    briefing_id: Name
    snapshot_version: Annotated[int, Field(gt=0)]
    as_of: Instant
    event: ArchiveView
    candidate: G3Candidate
    documents: tuple[G4DocumentVersion, ...]
    claims: tuple[ClaimCandidate, ...]
    citations: tuple[Citation, ...]
    assessments: tuple[ClaimAssessment, ...]
    opens_recorded_by_get: Literal[False] = False


class MutationView(StrictModel):
    schema_revision: Literal["g4-pr4-mutation-v1"] = "g4-pr4-mutation-v1"
    resource_id: Name
    deduplicated: bool
    head: HeadView


class ProfileView(StrictModel):
    profile: Profile
    config_sha256: Hash
    calibration: Literal["uncalibrated_experimental_profile"] = "uncalibrated_experimental_profile"


class StatusView(StrictModel):
    schema_revision: Literal["g4-pr4-status-v1"] = "g4-pr4-status-v1"
    scope: Literal["local_single_user_no_multiuser_auth"] = "local_single_user_no_multiuser_auth"
    enabled: bool
    state: Literal["ready", "disabled", "migration_required", "unavailable"]
    mode: Mode
    head: HeadView | None
    worker_available: bool
    code: Name | None = None
    runtime_policy_sha256: Hash
    profiles: tuple[ProfileView, ...]
    history_storage: Literal["sqlite_append_only"] = "sqlite_append_only"
    history_scoring: Literal["not_applied_pr3_v2"] = "not_applied_pr3_v2"


MODELS = (PersonaWrite, BriefingWrite, CancelWrite, InteractionWrite, ErrorView, HeadView, PersonaView,
          RunView, ArchiveView, DeliveryView, BriefingView, InteractionView, EventDetailView, MutationView, StatusView)
