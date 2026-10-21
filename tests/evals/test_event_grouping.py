import pytest
from test_loader import step


def groups(candidates):
    from evals.intelligence_v1.contracts import BaselineConfig
    from evals.intelligence_v1.grouping import group_candidates

    return group_candidates(candidates, BaselineConfig())


def test_T06_T07_T15_visible_upstream_and_distinct_project_announcement():
    from evals.intelligence_v1.baselines import get_ranker
    from evals.intelligence_v1.contracts import BaselineConfig

    context, candidates = step(name="D8")
    result = groups(candidates)
    assert {frozenset(g.doc_version_ids) for g in result} == {
        frozenset(["d01:a:2", "d01:b:1", "d01:c:1", "d01:d:1"]),
        frozenset(["d01:e:1"]), frozenset(["d01:f:1"])}
    upstream = next(g for g in result if len(g.doc_version_ids) > 1)
    assert upstream.evidence_independence == "not_independent"
    assert "visible_upstream" in upstream.merge_reasons
    ranked = get_ranker("b2-predicted", BaselineConfig()).rank(context, candidates)
    assert len(ranked) == len({r.predicted_event_id for r in ranked}) == 3
    assert groups(candidates[::-1]) == result


def test_exact_duplicate_requires_both_non_null_url_and_hash():
    _, docs = step(name="D0")
    a = docs[0]
    b = a.model_copy(update={"doc_version_id": "b:1", "document_id": "b"})
    assert len(groups((a, b))) == 1
    # Tiny bodies cannot accidentally satisfy the conservative text fallback.
    a = a.model_copy(update={"paragraphs": (), "text_excerpt": None})
    b = b.model_copy(update={"paragraphs": (), "text_excerpt": None})
    for changes in ({"canonical_url": None}, {"content_sha256": None}):
        assert len(groups((a.model_copy(update=changes), b.model_copy(update=changes)))) == 2


@pytest.mark.parametrize("shared,extra,merge", [(19, 1, True), (18, 2, False)])
def test_similarity_threshold_is_inclusive(shared, extra, merge):
    from evals.intelligence_v1.contracts import Paragraph

    _, docs = step(name="D0")
    common = [f"word{i}" for i in range(shared)]
    a = docs[0].model_copy(update={"canonical_url": None,
        "title": "same exact announcement", "content_sha256": None,
        "paragraphs": (Paragraph(paragraph_id="p1", text=" ".join(common)),)})
    b = a.model_copy(update={"doc_version_id": "b:1", "document_id": "b",
        "paragraphs": (Paragraph(paragraph_id="p1", text=" ".join(
            common + [f"extra{i}" for i in range(extra)])),)})
    assert len(groups((a, b))) == (1 if merge else 2)


def test_similarity_does_not_transitively_bridge_incompatible_endpoints():
    from evals.intelligence_v1.contracts import Paragraph

    _, docs = step(name="D0")
    base = [f"word{i}" for i in range(20)]
    candidates = []
    for name, words in (("a", base), ("b", base + ["bridge"]),
                        ("c", base[1:] + ["bridge"])):
        candidates.append(docs[0].model_copy(update={"document_id": name,
            "doc_version_id": name + ":1", "canonical_url": None, "content_sha256": None,
            "title": "same exact announcement",
            "paragraphs": (Paragraph(paragraph_id="p1", text=" ".join(words)),)}))
    assert len(groups(tuple(candidates))) == 2
    assert groups(tuple(reversed(candidates))) == groups(tuple(candidates))
