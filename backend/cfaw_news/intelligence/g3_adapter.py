"""New validated runtime wrapper over frozen G3 computation kernels, not offline replay."""

from dataclasses import dataclass

from evals.intelligence_g2.contracts import data, digest, json_bytes
from evals.intelligence_g3 import budget as native_budget
from evals.intelligence_g3.history_contracts import HistoryConfig
from evals.intelligence_g3.rankers import _contributions, _feature, _features
from evals.intelligence_g3.ranking_contracts import RankingConfig, RankingFeatures
from evals.intelligence_g3.revisit import RevisitEvent, _history_features, _prefix
from evals.intelligence_v1.baselines import candidate_scores
from evals.intelligence_v1.contracts import PersonaVersion
from evals.intelligence_v1.hashing import sha256_bytes

from .contracts import LedgerError
from .runtime_contracts import FACT_PIN, RuntimeRanking, RuntimeReplay
from .runtime_control import controlled, current


@dataclass(frozen=True)
class RetrievalDocument:
    doc_version_id: str
    title: str
    text_excerpt: str
    paragraphs: tuple = ()


@dataclass(frozen=True)
class Query:
    persona: PersonaVersion


def rows(history_input, algorithm, checkpoint=None):
    """Projection/orchestration only: all features, history rules and weights are native."""
    replay, config = history_input.replay, RankingConfig()
    documents, pool_refs = [], ["/persona/persona/domain_interests", "/persona/persona/current_goals",
                                "/persona/persona/hard_constraints"]
    for i, candidate in enumerate(replay.candidates):
        item = candidate.rule_item
        documents.append(RetrievalDocument(candidate.event.event_key,
            item.headline.text if item.headline else "", "\n".join(s.statement.text
                for s in item.claim_summaries if s.claim_key in item.selected_claim_keys)))
        pool_refs += [f"/candidates/{i}/rule_item/headline", f"/candidates/{i}/rule_item/claim_summaries",
                      f"/candidates/{i}/rule_item/selected_claim_keys"]
    scores = candidate_scores(Query(replay.persona.persona), tuple(documents))
    maximum = max(scores.values(), default=0.0)
    result = []
    for i, candidate in enumerate(replay.candidates):
        if checkpoint is not None:
            checkpoint("ranking_candidate")
        base, block = _features(replay, candidate, i, scores[candidate.event.event_key], maximum,
                                config, pool_refs)
        history, signals, penalty = _history_features(history_input, candidate, HistoryConfig())
        protected = not block and history.promotion != "none"
        updates = {name: data(_prefix(getattr(base, name))) for name in ("bm25", "relevance", "recency")}
        updates.update(novelty=data(_feature(float(not history.declared_known) if not block else 0,
            history.input_refs, "explicit_known" if history.declared_known else
            "no_explicit_knowledge_not_proof_of_unfamiliarity")),
            material_change=data(_feature(float(protected), history.input_refs, history.promotion)),
            duplicate=data(_feature(penalty, history.input_refs, "protected_update" if protected else
                "unchanged_delivered_statements" if penalty else "no_safe_repeat_penalty")),
            exploration=data(_feature(base.exploration.value if not history.delivery_count
                and not history.declared_known and not any("uncertain" in s or "missing_explicit" in s
                    for s in history.mapping_statuses) else 0,
                [*history.input_refs, *_prefix(base.exploration).input_refs],
                "bounded_explicit_unseen_exploration")), exposure_signals=signals, history_delivery_id=None)
        features = RankingFeatures.model_validate_json(json_bytes({**data(base), **updates}))
        components = _contributions(algorithm, features, config)
        result.append(RevisitEvent(rank=1, event_key=candidate.event.event_key,
            event_revision=candidate.event.event_revision, item_id=candidate.rule_item.item_id,
            snapshot_id=candidate.snapshot.snapshot_id, g2_view_sha256=candidate.g2_view_sha256,
            g2_tier_candidate=candidate.rule_item.tier_candidate, eligible=not block, block_reasons=block,
            constraint_input_refs=tuple(f"/replay/candidates/{i}/{p}" for p in (
                "rule_item/tier_candidate", "rule_item/evidence_status", "bundle/status",
                "bundle/assessments", "rule_item/selected_claim_keys")),
            score=round(sum(c.contribution for c in components), config.score_decimals),
            features=features, components=components, history=history, protected=protected,
            reason_codes=(*block, *(f"{c.feature}_{'down' if c.contribution < 0 else 'up'}"
                for c in components if c.contribution), *history.reason_codes,
                "eligible_then_protected_then_score")))
    result.sort(key=lambda r: (not r.eligible, not r.protected, -r.score, r.event_key,
                               r.event_revision, r.item_id))
    return tuple(RevisitEvent.model_validate_json(json_bytes({**data(row), "rank": i}))
                 for i, row in enumerate(result, 1))


def replay_fields(envelope, stages, observations, identities):
    last = stages[-1]
    return RuntimeReplay(as_of=envelope.as_of, persona=envelope.persona,
        candidates=observations[-1].candidates, evidence=last.evidence,
        identity_state=last.grouping.next_state, observations=observations, document_archive=identities,
        source_coverage=last.replay_input.context.source_coverage,
        time_window_start=envelope.time_window_start, time_window_end=envelope.time_window_end,
        attention_budget_seconds=envelope.config.attention_budget_seconds)


def history_fields(envelope, stages, observations, identities):
    from .runtime_contracts import RuntimeHistoryInput
    from .runtime_history import project_history
    replay = replay_fields(envelope, stages, observations, identities)
    if envelope.schema_revision != "g4-h09-runtime-envelope-v2":
        return RuntimeHistoryInput(envelope=envelope, replay=replay)
    deliveries, old, journal = project_history(envelope, current().check)
    seen, archive = {}, []
    for observation in (*old, *observations):
        selected = []
        for candidate in observation.candidates:
            identifier = candidate.snapshot.snapshot_id
            core = data(candidate)
            core.pop("trace", None)
            core.pop("trace_pointer", None)
            core.pop("g2_view_sha256", None)
            if identifier in seen and seen[identifier] != core:
                raise LedgerError("G4_RUNTIME_HISTORY_SNAPSHOT_CONFLICT")
            if identifier not in seen:
                selected.append(candidate)
                seen[identifier] = core
        if selected:
            archive.append(observation.model_copy(update={"candidates": tuple(selected)}))
    fields = data(replay)
    published = {ref.snapshot_id: ref for delivery in deliveries for ref in delivery.items}
    fields.update(deliveries=[data(d) for d in deliveries], observations=[data(o) for o in archive],
                  published_refs=[data(ref) for ref in published.values()])
    value = RuntimeHistoryInput(envelope=envelope, replay=RuntimeReplay.model_validate_json(json_bytes(fields)), journal=journal)
    from evals.intelligence_g3.history import validate_input
    validate_input(value)
    return value


@controlled
def validate_context(value):
    from .g2_adapter import run_native
    stages, observations, identities, _ = run_native(value.envelope,
        sha256_bytes(json_bytes(value.envelope)), current().check)
    expected = history_fields(value.envelope, stages, observations, identities)
    if value != expected:
        raise LedgerError("G4_RUNTIME_CONTEXT_MISMATCH")


@controlled
def rank_runtime(value):
    from .runtime_contracts import RuntimeHistoryInput
    value = RuntimeHistoryInput.model_validate_json(json_bytes(value))
    validate_context(value)
    current().check("ranking_features")
    algorithm = value.envelope.config.algorithm
    pool = sorted((c.event.event_key, c.event.event_revision, c.rule_item.item_id,
                   c.snapshot.snapshot_id, c.g2_view_sha256) for c in value.replay.candidates)
    return RuntimeRanking(algorithm_id=algorithm, input_sha256=digest(value),
        config_sha256=digest(value.envelope.config), candidate_pool_sha256=digest(pool),
        fact_signature_policy_sha256=FACT_PIN, events=rows(value, algorithm, current().check),
        history_status="validated_sqlite_prefix_native_rules_v1" if value.envelope.history_prefix is not None else "not_integrated")


def plan_reasons(envelope, evidence):
    """A diagnostic native tier is never authorization for real Focus/Radar."""
    if envelope.record_origin != "real":
        return []
    reasons = []
    if any(d.rights in {"unknown", "metadata_only"} or d.provenance.startswith("legacy")
           for d in envelope.versions):
        reasons.append("G4_RUNTIME_RIGHTS_OR_LEGACY_NOT_EVIDENCE")
    if any(s.source_role == "other" for s in envelope.sources):
        reasons.append("G4_RUNTIME_SOURCE_UNRESOLVED")
    if any("independence_unknown" in b.uncertainties for b in evidence.bundles):
        reasons.append("G4_RUNTIME_REAL_INDEPENDENCE_UNRESOLVED")
    return reasons


@controlled
def plan_fields(value):
    from .runtime_contracts import RuntimeBudgetInput
    value = RuntimeBudgetInput.model_validate_json(json_bytes(value))
    if (value.ranking != rank_runtime(value.history_input)
            or data(value.config) != data(value.history_input.envelope.config.budget)):
        raise LedgerError("G4_RUNTIME_RANKING_BINDING_INVALID")
    if plan_reasons(value.history_input.envelope, value.history_input.replay.evidence):
        raise LedgerError("G4_RUNTIME_EVIDENCE_NOT_READY")
    current().check("budget_allocation")
    fields = native_budget.derive(value)
    current().check("budget_coverage")
    from .runtime import coverage
    fields["coverage"] = data(coverage(value.history_input.envelope,
        root="/history_input/replay/source_coverage"))
    return fields
