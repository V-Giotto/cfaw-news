import math

import pytest
from test_replay_end_to_end import run

from evals.intelligence_v1.hashing import sha256_bytes


def test_metrics_duplicate_positions_zero_gain_and_representative_only():
    from evals.intelligence_v1.evaluate import ranking_metrics

    # The third card is an erroneous merge: only its displayed representative gets credit.
    mapping = {"a": "x", "b": "x", "c": "y", "d": "z"}
    labels = {"x": {"tier": "focus", "graded_relevance": 3},
              "y": {"tier": "focus", "graded_relevance": 2},
              "z": {"tier": "focus", "graded_relevance": 1}}
    items = [{"representative_doc_version_id": "a", "doc_version_ids": ["a"]},
             {"representative_doc_version_id": "b", "doc_version_ids": ["b"]},
             {"representative_doc_version_id": "c", "doc_version_ids": ["c", "d"]}]
    result = ranking_metrics(items, mapping, labels, k=5)
    assert result["ImportantEventRecall@5"]["numerator"] == 2
    assert result["ImportantEventRecall@5"]["denominator"] == 3
    assert result["ImportantEventRecall@5"]["value"] == pytest.approx(2/3)
    expected = (7 + 3/math.log2(4)) / (7 + 3/math.log2(3) + 1/math.log2(4))
    assert result["EventnDCG@5"]["value"] == pytest.approx(expected)
    empty = ranking_metrics([], {}, {}, k=5)
    assert empty["ImportantEventRecall@5"]["value"] is None
    assert empty["EventnDCG@5"]["value"] is None


def test_DEV01_missing_gold_is_null_and_group_errors_remain_diagnostic(bundle, tmp_path):
    from evals.intelligence_v1.evaluate import evaluate_run

    out = tmp_path / "b2-predicted"
    run(bundle, out, "b2-predicted")
    manifest = bundle / "manifests/dataset_manifest.json"
    report = evaluate_run(out, manifest, manifest_sha256=sha256_bytes(manifest.read_bytes()),
                          out=tmp_path/"evaluation")
    dev = [s for s in report["steps"] if s["timeline_id"] == "DEV-01"]
    assert len(dev) == 6
    assert all(s["metrics"]["ImportantEventRecall@5"]["value"] is None for s in dev)
    assert all(s["metrics"]["EventnDCG@5"]["undefined_reason"] == "gold_not_available"
               for s in dev)
    assert next(s for s in dev if s["step_id"] == "D8")["group_errors"]["false_negative_pairs"]
    assert report["human_annotation"] == "not_confirmed"


def test_tampered_gold_blocks_evaluation_and_never_rewrites_predictions(bundle, tmp_path):
    from evals.intelligence_v1.evaluate import evaluate_run
    from evals.intelligence_v1.exceptions import DatasetValidationError

    out = tmp_path / "b0"
    run(bundle, out, "b0")
    raw = (out/"predictions.jsonl").read_bytes()
    manifest = bundle / "manifests/dataset_manifest.json"
    pin = sha256_bytes(manifest.read_bytes())
    (bundle/"labels/gold.jsonl").write_bytes(b" ")
    target = tmp_path / "must-not-exist"
    with pytest.raises(DatasetValidationError):
        evaluate_run(out, manifest, manifest_sha256=pin, out=target)
    assert not target.exists() and (out/"predictions.jsonl").read_bytes() == raw
