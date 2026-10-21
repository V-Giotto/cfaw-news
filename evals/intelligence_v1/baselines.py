"""Pure B0-B4 ranking. No dataset IO or reference-answer imports."""

from dataclasses import dataclass
from typing import Protocol

from cfaw_news.retrieval import score_all

from .contracts import CandidateDocumentVersion, RankedItem, ReplayContext, ScoreComponents
from .exceptions import ContractError
from .grouping import group_candidates
from .history import exposure_adjustment
from .temporal import require_visible_version


class RankerProtocol(Protocol):
    def rank(self, context: ReplayContext,
             candidates: tuple[CandidateDocumentVersion, ...]) -> tuple[RankedItem, ...]: ...


def persona_query(persona):
    return " ".join((*persona.domain_interests, *persona.current_goals, *persona.hard_constraints))


def checked_candidates(context, candidates):
    ids = [d.doc_version_id for d in candidates]
    if len(set(ids)) != len(ids) or set(ids) != set(context.candidate_doc_version_ids):
        raise ContractError("VISIBLE_SET_MISMATCH")
    for candidate in candidates:
        require_visible_version(candidate, as_of=context.as_of)
    return {d.doc_version_id: d for d in candidates}


def candidate_scores(context, candidates):
    rows = [{"id": d.doc_version_id, "title": d.title,
             "summary": "\n".join([d.text_excerpt or "", *(p.text for p in d.paragraphs)])}
            for d in sorted(candidates, key=lambda d: d.doc_version_id)]
    return {r["id"]: r["retrieval_score"] for r in score_all(persona_query(context.persona), rows)}


def rank_groups(context, candidates, groups):
    by_id = checked_candidates(context, candidates)
    members = [v for g in groups for v in g.doc_version_ids]
    if len(set(members)) != len(members) or set(members) != set(by_id):
        raise ContractError("GROUP_MEMBERS_INVALID")
    scores = candidate_scores(context, candidates)
    ranked = []
    for group in groups:
        representative = min(group.doc_version_ids, key=lambda key: (-scores[key], key))
        ranked.append(RankedItem(rank=1, doc_version_ids=group.doc_version_ids,
            representative_doc_version_id=representative,
            representative_source_id=by_id[representative].source_id, score=scores[representative],
            score_components=ScoreComponents(bm25=scores[representative], aggregation="max"),
            predicted_event_id=group.predicted_event_id, merge_reasons=group.merge_reasons,
            evidence_independence=group.evidence_independence))
    ranked.sort(key=lambda r: (-r.score, r.representative_doc_version_id, r.predicted_event_id))
    return tuple(r.model_copy(update={"rank": i}) for i, r in enumerate(ranked, 1))


@dataclass(frozen=True)
class BaselineRanker:
    algorithm_id: str
    config: object
    half_life_days: int = 7

    def rank(self, context, candidates):
        by_id = checked_candidates(context, candidates)
        if self.algorithm_id in {"b2-predicted", "b3", "b4"}:
            ranked = rank_groups(context, candidates, group_candidates(candidates, self.config))
            if self.algorithm_id == "b2-predicted":
                return ranked
            maximum = max((r.score for r in ranked), default=0)
            weighted = []
            for item in ranked:
                latest = max(by_id[v].available_at for v in item.doc_version_ids)
                age = max(0, (context.as_of-latest).total_seconds()/86400)
                norm = item.score/maximum if maximum else 0.0
                recency = 2**(-age/self.half_life_days)
                base = self.config.bm25_weight*norm + self.config.recency_weight*recency
                adjustment = (exposure_adjustment(context, candidates, item, self.config)
                              if self.algorithm_id == "b4" else {})
                components = item.score_components.model_copy(update={"bm25_norm": norm,
                    "age_days": age, "recency": recency, "half_life_days": self.half_life_days,
                    "latest_visible_material_at": latest, "base_score": base, **adjustment})
                weighted.append(item.model_copy(update={"score_components": components,
                    "score": round(base-adjustment.get("penalty", 0), self.config.score_decimals)}))
            weighted.sort(key=lambda r: (-r.score, r.representative_doc_version_id,
                                         r.predicted_event_id))
            return tuple(r.model_copy(update={"rank": i}) for i, r in enumerate(weighted, 1))
        if self.algorithm_id == "b0":
            ordered = sorted(candidates, key=lambda d: d.doc_version_id)
            ordered.sort(key=lambda d: d.available_at, reverse=True)
            scores = {}
        else:
            scores = candidate_scores(context, candidates)
            ordered = sorted(candidates, key=lambda d: (-scores[d.doc_version_id], d.doc_version_id))
        return tuple(RankedItem(rank=i, doc_version_ids=(d.doc_version_id,),
            representative_doc_version_id=d.doc_version_id, representative_source_id=d.source_id,
            score=scores.get(d.doc_version_id), score_components=(
                ScoreComponents(available_at=d.available_at) if self.algorithm_id == "b0"
                else ScoreComponents(bm25=scores[d.doc_version_id])))
            for i, d in enumerate(ordered, 1))


def get_ranker(algorithm_id, config, *, half_life_days=None):
    if algorithm_id == "b2-oracle":
        raise ContractError("ORACLE_REQUIRES_EXPLICIT_PATH")
    if algorithm_id not in {"b0", "b1", "b2-predicted", "b3", "b4"}:
        raise ContractError("UNKNOWN_ALGORITHM")
    half = config.half_life_days if half_life_days is None else half_life_days
    if type(half) is not int or half not in config.registered_half_lives:
        raise ContractError("UNREGISTERED_EXPERIMENT")
    return BaselineRanker(algorithm_id, config, half)
