"""Pure B0/B1/B2-predicted ranking. No dataset IO or reference-answer imports."""

from dataclasses import dataclass
from typing import Protocol

from cfaw_news.retrieval import score_all

from .contracts import CandidateDocumentVersion, RankedItem, ReplayContext, ScoreComponents
from .exceptions import ContractError
from .grouping import group_candidates
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

    def rank(self, context, candidates):
        checked_candidates(context, candidates)
        if self.algorithm_id == "b2-predicted":
            return rank_groups(context, candidates, group_candidates(candidates, self.config))
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


def get_ranker(algorithm_id, config):
    if algorithm_id == "b2-oracle":
        raise ContractError("ORACLE_REQUIRES_EXPLICIT_PATH")
    if algorithm_id not in {"b0", "b1", "b2-predicted"}:
        raise ContractError("UNKNOWN_ALGORITHM")
    return BaselineRanker(algorithm_id, config)
