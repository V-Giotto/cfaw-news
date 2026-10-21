import pytest


def test_METRIC01_null_denominators_are_finite_standard_json():
    from evals.intelligence_v1.hashing import canonical_json
    from evals.intelligence_v1.metrics import ratio

    result = ratio(0, 0, "no_visible_gold_focus_events")
    assert result == {"numerator": 0, "denominator": 0, "value": None,
                      "undefined_reason": "no_visible_gold_focus_events"}
    assert "NaN" not in canonical_json(result)


def test_METRIC02_duplicates_and_wrong_merge_cannot_gain_multiple_events():
    from evals.intelligence_v1.metrics import ranking_metrics

    items = [{"representative_doc_version_id": f"a{i}", "doc_version_ids": [f"a{i}"]}
             for i in range(5)]
    mapping = {f"a{i}": "x" for i in range(5)}
    labels = {"x": {"tier": "focus", "graded_relevance": 3},
              "y": {"tier": "focus", "graded_relevance": 2}}
    mapping["other"] = "y"
    result = ranking_metrics(items, mapping, labels, k=5)
    assert result["ImportantEventRecall@5"]["numerator"] == 1
    assert result["ImportantEventRecall@5"]["denominator"] == 2
    wrong = [{"representative_doc_version_id": "a0", "doc_version_ids": ["a0", "other"]}]
    assert ranking_metrics(wrong, mapping, labels, k=5)["ImportantEventRecall@5"]["value"] == .5


def test_binary_metrics_zero_and_abstention_are_different():
    from evals.intelligence_v1.metrics import binary_metrics

    result = binary_metrics({"a"}, {"b"}, {"a", "b"})
    assert result["precision"]["value"] == 0 and result["recall"]["value"] == 0
    assert result["f1"]["value"] == 0
    assert binary_metrics(None, {"b"}, {"a", "b"})["recall"]["undefined_reason"] == "prediction_not_emitted"


def test_macro_micro_and_null_exclusion_are_explicit():
    from evals.intelligence_v1.metrics import aggregate_metrics, ratio

    result = aggregate_metrics([ratio(1, 1, "empty"), ratio(0, 9, "empty"), ratio(0, 0, "empty")])
    assert result["macro"] == .5 and result["micro"] == pytest.approx(.1)
    assert result["defined_count"] == 2 and result["undefined_count"] == 1
