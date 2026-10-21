import math

import pytest
from test_loader import step


def test_score_all_hand_calculation_zeros_empty_query_and_han():
    from cfaw_news.retrieval import score_all, tokenize

    docs = [{"id": "b", "title": "", "summary": "alpha"},
            {"id": "a", "title": "", "summary": "beta"}]
    scored = score_all("alpha", docs)
    assert {d["id"]: d["retrieval_score"] for d in scored} == {
        "b": round(math.log(2), 5), "a": 0.0}
    assert len(score_all("", docs)) == 2
    assert all(d["retrieval_score"] == 0 for d in score_all("", docs))
    assert score_all("alpha", []) == []
    assert tokenize("中文会议 Mac") == ["中文", "文会", "会议", "mac"]


@pytest.mark.parametrize("algorithm", ["b0", "b1", "b2-predicted"])
def test_all_candidates_and_zero_scores_survive_beyond_eight(algorithm):
    from evals.intelligence_v1.baselines import get_ranker
    from evals.intelligence_v1.contracts import BaselineConfig

    context, docs = step(name="D0")
    candidates = tuple(docs[0].model_copy(update={
        "document_id": f"doc:{i:02}", "doc_version_id": f"doc:{i:02}:1",
        "canonical_url": None, "content_sha256": None, "title": "zzzz",
        "text_excerpt": None, "paragraphs": (),
    }) for i in range(12))
    context = context.model_copy(update={
        "candidate_doc_version_ids": tuple(d.doc_version_id for d in candidates)})
    ranked = get_ranker(algorithm, BaselineConfig()).rank(context, candidates)
    assert len(ranked) == 12
    assert [r.representative_doc_version_id for r in ranked] == [d.doc_version_id for d in candidates]
    if algorithm != "b0":
        assert all(r.score == 0 for r in ranked)


def test_B0_uses_availability_and_B1_query_is_fixed():
    from evals.intelligence_v1.baselines import get_ranker, persona_query
    from evals.intelligence_v1.contracts import BaselineConfig

    context, candidates = step(name="D8")
    assert persona_query(context.persona) == (
        "Agent development evaluation Assess tools for a Windows CPU workstation Windows CPU only")
    ranked = get_ranker("b0", BaselineConfig()).rank(context, candidates)
    assert [r.representative_doc_version_id for r in ranked] == [
        "d01:f:1", "d01:a:2", "d01:e:1", "d01:c:1", "d01:d:1", "d01:b:1"]


def test_positive_score_corpus_has_no_implicit_topk_and_legacy_search_is_unchanged():
    from cfaw_news.retrieval import score_all, search

    docs = [{"id": f"a:{i:02}", "title": "alpha", "summary": "alpha beta"} for i in range(15)]
    all_scores = score_all("alpha beta", docs)
    old = search({"name": "alpha", "purpose": "beta"}, docs)
    assert len(all_scores) == 15 and all(r["retrieval_score"] > 0 for r in all_scores)
    assert old == all_scores[:8]
    assert search({"name": "zzzz", "purpose": ""}, docs) == []
