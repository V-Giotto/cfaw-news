import math

import pytest
from test_loader import step


def history_context(context, docs, *, kinds=("included",), hash_value=None):
    from evals.intelligence_v1.contracts import (
        DeliveryItemSnapshot,
        HistoricalDocument,
        VisibleDeliveryItem,
        VisibleExposure,
    )

    doc = docs[0]
    snapshot = DeliveryItemSnapshot(delivery_id="history:d0", event_prediction_id="predicted:old",
        members=(HistoricalDocument(document_id=doc.document_id, doc_version_id="old:1",
            content_sha256=hash_value or doc.content_sha256),))
    visible = VisibleDeliveryItem(**snapshot.model_dump(), delivery_as_of=context.as_of,
                                 delivery_generated_at=context.as_of)
    exposures = tuple(VisibleExposure(exposure_id=f"history:{n}", delivery_id="history:d0",
        event_prediction_id="predicted:old", kind=kind, occurred_at=context.as_of,
        source="synthetic_fixture") for n, kind in enumerate(kinds))
    return context.model_copy(update={"delivery_history": (visible,), "exposure_history": exposures})


def test_B3_normalization_and_exact_half_life_without_gold():
    from datetime import timedelta

    from evals.intelligence_v1.baselines import get_ranker
    from evals.intelligence_v1.contracts import BaselineConfig

    context, docs = step(name="D0")
    context = context.model_copy(update={"as_of": docs[0].available_at + timedelta(days=7)})
    item, = get_ranker("b3", BaselineConfig()).rank(context, docs)
    c = item.score_components
    assert c.bm25_norm == 1 and c.recency == pytest.approx(.5)
    assert item.score == pytest.approx(.875)
    assert c.latest_visible_material_at == docs[0].available_at
    assert c.half_life_days == 7 and c.age_days == 7


@pytest.mark.parametrize("half", [3, 7, 14])
def test_B3_registered_half_lives_and_zero_scores(half):
    from evals.intelligence_v1.baselines import get_ranker
    from evals.intelligence_v1.contracts import BaselineConfig

    context, docs = step(name="D0")
    context = context.model_copy(update={"persona": context.persona.model_copy(update={
        "domain_interests": (), "current_goals": (), "hard_constraints": ()})})
    item, = get_ranker("b3", BaselineConfig(), half_life_days=half).rank(context, docs)
    assert item.score_components.bm25_norm == 0
    assert math.isfinite(item.score)


@pytest.mark.parametrize("kinds,penalty", [(("included",), .1), (("rendered",), .2),
    (("opened",), .1), (("acknowledged",), .35), (("dismissed",), .1),
    (("included", "rendered", "opened", "acknowledged", "acknowledged"), .45)])
def test_T11_T12_explicit_history_signal_penalties_and_no_knowledge_inference(kinds, penalty):
    from evals.intelligence_v1.baselines import get_ranker
    from evals.intelligence_v1.contracts import BaselineConfig

    context, docs = step(name="D0")
    old_known = context.persona.knowledge_known
    context = history_context(context, docs, kinds=kinds)
    b3, = get_ranker("b3", BaselineConfig()).rank(context, docs)
    b4, = get_ranker("b4", BaselineConfig()).rank(context, docs)
    assert b4.score == pytest.approx(b3.score-penalty, abs=1e-5)
    assert b4.score_components.penalty == pytest.approx(penalty)
    assert b4.score_components.text_delta == "no_change"
    assert set(kinds) <= set(b4.score_components.exposure_signals)
    assert context.persona.knowledge_known == old_known
    assert b4.predicted_event_id != "predicted:old"


def test_T13_new_visible_text_clears_penalty_without_claiming_correction():
    from evals.intelligence_v1.baselines import get_ranker
    from evals.intelligence_v1.contracts import BaselineConfig

    context, docs = step(name="D0")
    context = history_context(context, docs, kinds=("acknowledged",), hash_value="0"*64)
    item, = get_ranker("b4", BaselineConfig()).rank(context, docs)
    assert item.score_components.penalty == 0
    assert item.score_components.text_delta == "new_text"
    assert "correction" not in item.model_dump_json()


def test_B4_unknown_hash_is_not_no_change_and_signed_scores_are_preserved():
    from datetime import timedelta

    from evals.intelligence_v1.baselines import get_ranker
    from evals.intelligence_v1.contracts import BaselineConfig, RankedItem

    context, docs = step(name="D0")
    context = context.model_copy(update={"as_of": context.as_of+timedelta(days=100),
        "persona": context.persona.model_copy(update={"domain_interests": (),
            "current_goals": (), "hard_constraints": ()})})
    history = history_context(context, docs, kinds=("acknowledged", "rendered"))
    item, = get_ranker("b4", BaselineConfig()).rank(history, docs)
    assert item.score < 0
    assert RankedItem.model_validate_json(item.model_dump_json()).score == item.score
    unknown = (docs[0].model_copy(update={"content_sha256": None}),)
    item, = get_ranker("b4", BaselineConfig()).rank(history, unknown)
    assert item.score_components.text_delta == "unknown" and item.score_components.penalty == 0


def test_T14_candidates_are_not_filtered_to_last_24_hours():
    from evals.intelligence_v1.baselines import get_ranker
    from evals.intelligence_v1.contracts import BaselineConfig

    context, docs = step(name="D8")
    for algorithm in ("b3", "b4"):
        ranked = get_ranker(algorithm, BaselineConfig()).rank(context, docs)
        assert {v for r in ranked for v in r.doc_version_ids} == {d.doc_version_id for d in docs}
        assert ranked == get_ranker(algorithm, BaselineConfig()).rank(context, docs[::-1])


@pytest.mark.parametrize("algorithm", ["b3", "b4"])
def test_T18_exact_score_time_ties_and_all_zero_candidates_beyond_eight(algorithm):
    from evals.intelligence_v1.baselines import get_ranker
    from evals.intelligence_v1.contracts import BaselineConfig

    context, docs = step(name="D0")
    candidates = tuple(docs[0].model_copy(update={"document_id": f"tie:{i:02}",
        "doc_version_id": f"tie:{i:02}:1", "canonical_url": None, "title": "zzzz",
        "text_excerpt": None, "paragraphs": (), "content_sha256": None}) for i in range(12))
    context = context.model_copy(update={"candidate_doc_version_ids": tuple(
        d.doc_version_id for d in candidates)})
    ranker = get_ranker(algorithm, BaselineConfig())
    ranked = ranker.rank(context, candidates[::-1])
    assert len(ranked) == 12
    assert all(r.score_components.bm25_norm == 0 for r in ranked)
    assert len({r.score for r in ranked}) == 1
    assert [r.representative_doc_version_id for r in ranked] == [d.doc_version_id for d in candidates]
