"""PR2-only registered ranking policy and explainable, immutable results."""

from typing import Annotated, Literal

from pydantic import Field

from evals.intelligence_v1.contracts import Instant, NonEmpty, Sha256, StrictModel

Algorithm = Literal["b0", "b1", "b2", "b3", "b4", "p1"]
Number = Annotated[float, Field(allow_inf_nan=False)]
ALGORITHM_VERSIONS = {name: f"g3-{name}-event-v1" for name in
                      ("b0", "b1", "b2", "b3", "b4", "p1")}


class RankingConfig(StrictModel):
    schema_revision: Literal["g3-pr2-1"] = "g3-pr2-1"
    config_revision: Literal["g3-event-ranking-v1"] = "g3-event-ranking-v1"
    query_revision: Literal["persona-query-v1"] = "persona-query-v1"
    retrieval_revision: Literal["bm25-han-bigram-v1"] = "bm25-han-bigram-v1"
    text_projection: Literal["rule-headline-selected-claims-v1"] = (
        "rule-headline-selected-claims-v1")
    normalization: Literal["pool-max-zero-if-zero"] = "pool-max-zero-if-zero"
    time_policy: Literal["latest-current-member-available-at"] = (
        "latest-current-member-available-at")
    missing_time_policy: Literal["zero-recency-last-b0"] = "zero-recency-last-b0"
    missing_b0_score: Number = -1e30
    half_life_days: Annotated[int, Field(gt=0)] = 7
    score_decimals: Annotated[int, Field(ge=0, le=10)] = 5
    tie_break: Literal["eligible-desc-score-desc-event-key-revision-item-id"] = (
        "eligible-desc-score-desc-event-key-revision-item-id")
    baseline_relevance_weight: Number = 0.75
    baseline_recency_weight: Number = 0.25
    relevance_weight: Number = 0.5
    novelty_weight: Number = 0.15
    material_change_weight: Number = 0.2
    recency_weight: Number = 0.15
    exploration_weight: Number = 1.0
    duplicate_weight: Number = -1.0
    included_penalty: Number = 0.1
    rendered_penalty: Number = 0.1
    acknowledged_penalty: Number = 0.25
    exploration_cap: Number = 0.05
    exploration_preferences: tuple[NonEmpty, ...] = (
        "bounded", "include plausible unfamiliar methods")
    history_policy: Literal["latest-exact-event-delivery-distinct-signals-v1"] = (
        "latest-exact-event-delivery-distinct-signals-v1")
    change_policy: Literal["cited-attributed-statement-set-delta-v1"] = (
        "cited-attributed-statement-set-delta-v1")
    knowledge_policy: Literal["exact-token-statement-or-acknowledged-v1"] = (
        "exact-token-statement-or-acknowledged-v1")
    hard_gate: Literal["g2-hold-insufficient-or-no-cited-attributed-claims"] = (
        "g2-hold-insufficient-or-no-cited-attributed-claims")


class Feature(StrictModel):
    value: Number
    input_refs: tuple[NonEmpty, ...]
    reason: NonEmpty


class RankingFeatures(StrictModel):
    bm25: Feature
    relevance: Feature
    novelty: Feature
    material_change: Feature
    recency: Feature
    duplicate: Feature
    exploration: Feature
    latest_material_at: Instant | None
    age_days: Number | None
    history_delivery_id: NonEmpty | None
    exposure_signals: tuple[NonEmpty, ...]


class Contribution(StrictModel):
    feature: NonEmpty
    raw_value: Number
    weight: Number
    contribution: Number
    input_refs: tuple[NonEmpty, ...]


class RankedEvent(StrictModel):
    rank: Annotated[int, Field(ge=1)]
    event_key: NonEmpty
    event_revision: Sha256
    item_id: NonEmpty
    snapshot_id: NonEmpty
    g2_view_sha256: Sha256
    g2_tier_candidate: Literal["focus", "radar", "hold"]
    eligible: bool
    block_reasons: tuple[NonEmpty, ...]
    constraint_input_refs: tuple[NonEmpty, ...]
    score: Number
    features: RankingFeatures
    components: tuple[Contribution, ...]
    reason_codes: tuple[NonEmpty, ...]


class RankingResult(StrictModel):
    schema_revision: Literal["g3-pr2-1"] = "g3-pr2-1"
    algorithm_id: Algorithm
    algorithm_version: NonEmpty
    config: RankingConfig
    config_sha256: Sha256
    input_sha256: Sha256
    comparison_sha256: Sha256
    candidate_pool_sha256: Sha256
    as_of: Instant
    persona_version_id: NonEmpty
    attention_budget_seconds: int
    events: tuple[RankedEvent, ...]
    diagnostics: tuple[NonEmpty, ...]
    scope: Literal["offline_ranking_only_no_budget_or_quality_claim"] = (
        "offline_ranking_only_no_budget_or_quality_claim")


MODELS = (RankingConfig, RankingResult)
