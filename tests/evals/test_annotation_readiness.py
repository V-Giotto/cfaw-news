"""Arithmetic and form probes; none are human annotation evidence."""

import json

import pytest
from conftest import refresh

from evals.intelligence_v1.hashing import sha256_bytes


def label(event, members, score):
    return {"local_event_id": event, "document_version_ids": members,
            **dict.fromkeys(("relevance", "potential_value", "novelty_to_persona",
                             "evidence_quality", "graded_relevance"), score),
            "tier": "radar", "material_change": "new", "claim_reviews": [],
            "document_relations": []}


def record(step, event, members, score):
    return {"timeline_id": "DEV-01", "step_id": step,
            "initial_label": label(event, members, score)}


def test_split_merge_component_is_not_also_a_missing_event():
    from evals.intelligence_v1.agreement import align_components

    value = align_components([label("a", ["x", "y"], 2)],
                             [label("b1", ["x"], 1), label("b2", ["y"], 3)])
    assert len(value) == 1
    assert value[0]["status"] == "split_merge_disagreement"
    assert value[0]["a_indices"] == [0] and value[0]["b_indices"] == [0, 1]
    assert value[0]["a_documents"] == value[0]["b_documents"] == ["x", "y"]


def test_matching_uses_members_and_preserves_real_missing_groups():
    from evals.intelligence_v1.agreement import align_components

    result = align_components([label("arbitrary", ["x"], 1), label("a2", ["z"], 1)],
                              [label("different-id", ["x"], 1), label("b2", ["q"], 1)])
    assert sorted(x["status"] for x in result) == ["matched", "missing_in_a", "missing_in_b"]


def test_filtering_uses_the_same_samples_for_numerator_and_denominator():
    from evals.intelligence_v1.agreement import compare_development_records

    data = {"A": [record(s, "a", [s], 1) for s in ("D0", "D4", "D5")],
            "B": [record(s, "b", [s], 1) for s in ("D0", "D4", "D5")]}
    result = compare_development_records(data, families={"DEV-01": "f1"},
                                         excluded_steps={"D4", "D5"})
    stat = result["statistics"]["evidence_quality"]
    assert stat["count"] == stat["agreement_numerator"] == 1
    assert result["human_annotation_gate"] == "BLOCKED"
    assert result["scope"] == "human_ai_development_comparison_not_independent_human_agreement"
    assert result["semantic_support"]["value"] is None


@pytest.mark.parametrize("right", [[], [record("D0", "b", ["x"], 1)]])
def test_unannotated_documents_are_not_negative_event_pair_labels(right):
    from evals.intelligence_v1.agreement import compare_development_records

    data = {"A": [record("D0", "a1", ["x"], 1), record("D0", "a2", ["y"], 1)],
            "B": right}
    result = compare_development_records(data, families={"DEV-01": "f1"})
    assert result["event_pair_counts"]["comparable_pairs"] == 0
    assert result["event_pairs"]["raw_agreement"]["value"] is None


def test_family_interval_is_missing_for_one_family_and_for_no_samples():
    from evals.intelligence_v1.agreement import family_confidence_interval

    one = family_confidence_interval([("f1", 0, 0), ("f1", 1, 1)], [0, 1], weighted=True)
    assert one["interval"] is None and one["undefined_reason"] == "fewer_than_two_families"
    empty = family_confidence_interval([], [0, 1], weighted=True)
    assert empty["interval"] is None and empty["undefined_reason"] == "no_paired_samples"


def test_family_bootstrap_is_seeded_order_invariant_and_discloses_small_sample():
    from evals.intelligence_v1.agreement import family_confidence_interval

    pairs = [(f"f{i}", a, b) for i in range(5) for a, b in ((0, 0), (1, i % 2))]
    result = family_confidence_interval(pairs, [0, 1], resamples=80)
    assert result == family_confidence_interval(list(reversed(pairs)), [0, 1], resamples=80)
    assert result["family_count"] == 5 and result["resampling_unit"] == "family"
    assert result["interval"] is not None
    assert result["warning"] == "few_families_unstable_not_generalization_evidence"


def test_one_sided_constant_does_not_make_kappa_undefined():
    from evals.intelligence_v1.annotations import agreement_statistic

    value = agreement_statistic([1, 1], [0, 2], [0, 1, 2, 3], weighted=True)
    assert value["kappa"] == 0 and value["undefined_reason"] is None
    assert value["distribution_left"] == [0, 2, 0, 0]
    assert value["distribution_right"] == [1, 0, 1, 0]


def test_all_degenerate_family_resamples_have_no_interval():
    from evals.intelligence_v1.agreement import family_confidence_interval

    value = family_confidence_interval([("a", 1, 1), ("b", 1, 1)], [0, 1], resamples=20)
    assert value["interval"] is None and value["valid_resamples"] == 0
    assert value["undefined_resamples"] == 20
    assert value["undefined_reason"] == "all_bootstrap_kappas_undefined"


def test_packet_exports_current_guide_schema_and_array_templates(bundle, tmp_path):
    from evals.intelligence_v1.annotations import export_packet
    from evals.intelligence_v1.build_pr5 import GUIDE_FILE
    from evals.intelligence_v1.contracts import HumanAnnotation

    manifest = refresh(bundle)
    target = tmp_path / "packet"
    export_packet(manifest, manifest_sha256=sha256_bytes(manifest.read_bytes()),
                  timeline_id="DEV-01", step_id="D0", out=target)
    blank = json.loads((target / "blank_form.json").read_bytes())
    assert blank["template_only"] is True
    assert blank["initial_label"]["claim_reviews"] == []
    fields = json.loads((target / "field_templates.json").read_bytes())
    assert fields["claim_review"]["limitations"] == []
    assert fields["evidence_ref"]["direction"] is None
    assert set(fields["document_relation"]) == {
        "left_doc_version_id", "right_doc_version_id", "relation", "rationale",
        "evidence_at", "record_origin", "provenance_uri"}
    schema = json.loads((target / "submission.schema.json").read_bytes())
    assert schema.pop("$schema") == "https://json-schema.org/draft/2020-12/schema"
    assert schema == HumanAnnotation.model_json_schema()
    assert (target / GUIDE_FILE).read_bytes() == (bundle / GUIDE_FILE).read_bytes()
    with pytest.raises(ValueError):
        HumanAnnotation.model_validate_json(json.dumps(blank))
