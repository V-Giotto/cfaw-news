from itertools import combinations

import pytest

from evals.intelligence_g2.contracts import G2Error, data, digest, parse
from evals.intelligence_g2.pr2.contracts import PR2Config, check_schemas
from evals.intelligence_g2.pr2.features import canonical_url, extract_features
from evals.intelligence_g2.pr2.grouping import r0_partition
from evals.intelligence_g2.pr2.validate_output import validate_output
from evals.intelligence_v1.contracts import BaselineConfig
from evals.intelligence_v1.grouping import group_candidates

from .support import bridge_specs, duplicate_specs, evidence_steps, make_input, run, sequence


def test_T11_ten_duplicates_keep_every_source_and_one_view():
    value = make_input(duplicate_specs())
    inputs, results = run([value])
    result = results[0]
    assert len(result.events) == len(result.views) == 1
    assert len(result.events[0].member_doc_version_ids) == 10
    assert len(result.views[0].source_pointers) == 10
    assert len({p.source_id for p in result.views[0].source_pointers}) == 10
    assert {p.independence for p in result.views[0].source_pointers} == {"unknown"}
    assert len(result.relations) == 45
    assert {p.predicted_relation for p in result.relations} == {"exact_duplicate"}
    broken = result.model_copy(update={"partition": result.partition.model_copy(update={"clusters": ()})})
    with pytest.raises(G2Error) as error:
        validate_output(broken, inputs[0], PR2Config())
    assert (error.value.code, error.value.stage, error.value.field) == (
        "GROUP_MEMBERS_INVALID", "grouping", "member_doc_version_ids")


def test_T12_official_and_test_share_identity_without_claiming_independence():
    inputs, results = run(sequence(evidence_steps()))
    before, after = results
    assert len(after.events) == 1
    assert before.events[0].event_key == after.events[0].event_key
    assert before.events[0].event_revision != after.events[0].event_revision
    assert after.relations[0].predicted_relation == "same_event_different_evidence"
    assert {p.dependency for p in after.views[0].source_pointers} == {"unknown"}
    assert {p.independence for p in after.views[0].source_pointers} == {"unknown"}
    assert all(v.next_state.strategy == "r1" for v in results)
    assert inputs[-1].previous_state == before.next_state


def test_T12_no_testing_is_not_a_measurement_and_upstream_is_not_sufficient():
    a = {"id": "a", "title": "Atlas Tool release"}
    b = {"id": "b", "title": "Atlas Tool announcement republished", "upstream": "a",
         "body": "This republishes the announcement, with no independent testing."}
    result = run([make_input([a, b])])[1][0]
    assert result.relations[0].predicted_relation == "syndicated"
    assert result.features[1].material_role == "reprint"
    b = {**b, "title": "Atlas Tool discussion", "body": "A discussion without a declared target or copying cue."}
    result = run([make_input([a, b])])[1][0]
    assert result.relations[0].predicted_relation == "uncertain"
    b = {**b, "title": "Atlas Tool test", "body": "We tested a toy setup.", "upstream": "a"}
    result = run([make_input([a, b])])[1][0]
    assert result.relations[0].predicted_relation == "same_event_different_evidence"
    assert result.features[1].material_role == "measurement"


@pytest.mark.parametrize("title,reason,relation", [
    ("Boreal Tool v1.0 release", "different_subject", "unrelated"),
    ("Atlas Tool v2.0 release", "different_target_version", "related_distinct_event"),
    ("Atlas Tool license", "different_action", "related_distinct_event"),
    ("Atlas Tool documentation theme", "different_action", "related_distinct_event"),
])
def test_T13_conflicts_override_upstream_and_lexical_similarity(title, reason, relation):
    specs = [{"id": "a"}, {"id": "b", "title": title, "upstream": "a"}]
    inputs, results = run([make_input(specs)])
    result = results[0]
    assert len(result.events) == 2
    pair = result.relations[0]
    assert pair.predicted_relation == relation
    assert reason in pair.cannot_link
    if relation == "related_distinct_event":
        assert all(len(e.related_event_keys) == 1 for e in result.events)
    one = result.partition.clusters[0].model_copy(update={"member_doc_version_ids": ("a:1", "b:1")})
    broken = result.model_copy(update={"partition": result.partition.model_copy(update={"clusters": (one,)})})
    with pytest.raises(G2Error) as error:
        validate_output(broken, inputs[0], PR2Config())
    assert (error.value.code, error.value.stage, error.value.field, error.value.record_id) == (
        "G2_PR2_CANNOT_LINK_VIOLATION", "grouping", "member_doc_version_ids", "a:1")


def test_T13_different_features_and_multi_subject_abstain():
    specs = [{"id": "a", "title": "Atlas Tool adds search"},
             {"id": "b", "title": "Atlas Tool adds caching"},
             {"id": "c", "title": "Atlas Tool and Boreal Tool test"}]
    result = run([make_input(specs)], "r2")[1][0]
    assert len(result.events) == 3
    pair = result.relations[0]
    assert pair.predicted_relation == "related_distinct_event"
    assert "different_action_object" in pair.cannot_link
    assert all(p.predicted_relation == "uncertain" for p in result.relations if "c:1" in (
        p.left_doc_version_id, p.right_doc_version_id))


def test_T14_complete_linkage_blocks_a_positive_bridge_and_is_order_independent():
    value = make_input(bridge_specs())
    result = run([value], "r2")[1][0]
    by_pair = {(p.left_doc_version_id, p.right_doc_version_id): p for p in result.relations}
    assert by_pair[("a:1", "b:1")].predicted_relation == "same_event_different_evidence"
    assert by_pair[("b:1", "c:1")].predicted_relation == "same_event_different_evidence"
    assert by_pair[("a:1", "c:1")].predicted_relation == "uncertain"
    assert [g.member_doc_version_ids for g in result.partition.clusters] == [("a:1", "b:1"), ("c:1",)]
    assert result.partition.blocked_merges[0].blocking_pairs == (("a:1", "c:1"),)
    reverse = value.model_copy(update={"visible_documents": value.visible_documents[::-1]})
    assert run([reverse], "r2")[1][0] == result


def test_T14_R0_is_exactly_the_frozen_function_even_when_it_violates_new_constraints():
    value = make_input([{"id": "a"}, {"id": "b", "title": "Boreal Tool v2.0 release", "upstream": "a"}])
    candidates = tuple(d.candidate for d in value.visible_documents)
    expected = group_candidates(candidates, BaselineConfig())
    actual = r0_partition(candidates)
    assert [(g.member_doc_version_ids, g.r0_group_id) for g in actual.clusters] == [
        (g.doc_version_ids, g.predicted_event_id) for g in expected]
    result = run([value], "r0")[1][0]
    assert result.relations == () and len(result.events) == 1
    assert run([value], "r1")[1][0].events != result.events


def test_T12_cross_language_requires_shared_identifier():
    target = "synthetic://atlas/repo/releases/tag/v1.0"
    specs = [{"id": "a", "url": target}, {"id": "b", "title": "阿特拉斯工具实测",
             "body": "发布目标: " + target + "\n这是合成测试材料。"}]
    result = run([make_input(specs)])[1][0]
    assert len(result.events) == 1
    assert result.relations[0].predicted_relation == "same_event_different_evidence"
    specs[1]["body"] = "这是缺少发布标识的合成测试材料。"
    assert len(run([make_input(specs)])[1][0].events) == 2


def test_T18_contracts_feature_provenance_and_all_pair_coverage():
    assert check_schemas()
    assert PR2Config.model_config == {"extra": "forbid", "strict": True, "frozen": True}
    with pytest.raises(G2Error) as error:
        parse(PR2Config, {**data(PR2Config()), "oracle": True})
    assert error.value.code == "SCHEMA_INVALID" and error.value.field == "oracle"
    value = make_input(duplicate_specs()[:3])
    inputs, results = run([value])
    result = results[0]
    assert {(p.left_doc_version_id, p.right_doc_version_id) for p in result.relations} == set(
        combinations(sorted(value.context.candidate_doc_version_ids), 2))
    with pytest.raises(G2Error) as error:
        validate_output(result.model_copy(update={"relations": result.relations[:-1]}), inputs[0], PR2Config())
    assert (error.value.code, error.value.stage, error.value.field) == (
        "G2_PR2_PAIR_SET_INVALID", "relations", "relations")
    corrupted = result.features[0].model_copy(update={"target_version": "999"})
    with pytest.raises(G2Error) as error:
        validate_output(result.model_copy(update={"features": (corrupted,) + result.features[1:]}), inputs[0], PR2Config())
    assert error.value.code == "G2_PR2_FEATURE_PROVENANCE_INVALID"
    assert error.value.stage == "features" and error.value.field == "features"
    extracted = extract_features(replay_input=value, previous_state=None, config=PR2Config())
    assert all(ref.value_sha256 for f in extracted for ref in f.refs)
    assert digest(result.features[0]) == digest(extracted[0])


def test_T13_url_normalization_does_not_erase_semantic_components():
    assert canonical_url("https://EXAMPLE.invalid:443/a?utm_source=x&version=1#feature") == (
        "https://example.invalid/a?version=1#feature")
    assert canonical_url("https://example.invalid/a?version=2#feature") != canonical_url(
        "https://example.invalid/a?version=1#feature")


@pytest.mark.parametrize("day,expected", [(14, 1), (15, 2)])
def test_T14_R2_time_window_is_inclusive_and_not_enabled_by_default(day, expected):
    body = "Event date: 2026-01-01\n" + " ".join(f"token{i}" for i in range(20))
    a = {"id": "a", "title": "Atlas Tool release", "body": body}
    b = {"id": "b", "title": "Atlas Tool release", "body": body}
    values = sequence([(0, [a]), (day, [a, b])])
    assert len(run(values, "r1")[1][-1].events) == 2
    assert len(run(values, "r2")[1][-1].events) == expected


def test_T13_ABI_and_baseline_versions_are_not_product_identifiers():
    value = make_input([{"id": "a", "title": "Atlas Tool release",
                         "body": "Supports ABI 2 on GPU 9; Baseline Y version 8 is a comparison."}])
    feature = run([value])[1][0].features[0]
    assert feature.target_version is None


@pytest.mark.parametrize("strategy", ["r1", "r2"])
@pytest.mark.parametrize("title,body,version,ambiguous", [
    ("Atlas Tool release compared with Baseline v2.0",
     "Atlas Tool v1.0 is released; Baseline v2.0 is a comparison only.", "1.0", False),
    ("Atlas Tool release compared with Baseline v2.0",
     "Baseline v2.0 is a comparison only.", None, False),
    ("Atlas Tool v2.0 release",
     "Atlas Tool v1.0 is released; Baseline v2.0 is a comparison only.", None, True),
])
def test_review_comparison_versions_never_override_subject_bound_version(
        strategy, title, body, version, ambiguous):
    value = make_input([{"id": "a", "title": "Atlas Tool v2.0 release"},
                        {"id": "b", "title": title, "body": body}])
    result = run([value], strategy)[1][0]
    feature = next(f for f in result.features if f.document_id == "b")
    assert (feature.target_version, feature.ambiguous) == (version, ambiguous)
    assert len(result.events) == 2
    assert result.relations[0].predicted_relation in {"related_distinct_event", "uncertain"}
    assert result.validation.ok


@pytest.mark.parametrize("strategy", ["r1", "r2"])
def test_review_subject_bound_version_survives_repository_canonicalization(strategy):
    url = "synthetic://vendor/atlas/releases/tag/v1.0"
    value = make_input([{"id": "a", "url": url},
        {"id": "b", "title": "Atlas Tool release compared with Baseline v2.0",
         "body": "Target: " + url + "\nAtlas Tool v1.0 is released; Baseline v2.0 is comparison only."}])
    result = run([value], strategy)[1][0]
    assert {f.target_version for f in result.features} == {"1.0"}
    assert not any(f.ambiguous for f in result.features)
    assert len(result.events) == 1
    assert result.relations[0].predicted_relation == "same_event_different_evidence"


def test_T17_direct_relation_api_rejects_future_features():
    from datetime import timedelta

    from evals.intelligence_g2.pr2.relations import predict_relations

    value = make_input([{"id": "a"}])
    feature = run([value])[1][0].features[0]
    future = feature.model_copy(update={"available_at": value.context.as_of + timedelta(days=1)})
    with pytest.raises(G2Error) as error:
        predict_relations(features=(future,), as_of=value.context.as_of, strategy="r1", config=PR2Config())
    assert (error.value.code, error.value.stage, error.value.field, error.value.record_id) == (
        "G2_PR2_HISTORY_FUTURE", "relations", "features.available_at", "a:1")


def test_T13_same_repository_does_not_erase_different_product_subjects():
    shared = "synthetic://vendor/monorepo/releases/tag/v1.0"
    value = make_input([{"id": "a", "url": shared},
                        {"id": "b", "title": "Boreal Tool v1.0 release", "url": shared}])
    result = run([value])[1][0]
    assert len(result.events) == 2
    assert result.relations[0].predicted_relation == "unrelated"
    assert "different_subject" in result.relations[0].cannot_link


def test_T14_R2_near_copy_is_a_separate_experimental_rule():
    body = "Event date: 2026-01-01\nReprint: " + " ".join(f"word{i}" for i in range(20))
    specs = [{"id": name, "title": "Atlas Tool release reprint", "body": body} for name in ("a", "b")]
    assert run([make_input(specs)], "r1")[1][0].relations[0].predicted_relation == "uncertain"
    pair = run([make_input(specs)], "r2")[1][0].relations[0]
    assert (pair.predicted_relation, pair.rule_id) == ("syndicated", "near_copy")
