from evals.intelligence_g2.pr3.evaluate import compare, ratio
from evals.intelligence_g2.pr3.reference_loader import load_references

from .support import FIXTURE, pin, run, scenarios


def test_metrics_from_explicit_references_include_direction_scope_numeric_and_gap_denominators():
    path = FIXTURE / "reference/manifest_v2.json"
    refs, directions, quality, _ = load_references(path, pin=pin(path))
    outputs = tuple(row for c in scenarios() for row in run(c["case_id"])[1])
    report, errors = compare(outputs, references=refs, directions=directions, quality=quality, reference_sha256=pin(path))
    assert errors == []
    assert report["counts"]["scored_steps"] == 19
    assert report["counts"]["tp"] > 0
    assert report["counts"]["fp"] == report["counts"]["fn"] == 0
    assert report["scope_field_retention"]["value"] == 1
    assert report["numeric_fidelity"]["value"] == 1
    assert report["coverage_gap_recall"]["value"] == 1
    assert report["direction_confusion_matrix"]["supports->supports"] > 0
    assert report["direction_confusion_matrix"]["refutes->refutes"] > 0
    assert not report["independent_validation"]
    assert report["independent_semantic_support"]["value"] is None


def test_missing_predictions_are_counted_and_zero_denominators_remain_null():
    path = FIXTURE / "reference/manifest_v2.json"
    refs, directions, quality, _ = load_references(path, pin=pin(path))
    _, rows = run("T19")
    row = rows[0].model_copy(update={"claims": (), "citations": (), "assessments": (), "links": ()})
    report, errors = compare((row,), references=refs, directions=directions, quality=quality, reference_sha256=pin(path))
    assert report["counts"]["fn"] == 1
    assert any(e["kind"] == "FN" for e in errors)
    assert report["extraction_precision"]["value"] is None
    assert ratio(0, 0)["unavailable_reason"] == "zero_denominator"
