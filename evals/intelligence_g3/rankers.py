"""Pure G3 event adapters. No grouping, labels, dataset IO or inferred knowledge."""

from types import SimpleNamespace

from evals.intelligence_g2.contracts import data, digest
from evals.intelligence_v1.baselines import candidate_scores

from .bridge import preflight
from .contracts import G3ReplayInput, fail, parse
from .fact_signature import REVISION as FACT_REVISION
from .fact_signature import persona_content, policy_sha256, signature
from .ranking_contracts import (
    ALGORITHM_VERSIONS,
    Contribution,
    Feature,
    RankedEvent,
    RankingConfig,
    RankingFeatures,
    RankingResult,
)


def registered_config(config=None):
    # One a-priori policy, not a tuning API. New policies require a new registration.
    value = parse(RankingConfig, data(config)) if config is not None else RankingConfig()
    if value != RankingConfig():
        fail("G3_RANK_CONFIG_INVALID", "registered_ranking_config")
    return value


def _feature(value, refs, reason):
    return Feature(value=value, input_refs=tuple(sorted(set(refs))), reason=reason)


def _claims(candidate, evidence, prefix):
    """Cited source attributions, not independent truth or counts of sources."""
    selected = set(candidate.rule_item.selected_claim_keys)
    assessments = {a.claim_key: a for a in candidate.bundle.assessments}
    result = {}
    for index, claim in enumerate(evidence.claims):
        assessment = assessments.get(claim.claim_key)
        if (claim.claim_key not in selected or not claim.evidence_ref_ids or assessment is None
                or assessment.verification_state != "source_attributed"
                or (assessment.lifecycle != "current" and claim.marker == "none")):
            continue
        # Statement content, not doc/claim IDs: reprints cannot manufacture novelty.
        fact = signature(claim)
        result.setdefault(fact, []).append(f"{prefix}/claims/{index}")
    return result


def _history(value, candidate):
    key = candidate.event.event_key
    matches = [(i, d, j, ref) for i, d in enumerate(value.deliveries)
               for j, ref in enumerate(d.items) if ref.event_key == key]
    if not matches:
        return None, (), (), ()
    index, delivery, j, ref = max(matches, key=lambda m: (
        m[1].delivery.generated_at, m[1].delivery.as_of, m[1].delivery.delivery_id,
        m[3].snapshot_id))
    path = f"/deliveries/{index}"
    refs = [f"{path}/items/{j}", f"{path}/delivery"]
    signals = {"included"}
    for i, h in enumerate(value.history):
        if h.delivery_id == delivery.delivery.delivery_id and h.target == ref:
            signals.add(h.kind)
            refs.append(f"/history/{i}")
    for oi, observation in enumerate(value.observations):
        for ci, previous in enumerate(observation.candidates):
            if previous.snapshot.snapshot_id == ref.snapshot_id:
                return (index, delivery, ref, oi, ci, previous), tuple(sorted(signals)), refs, matches
    # PR1 validates this; never silently treat an unresolved target as unseen.
    fail("G3_REFERENCE_NOT_FOUND", "ranking.history_snapshot")


def _features(value, candidate, ci, bm25, maximum, config, pool_refs):
    root = f"/candidates/{ci}"
    item = candidate.rule_item
    current = _claims(candidate, value.evidence, "/evidence")
    support_refs = [r for paths in current.values() for r in paths]
    support_refs += [f"{root}/rule_item/selected_claim_keys", f"{root}/bundle/assessments"]
    block = []
    if item.tier_candidate == "hold":
        block.append("g2_hold")
    if item.evidence_status == "insufficient" or candidate.bundle.status == "insufficient":
        block.append("g2_evidence_insufficient")
    if not current:
        block.append("no_cited_attributed_claim")
    eligible = not block
    # G1 uses availability, never publisher timestamps or the replay observation time.
    pointers = [(i, p) for i, p in enumerate(item.source_pointers)
                if p.doc_version_id in candidate.event.member_doc_version_ids]
    latest = max((p.available_at for _, p in pointers), default=None)
    age = max(0.0, (value.as_of - latest).total_seconds() / 86400) if latest else None
    recency = 2 ** (-age / config.half_life_days) if age is not None else 0.0
    time_refs = [f"{root}/rule_item/source_pointers/{i}/available_at" for i, _ in pointers]
    time_refs += ["/as_of", f"{root}/event/member_doc_version_ids"]
    norm = bm25 / maximum if maximum else 0.0
    previous, signals, history_refs, matches = _history(value, candidate)
    change, unchanged = False, False
    change_refs = list(support_refs)
    if previous:
        _, _, _, oi, pci, prior = previous
        old = _claims(prior, value.observations[oi].evidence, f"/observations/{oi}/evidence")
        change_refs += [r for paths in old.values() for r in paths]
        change_refs += [f"/observations/{oi}/candidates/{pci}", *history_refs]
        change = bool(set(current) - set(old))
        unchanged = bool(current) and set(current) == set(old)
    # Only explicit, exact statement knowledge. Opening never means knowing.
    known_statements = {persona_content(k) for k in value.persona.persona.knowledge_known}
    explicit_known = bool(current) and all(sig.content in known_statements for sig in current)
    known_refs = ["/persona/persona/knowledge_known", *support_refs]
    acknowledged = False
    for hi, h in enumerate(value.history):
        if h.kind != "acknowledged" or h.target.event_key != candidate.event.event_key:
            continue
        known_refs.append(f"/history/{hi}")
        for oi, observation in enumerate(value.observations):
            for pci, prior in enumerate(observation.candidates):
                if prior.snapshot.snapshot_id == h.target.snapshot_id:
                    old = _claims(prior, observation.evidence, f"/observations/{oi}/evidence")
                    known_refs.append(f"/observations/{oi}/candidates/{pci}")
                    known_refs += [r for paths in old.values() for r in paths]
                    acknowledged |= bool(current) and set(current) <= set(old)
    novelty = float(not (explicit_known or acknowledged)) if current else 0.0
    weights = {"included": config.included_penalty, "rendered": config.rendered_penalty,
               "acknowledged": config.acknowledged_penalty}
    penalty = sum(weights.get(s, 0.0) for s in signals) if unchanged else 0.0
    preference = value.persona.persona.exploration_preference.strip().casefold()
    exploration = (config.exploration_cap * (1 - norm)
                   if eligible and novelty and not matches
                   and preference in config.exploration_preferences else 0.0)
    features = RankingFeatures(
        bm25=_feature(bm25, pool_refs, "g1_persona_query_bm25_event_projection"),
        relevance=_feature(norm, pool_refs, "pool_max_normalized_zero_if_zero"),
        novelty=_feature(novelty, known_refs, "explicit_known" if explicit_known else
                         "acknowledged_current_evidence" if acknowledged else
                         "no_explicit_knowledge_not_proof_of_unfamiliarity"),
        material_change=_feature(float(change), change_refs, "new_cited_statement_since_delivery"
                                 if change else "no_supported_increment_observed"),
        recency=_feature(recency, time_refs, "availability_half_life" if latest else
                         "missing_material_time_zero"),
        duplicate=_feature(penalty, [*change_refs, *history_refs],
                           "same_observed_statements_distinct_exposure_signals" if unchanged else
                           "supported_change_or_unknown_no_penalty"),
        exploration=_feature(exploration, [*pool_refs, *known_refs, "/deliveries",
                                          "/persona/persona/exploration_preference"],
                             "bounded_unseen_eligible_exploration"),
        latest_material_at=latest, age_days=age,
        history_delivery_id=previous[1].delivery.delivery_id if previous else None,
        exposure_signals=signals)
    return features, tuple(block)


def _contributions(algorithm, features, config):
    if algorithm == "b0":
        stamp = features.latest_material_at
        return (Contribution(feature="available_at_epoch_seconds",
                raw_value=stamp.timestamp() if stamp else config.missing_b0_score, weight=1,
                contribution=stamp.timestamp() if stamp else config.missing_b0_score,
                input_refs=features.recency.input_refs),)
    if algorithm in {"b1", "b2"}:
        terms = (("bm25", 1),)
    elif algorithm in {"b3", "b4"}:
        terms = (("relevance", config.baseline_relevance_weight),
                 ("recency", config.baseline_recency_weight))
        if algorithm == "b4":
            terms += (("duplicate", -1),)
    else:
        terms = tuple((name, getattr(config, f"{name}_weight")) for name in
                      ("relevance", "novelty", "material_change", "recency", "exploration", "duplicate"))
    return tuple(Contribution(feature=name, raw_value=getattr(features, name).value,
                 weight=weight, contribution=getattr(features, name).value * weight,
                 input_refs=getattr(features, name).input_refs) for name, weight in terms)


def rank(value: G3ReplayInput, algorithm: str, config=None) -> RankingResult:
    """Rank every candidate, with ineligible rows retained after eligible rows."""
    if algorithm not in ALGORITHM_VERSIONS:
        fail("G3_UNKNOWN_RANKER", "algorithm_id")
    config = registered_config(config)
    if not isinstance(value, G3ReplayInput):
        fail("G3_SCHEMA_INVALID", "G3ReplayInput")
    preflight(value, value.as_of)
    value = parse(G3ReplayInput, data(value))
    rows, pool_refs = [], ["/persona/persona/domain_interests", "/persona/persona/current_goals",
                           "/persona/persona/hard_constraints"]
    for i, candidate in enumerate(value.candidates):
        item = candidate.rule_item
        rows.append(SimpleNamespace(doc_version_id=candidate.event.event_key,
            title=item.headline.text if item.headline else "", paragraphs=(),
            text_excerpt="\n".join(s.statement.text for s in item.claim_summaries
                                   if s.claim_key in item.selected_claim_keys)))
        pool_refs += [f"/candidates/{i}/rule_item/headline",
                      f"/candidates/{i}/rule_item/claim_summaries",
                      f"/candidates/{i}/rule_item/selected_claim_keys"]
    scores = candidate_scores(SimpleNamespace(persona=value.persona.persona), tuple(rows))
    maximum = max(scores.values(), default=0.0)
    events = []
    for i, candidate in enumerate(value.candidates):
        features, block = _features(value, candidate, i, scores[candidate.event.event_key],
                                    maximum, config, pool_refs)
        components = _contributions(algorithm, features, config)
        score = sum(c.contribution for c in components)
        if algorithm != "b0":
            score = round(score, config.score_decimals)
        events.append(RankedEvent(rank=1, event_key=candidate.event.event_key,
            event_revision=candidate.event.event_revision, item_id=candidate.rule_item.item_id,
            snapshot_id=candidate.snapshot.snapshot_id, g2_view_sha256=candidate.g2_view_sha256,
            g2_tier_candidate=candidate.rule_item.tier_candidate, eligible=not block,
            block_reasons=block, constraint_input_refs=(f"/candidates/{i}/rule_item/tier_candidate",
                f"/candidates/{i}/rule_item/evidence_status", f"/candidates/{i}/bundle/status",
                f"/candidates/{i}/bundle/assessments", f"/candidates/{i}/rule_item/selected_claim_keys"),
            score=score, features=features, components=components,
            reason_codes=tuple([*block, *(f"{c.feature}_{'down' if c.contribution < 0 else 'up'}"
                for c in components if c.contribution), "stable_event_identity_tie_break"])))
    events.sort(key=lambda e: (not e.eligible, -e.score, e.event_key, e.event_revision, e.item_id))
    pool_hash = digest(sorted((c.event.event_key, c.event.event_revision, c.rule_item.item_id,
                               c.snapshot.snapshot_id, c.g2_view_sha256) for c in value.candidates))
    input_hash, config_hash = digest(value), digest(config)
    return RankingResult(algorithm_id=algorithm, algorithm_version=ALGORITHM_VERSIONS[algorithm],
        config=config, config_sha256=config_hash, input_sha256=input_hash,
        comparison_sha256=digest(dict(input_sha256=input_hash, config_sha256=config_hash,
                                     candidate_pool_sha256=pool_hash,
                                     fact_signature_policy_sha256=policy_sha256())),
        candidate_pool_sha256=pool_hash, as_of=value.as_of,
        persona_version_id=value.persona.persona.persona_version_id,
        attention_budget_seconds=value.attention_budget_seconds,
        events=tuple(e.model_copy(update={"rank": i}) for i, e in enumerate(events, 1)),
        diagnostics=("g2_events_not_regrouped", "history_exact_event_only_no_alias_inheritance",
                     "fact_signature_revision:" + FACT_REVISION,
                     "fact_signature_policy_sha256:" + policy_sha256(),
                     "coverage_gaps_do_not_mean_no_world_change",
                     "free_text_persona_constraints_are_lexical_query_terms",
                     "no_independent_support_or_semantic_materiality_claim"))


def compare(value: G3ReplayInput, config=None) -> tuple[RankingResult, ...]:
    """One pool/context/config; no labels, budget selection or metric evaluation."""
    return tuple(rank(value, algorithm, config) for algorithm in ALGORITHM_VERSIONS)
