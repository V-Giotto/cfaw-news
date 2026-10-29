"""PR4 budget contracts. Full ranking/input retention and wire-level plan checks."""

from typing import Literal

from pydantic import model_validator

from evals.intelligence_v1.contracts import CoverageWindow, Instant, NonEmpty, Sha256, StrictModel

from .contracts import PACKAGE, Count, fail, json_bytes
from .history_contracts import HistoryInput
from .revisit import RevisitResult

Profile = Literal["focus60-radar40-v1", "focus70-radar30-v1", "focus80-radar20-v1"]
Tier = Literal["focus", "radar"]


class ReadingRule(StrictModel):
    revision: Literal["unicode-display-units-v1"] = "unicode-display-units-v1"
    category_table: Literal["unicode-3.2.0"] = "unicode-3.2.0"
    units_per_second: Literal[4] = 4
    item_overhead_seconds: Literal[4] = 4
    citation_seconds: Literal[2] = 2
    calibration: Literal["uncalibrated_not_actual_cognitive_time"] = (
        "uncalibrated_not_actual_cognitive_time")


class BudgetConfig(StrictModel):
    config_revision: Literal["g3-budget-v2"] = "g3-budget-v2"
    profile: Profile = "focus70-radar30-v1"
    reading_rule: ReadingRule = ReadingRule()
    allocation: Literal["protected-global-then-ranked-focus-then-ranked-radar-v1"] = (
        "protected-global-then-ranked-focus-then-ranked-radar-v1")
    unused_share: Literal["no-ordinary-borrowing"] = "no-ordinary-borrowing"
    truncation: Literal["omit-whole-optional-blocks-never-evidence-or-caveats"] = (
        "omit-whole-optional-blocks-never-evidence-or-caveats")
    domains: Literal["canonical-token-set-with-raw-labels-v2"] = (
        "canonical-token-set-with-raw-labels-v2")
    coverage: Literal["requested-interval-conservative-union-v1"] = (
        "requested-interval-conservative-union-v1")


class BudgetInput(StrictModel):
    schema_revision: Literal["g3-pr4-input-v2"] = "g3-pr4-input-v2"
    history_input: HistoryInput
    ranking: RevisitResult
    config: BudgetConfig = BudgetConfig()

    @model_validator(mode="after")
    def bound(self):
        from .budget import validate_input

        validate_input(self)
        return self


class ReadingEstimate(StrictModel):
    projection: Literal["focus", "radar", "minimum"]
    display_units: Count
    citation_count: Count
    seconds: Count
    # JSON pointers into BudgetInput. Complete blocks, not newly generated prose.
    content_refs: tuple[NonEmpty, ...]
    omitted_refs: tuple[NonEmpty, ...]


class PlanReason(StrictModel):
    code: NonEmpty
    input_refs: tuple[NonEmpty, ...]
    required_seconds: Count | None = None
    available_seconds: Count | None = None


class PlannedEvent(StrictModel):
    rank: Count
    event_key: NonEmpty
    snapshot_id: NonEmpty
    status: Literal["focus", "radar", "not_displayed", "truncated", "constraint_excluded"]
    tier: Tier | None
    protected: bool
    estimated_read_seconds: Count
    estimates: tuple[ReadingEstimate, ...]
    chosen_projection: Literal["focus", "radar", "minimum"] | None
    content_refs: tuple[NonEmpty, ...]
    omitted_refs: tuple[NonEmpty, ...]
    reasons: tuple[PlanReason, ...]


class DomainCoverage(StrictModel):
    domain: NonEmpty
    domain_key: NonEmpty
    query_tokens: tuple[NonEmpty, ...]
    labels: tuple[NonEmpty, ...]
    input_refs: tuple[NonEmpty, ...]
    reason_codes: tuple[NonEmpty, ...]
    eligible_events: Count
    presented_events: Count
    ratio: float | None


CoverageStatus = Literal["covered", "partial", "failed", "unknown", "service_offline"]


class CoverageSpan(StrictModel):
    start_at: Instant
    end_at: Instant

    @model_validator(mode="after")
    def ordered(self):
        if self.start_at > self.end_at:
            fail("G3_PLAN_INVALID", "coverage_interval")
        return self


class CoverageSegment(CoverageSpan):
    status: CoverageStatus
    observed_statuses: tuple[CoverageStatus, ...]
    window_refs: tuple[NonEmpty, ...]
    reason_codes: tuple[NonEmpty, ...]


class SourceIntervalCoverage(StrictModel):
    source_id: NonEmpty
    status: CoverageStatus
    observed_statuses: tuple[CoverageStatus, ...]
    window_refs: tuple[NonEmpty, ...]
    segments: tuple[CoverageSegment, ...]
    confirmed_intervals: tuple[CoverageSpan, ...]
    unconfirmed_intervals: tuple[CoverageSpan, ...]
    unobserved_intervals: tuple[CoverageSpan, ...]


class CoverageDiagnostics(StrictModel):
    policy_revision: Literal["requested-interval-conservative-union-v1"] = (
        "requested-interval-conservative-union-v1")
    interval_policy: Literal["half-open-duration-closed-point-v1"] = (
        "half-open-duration-closed-point-v1")
    requested_start_at: Instant
    requested_end_at: Instant
    windows: tuple[CoverageWindow, ...]
    status_counts: dict[str, Count]
    source_count: Count
    window_count: Count
    missing_source_ids: tuple[NonEmpty, ...]
    unobserved_source_ids: tuple[NonEmpty, ...]
    sources: tuple[SourceIntervalCoverage, ...]
    effective_statuses: tuple[NonEmpty, ...]
    has_gap: bool
    interpretation: Literal["coverage_observations_never_confirm_no_updates"] = (
        "coverage_observations_never_confirm_no_updates")


class BudgetDiagnostics(StrictModel):
    budget_seconds: Literal[180, 420, 900]
    focus_target_seconds: Count
    radar_target_seconds: Count
    focus_used_seconds: Count
    radar_used_seconds: Count
    protected_borrowed_seconds: Count
    used_seconds: Count
    unused_seconds: Count
    utilization: float
    candidate_count: Count
    eligible_event_count: Count
    presented_event_count: Count
    event_breadth: float | None
    breadth_unit: Literal["unique_g2_event_keys_not_independent_research_samples"] = (
        "unique_g2_event_keys_not_independent_research_samples")
    domain_coverage: tuple[DomainCoverage, ...]
    declared_domain_count: Count
    presented_domain_count: Count
    declared_domain_coverage: float | None
    truncated_event_keys: tuple[NonEmpty, ...]
    not_displayed_event_keys: tuple[NonEmpty, ...]
    excluded_event_keys: tuple[NonEmpty, ...]
    unmet_protected_event_keys: tuple[NonEmpty, ...]
    reason_counts: dict[str, Count]


class BriefingPlan(StrictModel):
    schema_revision: Literal["g3-pr4-plan-v2"] = "g3-pr4-plan-v2"
    input: BudgetInput
    input_sha256: Sha256
    ranking_sha256: Sha256
    config_sha256: Sha256
    # Original rank order, including every unshown and constrained candidate.
    events: tuple[PlannedEvent, ...]
    display_order: tuple[NonEmpty, ...]
    # Exact complete stage-one pool for future Archive/Library consumers.
    archive_snapshot_ids: tuple[NonEmpty, ...]
    coverage: CoverageDiagnostics
    diagnostics: BudgetDiagnostics
    scope: Literal["offline_development_plan_not_rendering_or_user_value_evidence"] = (
        "offline_development_plan_not_rendering_or_user_value_evidence")

    @model_validator(mode="after")
    def consistent(self):
        from .budget import derive

        expected = derive(self.input)
        actual = self.model_dump(mode="json", exclude={"input", "schema_revision", "scope"})
        if actual != expected:
            fail("G3_PLAN_INVALID", "derived_plan_binding")
        return self


MODELS = (ReadingRule, BudgetConfig, BudgetInput, BriefingPlan)


def schema_payloads():
    return {m.__name__ + ".schema.json": json_bytes(m.model_json_schema()) for m in MODELS}


def check_schemas():
    folder = PACKAGE / "schema/v4_1"
    payloads = schema_payloads()
    return ({p.name for p in folder.glob("*.schema.json")} == set(payloads)
            and all((folder / name).read_bytes() == raw for name, raw in payloads.items()))
