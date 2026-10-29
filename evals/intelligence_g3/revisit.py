"""PR3 ranking adapter: explicit history, conservative migration, protected updates."""

from typing import Annotated, Literal

from pydantic import Field

from evals.intelligence_g2.contracts import data, digest
from evals.intelligence_v1.contracts import NonEmpty, StrictModel

from .contracts import fail
from .fact_signature import REVISION as FACT_REVISION
from .fact_signature import persona_content, policy, policy_sha256
from .history import active_events, candidate_archive, resolve_target
from .history_contracts import HistoryConfig, HistoryInput
from .history_contracts import parse_history as parse
from .rankers import _claims, _contributions, _feature, rank
from .ranking_contracts import Algorithm, RankedEvent, RankingConfig, RankingResult


class HistoryFeatures(StrictModel):
    declared_known: bool
    delivery_count: Annotated[int, Field(ge=0)]
    resolved_snapshot_ids: tuple[NonEmpty, ...]
    mapping_statuses: tuple[NonEmpty, ...]
    promotion: Literal["none", "correction", "withdrawal", "material_change"]
    coverage_statuses: tuple[NonEmpty, ...]
    input_refs: tuple[NonEmpty, ...]
    reason_codes: tuple[NonEmpty, ...]


class RevisitEvent(RankedEvent):
    history: HistoryFeatures
    protected: bool


class RevisitResult(RankingResult):
    schema_revision: Literal["g3-pr3-ranking-v1"] = "g3-pr3-ranking-v1"
    config: HistoryConfig
    base_config: RankingConfig
    events: tuple[RevisitEvent, ...]
    scope: Literal["offline_synthetic_revisit_no_budget_or_quality_claim"] = (
        "offline_synthetic_revisit_no_budget_or_quality_claim")


def _prefix(feature):
    return feature.model_copy(update={"input_refs": tuple("/replay" + p for p in feature.input_refs)})


def _history_features(value, candidate, config):
    replay = value.replay
    archive = candidate_archive(replay)
    current = _claims(candidate, replay.evidence, "/replay/evidence")
    refs = [p for paths in current.values() for p in paths]
    refs += ["/journal/entries", "/mappings", "/replay/deliveries"]
    ci = next(i for i, c in enumerate(replay.candidates) if c == candidate)
    refs += [f"/replay/candidates/{ci}/bundle/assessments",
             f"/replay/candidates/{ci}/rule_item/selected_claim_keys",
             f"/replay/candidates/{ci}/event/lineage_ids", "/replay/identity_state/transitions"]
    matches, statuses, uncertain = [], [], False
    for di, delivery in enumerate(replay.deliveries):
        for ri, target in enumerate(delivery.items):
            status, mapping_refs = resolve_target(value, target, candidate)
            statuses.append(f"{target.snapshot_id}:{status}")
            if status == "unmapped_target":
                continue
            refs += [f"/replay/deliveries/{di}", f"/replay/deliveries/{di}/items/{ri}", *mapping_refs]
            if status in {"uncertain_mapping", "missing_explicit_mapping"}:
                uncertain = True
                continue
            old, observation, candidate_ref, evidence_ref = archive[target.snapshot_id]
            claims = _claims(old, observation.evidence, evidence_ref)
            refs += [candidate_ref, *(r for paths in claims.values() for r in paths)]
            matches.append((delivery, target, claims))
    # Only unresolved rows are excluded above. Exact current history and confirmed
    # migrations remain usable even when another ancestral branch is uncertain.
    active = active_events(value.journal)
    signals, known, explicit_not_known = set(), set(), False
    for delivery, target, claims in matches:
        signals.add("included")
        knowledge = None
        for hi, event in active:
            if event.delivery_id != delivery.delivery.delivery_id or event.target != target:
                continue
            refs.append(f"/journal/entries/{hi}/event")
            signals.add(event.kind if event.kind != "feedback" else f"feedback:{event.feedback}")
            if event.kind == "acknowledged" or event.feedback == "known":
                knowledge = True
            elif event.feedback == "not_known":
                knowledge = False
                # Unretracted conflicting declarations remain unknown regardless of
                # occurrence/arrival order. Correct them through an explicit retraction.
                explicit_not_known = True
        if knowledge:
            known.update(claims)
        elif knowledge is False:
            explicit_not_known = True
    # Retraction records are sources for the reducer, including withdrawn knowledge.
    refs += [f"/journal/entries/{i}" for i, e in enumerate(value.journal.entries)
             if any(e.event.target == m[1] for m in matches)]
    persona_known = {persona_content(k) for k in replay.persona.persona.knowledge_known}
    effective_known = known | {s for s in current if s.content in persona_known}
    if explicit_not_known:
        effective_known.clear()
    declared = bool(current) and set(current) <= effective_known
    refs.append("/replay/persona/persona/knowledge_known")
    # Use one earliest and latest delivered statement set per historical event identity.
    # Earliest is the pending-change anchor until explicitly acknowledged; latest tests repeats.
    groups = {}
    for match in matches:
        groups.setdefault(match[1].event_key, []).append(match)
    earliest, latest = set(), set()
    for group in groups.values():
        ordered = sorted(group, key=lambda m: (m[0].delivery.generated_at, m[1].as_of,
                                               m[0].delivery.delivery_id, m[1].snapshot_id))
        earliest.update(ordered[0][2])
        latest.update(ordered[-1][2])
    increment = set(current) - earliest if matches else set()
    pending_markers = {s.marker for s in set(current) - effective_known}
    promotion = "none"
    if current and not declared:
        if "withdrawal" in pending_markers:
            promotion = "withdrawal"
        elif "correction" in pending_markers:
            promotion = "correction"
        elif increment:
            promotion = "material_change"
    unchanged = bool(current) and set(current) == latest
    weights = {"included": config.included_penalty, "rendered": config.rendered_penalty,
               "acknowledged": config.acknowledged_penalty, "dismissed": config.dismissed_penalty,
               "feedback:known": config.acknowledged_penalty,
               "feedback:irrelevant": config.irrelevant_penalty}
    # known feedback and acknowledgment are the same explicit knowledge class, counted once.
    penalty_signals = signals - {"feedback:known"} if "acknowledged" in signals else signals
    if not declared:
        penalty_signals = penalty_signals - {"acknowledged", "feedback:known"}
    deliveries = len({m[0].delivery.delivery_id for m in matches})
    penalty = min(config.penalty_cap, sum(weights.get(s, 0) for s in penalty_signals)
                  + max(0, deliveries - 1) * config.repeated_delivery_penalty) if unchanged else 0.0
    if promotion != "none":
        penalty = 0.0
    coverage = tuple(sorted({c.status for c in replay.source_coverage})) or ("unknown",)
    reasons = ["explicit_knowledge_only", "opened_never_implies_acknowledged",
               "included_from_bound_delivery_only", "statement_sets_not_document_counts"]
    if explicit_not_known:
        reasons.append("explicit_not_known_vetoes_knowledge")
    if uncertain:
        reasons.append("uncertain_history_no_inherited_knowledge_or_penalty")
    if any(s.endswith(":unmapped_target") for s in statuses):
        reasons.append("unmapped_history_preserved_without_identity_inference")
    if promotion != "none":
        reasons.append(f"pending_{promotion}_protected_from_repeat_penalty")
    if any(s != "covered" for s in coverage):
        reasons.append("coverage_gap_no_claim_of_no_updates")
    return (HistoryFeatures(declared_known=declared, delivery_count=deliveries,
        resolved_snapshot_ids=tuple(sorted({m[1].snapshot_id for m in matches})),
        mapping_statuses=tuple(sorted(set(statuses))), promotion=promotion,
        coverage_statuses=coverage, input_refs=tuple(sorted(set([*refs, "/replay/source_coverage"]))),
        reason_codes=tuple(reasons)), tuple(sorted(signals)), penalty)


def rank_revisit(value: HistoryInput, algorithm: Algorithm = "p1") -> RevisitResult:
    if not isinstance(value, HistoryInput):
        fail("G3_SCHEMA_INVALID", "HistoryInput")
    # Revalidate direct model_copy/model_construct and serialized inputs identically.
    value = parse(HistoryInput, data(value))
    config, base_config = HistoryConfig(), RankingConfig()
    base = rank(value.replay, algorithm)
    candidates = {c.event.event_key: c for c in value.replay.candidates}
    rows = []
    for row in base.events:
        history, signals, penalty = _history_features(value, candidates[row.event_key], config)
        protected = row.eligible and history.promotion != "none"
        updates = {name: _prefix(getattr(row.features, name)) for name in
                   ("bm25", "relevance", "recency")}
        updates.update(
            novelty=_feature(float(not history.declared_known) if row.eligible else 0,
                             history.input_refs, "explicit_known" if history.declared_known else
                             "no_explicit_knowledge_not_proof_of_unfamiliarity"),
            material_change=_feature(float(protected), history.input_refs, history.promotion),
            duplicate=_feature(penalty, history.input_refs, "protected_update" if protected else
                               "unchanged_delivered_statements" if penalty else "no_safe_repeat_penalty"),
            exploration=_feature(row.features.exploration.value if not history.delivery_count
                                 and not history.declared_known and not any(
                                     "uncertain" in s or "missing_explicit" in s
                                     for s in history.mapping_statuses) else 0,
                                 [*history.input_refs, *_prefix(row.features.exploration).input_refs],
                                 "bounded_explicit_unseen_exploration"),
            exposure_signals=signals, history_delivery_id=None)
        features = row.features.model_copy(update=updates)
        components = _contributions(algorithm, features, base_config)
        score = sum(c.contribution for c in components)
        if algorithm != "b0":
            score = round(score, base_config.score_decimals)
        rows.append(parse(RevisitEvent, {**data(row), "features": data(features),
            "components": [data(c) for c in components], "score": score, "history": data(history),
            "protected": protected, "constraint_input_refs": tuple("/replay" + p for p in
                row.constraint_input_refs), "reason_codes": (*row.block_reasons,
                *(f"{c.feature}_{'down' if c.contribution < 0 else 'up'}" for c in components if c.contribution),
                *history.reason_codes, "eligible_then_protected_then_score" if algorithm in {"b4", "p1"}
                else "baseline_order_preserved")}))
    rows.sort(key=lambda r: (not r.eligible, not r.protected if algorithm in {"b4", "p1"} else False,
                             -r.score, r.event_key, r.event_revision, r.item_id))
    config_hash = digest(dict(history=data(config), base=data(base_config), fact_signature=policy()))
    input_hash = digest(value)
    return parse(RevisitResult, {**data(base), "schema_revision": "g3-pr3-ranking-v1",
        "config": data(config), "base_config": data(base_config),
        "algorithm_version": f"g3-{algorithm}-revisit-v1", "config_sha256": config_hash,
        "input_sha256": input_hash, "comparison_sha256": digest(dict(input_sha256=input_hash,
            config_sha256=config_hash, candidate_pool_sha256=base.candidate_pool_sha256)),
        "events": [data(r.model_copy(update={"rank": i})) for i, r in enumerate(rows, 1)],
        "diagnostics": ("explicit_g2_lineage_history_mapping", "all_history_as_of_filtered",
            "fact_signature_revision:" + FACT_REVISION,
            "fact_signature_policy_sha256:" + policy_sha256(),
            "coverage_gaps_do_not_mean_no_world_change", "statement_delta_is_not_semantic_validation"),
        "scope": "offline_synthetic_revisit_no_budget_or_quality_claim"})


def compare_revisit(value: HistoryInput):
    return tuple(rank_revisit(value, algorithm) for algorithm in ("b0", "b1", "b2", "b3", "b4", "p1"))
