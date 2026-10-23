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


def test_unknown_material_change_is_not_a_negative_reference_or_denominator():
    from datetime import datetime, timezone
    from types import SimpleNamespace

    from evals.intelligence_v1.metrics import step_metrics

    now = datetime(2026, 1, 2, tzinfo=timezone.utc)
    context = SimpleNamespace(as_of=now, time_window_start=datetime(2026, 1, 1, tzinfo=timezone.utc),
                              time_window_end=now, source_coverage=())
    item = dict(representative_doc_version_id='v', doc_version_ids=['v'],
                score_components={'text_delta': 'new_text'})
    row = dict(ranked_items=[item], presentation={'presented_items': [item], 'budget_seconds': 420})
    labels = {'event': dict(tier='radar', graded_relevance=1, material_change='insufficient',
                            supporting_doc_version_ids=['v'])}
    metrics, diagnostics = step_metrics(row, context, {'v': 'event'}, labels, k=5,
        evidence_times={'v': now}, historical_mapping={'old': 'event'})
    assert metrics['RepeatedNoChangeRate']['value'] is None
    assert metrics['RepeatedNoChangeRate']['denominator'] == 0
    assert metrics['NewTextProxyAgainstReference.precision']['value'] is None
    assert diagnostics['reference_change_insufficient_event_ids'] == ['event']
