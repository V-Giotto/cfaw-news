from datetime import timedelta

import pytest

from evals.intelligence_g2.contracts import G2Error, data, digest
from evals.intelligence_g2.pr2.contracts import AliasRecord, PR2Config
from evals.intelligence_g2.pr2.identity import (
    resolve_identity,
    resolve_published_reference,
    validate_graph,
)
from evals.intelligence_g2.pr2.pipeline import run_grouping_step
from evals.intelligence_g2.pr2.validate_output import checked_grouping_input

from .support import evidence_steps, make_input, merge_split_steps, run, sequence


@pytest.mark.parametrize("strategy", ["r0", "r1", "r2"])
def test_review_ambiguous_immutable_version_continues_without_new_identity(strategy):
    specs = [{"id": "a", "title": "Atlas Tool and Boreal Tool test"}]
    _, results = run(sequence([(0, specs), (1, specs)]), strategy)
    before, after = results
    assert before.features[0].ambiguous and after.features[0].ambiguous
    assert before.events[0].event_key == after.events[0].event_key
    assert before.events[0].event_revision == after.events[0].event_revision
    assert after.transitions == ()
    assert len(after.next_state.registry) == 1
    assert after.next_state.transitions == before.next_state.transitions
    assert after.validation.ok


@pytest.mark.parametrize("strategy", ["r1", "r2"])
def test_review_ambiguity_still_blocks_changed_version_and_cross_document_matching(strategy):
    title = "Atlas Tool and Boreal Tool test"
    values = sequence([(0, [{"id": "a", "title": title}]),
        (1, [{"id": "a", "title": title, "version": 2, "body": "Changed ambiguous material."},
             {"id": "b", "title": title, "body": "Another ambiguous material."}])])
    _, results = run(values, strategy)
    assert len(results[1].events) == 2
    assert results[0].events[0].event_key not in {e.event_key for e in results[1].events}
    assert results[1].relations[0].predicted_relation == "uncertain"
    assert {t.kind for t in results[1].transitions} == {"birth"}


def test_T15_new_evidence_and_document_revision_keep_key_without_false_revision():
    specs = [{"id": "a"}]
    v0 = make_input(specs)
    v1 = make_input(specs, day=1, previous=v0)
    v8 = make_input([{**specs[0], "version": 2, "body": "CORRECTION: scope is limited to a toy setup."}],
                    day=8, previous=v1)
    _, results = run([v0, v1, v8])
    a, b, c = [r.events[0] for r in results]
    assert a.event_key == b.event_key == c.event_key
    assert a.anchor_doc_version_id == c.anchor_doc_version_id == "a:1"
    assert a.event_revision == b.event_revision != c.event_revision
    assert resolve_published_reference(event_key=a.event_key, event_revision=a.event_revision, snapshot=a) is a
    with pytest.raises(G2Error) as error:
        resolve_published_reference(event_key=a.event_key, event_revision=c.event_revision, snapshot=a)
    assert error.value.code == "G2_PR2_REVISION_MISMATCH"


def test_T15_unrelated_candidates_persona_and_whole_bundle_pin_do_not_rekey():
    value = make_input([{"id": "a"}])
    original = run([value])[1][0].events[0]
    larger = make_input([{"id": "a"}, {"id": "z", "title": "Boreal Tool v9 release"}])
    new = next(e for e in run([larger])[1][0].events if "a:1" in e.member_doc_version_ids)
    assert (original.event_key, original.event_revision) == (new.event_key, new.event_revision)
    modified = value.model_copy(update={"input_manifest_sha256": "f" * 64,
        "context": value.context.model_copy(update={"persona": value.context.persona.model_copy(
            update={"current_goals": ("a different synthetic goal",)})})})
    newer = run([modified])[1][0].events[0]
    assert (original.event_key, original.event_revision) == (newer.event_key, newer.event_revision)


def test_T15_mutable_document_can_become_a_different_release():
    values = sequence([(0, [{"id": "a"}]),
        (8, [{"id": "a", "version": 2, "title": "Atlas Tool v2.0 release"}])])
    _, results = run(values)
    assert results[0].events[0].event_key != results[1].events[0].event_key
    assert len(results[1].next_state.registry) == 2
    assert {r.status for r in results[1].next_state.registry} == {"dormant", "active"}


def test_T16_merge_split_retire_parent_and_alias_without_rewriting_history():
    values = sequence(merge_split_steps())
    _, results = run(values)
    before, merged, split = results
    assert [len(r.events) for r in results] == [2, 1, 2]
    survivor = min(before.events, key=lambda e: (e.created_at, e.event_key)).event_key
    assert merged.events[0].event_key == survivor
    assert merged.transitions[0].kind == "merge"
    original_alias = merged.next_state.aliases[0]
    original_sha = digest(original_alias)
    before_sha, merged_sha = digest(before), digest(merged)
    assert split.transitions[0].kind == "split"
    children = tuple(sorted(e.event_key for e in split.events))
    assert survivor not in children
    assert not set(children) & {e.event_key for e in before.events}
    assert digest(split.next_state.aliases[0]) == original_sha
    assert split.next_state.aliases[-1].kind == "retired"
    assert split.next_state.transitions[:len(merged.next_state.transitions)] == merged.next_state.transitions
    assert resolve_identity(split.next_state, original_alias.alias_key, as_of=before.cursor.as_of) == {
        "status": "active", "target_keys": (original_alias.alias_key,)}
    assert resolve_identity(split.next_state, original_alias.alias_key, as_of=merged.cursor.as_of) == {
        "status": "alias", "target_keys": (survivor,)}
    assert resolve_identity(split.next_state, original_alias.alias_key, as_of=split.cursor.as_of) == {
        "status": "retired_split", "target_keys": children}
    assert resolve_identity(split.next_state, survivor, as_of=split.cursor.as_of)["target_keys"] == children
    assert (digest(before), digest(merged)) == (before_sha, merged_sha)
    assert run(values)[1] == results


def test_T16_invalid_alias_graph_is_rejected_with_exact_fields():
    _, results = run(sequence(merge_split_steps()[:1]))
    state = results[0].next_state
    a, b = [e.event_key for e in state.registry]
    tid = state.transitions[0].transition_id
    for targets in ((a,), ("missing",)):
        bad = state.model_copy(update={"aliases": (AliasRecord(alias_key=a, target_keys=targets,
            kind="created", effective_at=state.cursor.as_of, transition_id=tid),)})
        with pytest.raises(G2Error) as error:
            validate_graph(bad)
        assert (error.value.code, error.value.stage, error.value.field, error.value.record_id) == (
            "G2_PR2_IDENTITY_GRAPH_INVALID", "identity", "aliases", a)
    aliases = tuple(AliasRecord(alias_key=x, target_keys=(y,), kind="created",
        effective_at=state.cursor.as_of, transition_id=tid) for x, y in ((a, b), (b, a)))
    with pytest.raises(G2Error) as error:
        validate_graph(state.model_copy(update={"aliases": aliases}))
    assert error.value.code == "G2_PR2_IDENTITY_GRAPH_INVALID"


def test_T17_future_state_and_wrong_cursor_are_rejected_before_payload_access():
    inputs, results = run(sequence(evidence_steps()))
    value = inputs[-1]
    prior = value.previous_state
    future = prior.registry[0].last_features[0].model_copy(update={
        "available_at": value.cursor.as_of + timedelta(days=1)})
    event = prior.registry[0].model_copy(update={"last_features": (future,)})
    bad = value.model_copy(update={"previous_state": prior.model_copy(update={"registry": (event,)})})
    with pytest.raises(G2Error) as error:
        run_grouping_step(grouping_input=bad, config=PR2Config())
    assert (error.value.code, error.value.stage, error.value.field) == (
        "G2_PR2_HISTORY_FUTURE", "identity", "last_features.available_at")
    for cursor in (value.cursor.model_copy(update={"ordinal": 0}),
                   value.cursor.model_copy(update={"previous_step_id": "wrong"})):
        with pytest.raises(G2Error) as error:
            checked_grouping_input(value.model_copy(update={"cursor": cursor}), PR2Config())
        assert (error.value.code, error.value.stage, error.value.field) == (
            "G2_PR2_STATE_CHAIN_INVALID", "identity", "previous_state")
    with pytest.raises(G2Error) as error:
        checked_grouping_input(value.model_copy(update={"previous_state_sha256": "0" * 64}), PR2Config())
    assert error.value.code == "G2_PR2_STATE_CHAIN_INVALID"
    assert data(results[0].next_state) == data(prior)


def test_T17_future_candidate_body_guard_and_pure_step(monkeypatch):
    from pathlib import Path

    inputs, _ = run([make_input([{"id": "a"}])])
    value = inputs[0]
    doc = value.replay_input.visible_documents[0]

    class Future:
        doc_version_id = "future:1"
        available_at = value.cursor.as_of + timedelta(days=1)

        def __getattr__(self, name):
            if name in {"title", "paragraphs", "model_dump"}:
                pytest.fail("future body accessed")
            raise AttributeError(name)

    replay = value.replay_input.model_copy(update={"visible_documents": (
        doc.model_copy(update={"candidate": Future()}),)})
    with pytest.raises(G2Error) as error:
        run_grouping_step(grouping_input=value.model_copy(update={"replay_input": replay}), config=PR2Config())
    assert error.value.code == "FUTURE_VERSION"
    original = digest(value)

    def deny(*args, **kwargs):
        pytest.fail("pure step attempted IO")

    with monkeypatch.context() as scoped:
        for method in ("open", "stat", "lstat"):
            scoped.setattr(Path, method, deny)
        assert run_grouping_step(grouping_input=value, config=PR2Config()).events
    assert digest(value) == original


def test_T15_dormant_identity_reactivates_instead_of_rebirth():
    a = make_input([{"id": "a"}])
    empty = make_input([], day=1, previous=a)
    again = make_input([{"id": "a", "version": 2}], day=8, previous=empty)
    _, results = run([a, empty, again])
    assert results[0].events[0].event_key == results[2].events[0].event_key
    assert results[1].events == results[1].views == ()
    assert results[2].transitions[0].kind == "reactivate"


def test_T18_all_35_frozen_steps_and_R0_current_candidate_equality():
    from evals.intelligence_g2.contracts import G1_PIN, ROOT
    from evals.intelligence_g2.pr2.replay import load_sequence

    timelines = [(f"DEV-{n:02}", "D8") for n in range(1, 6)] + [("REVISIT-7D", "D8"), ("SYN-PR1", "D6")]
    total = 0
    for timeline, last in timelines:
        values, _ = load_sequence(ROOT / "evals/intelligence_v1/manifests/dataset_manifest.json",
                                 pin=G1_PIN, timeline_id=timeline, through_step=last)
        total += len(values)
        outputs = [run(values, s) for s in ("r0", "r1", "r2")]
        assert all(len(results) == len(values) for _, results in outputs)
        for index in range(len(values)):
            candidate_ids = set(values[index].context.candidate_doc_version_ids)
            for _, results in outputs:
                members = [m for e in results[index].events for m in e.member_doc_version_ids]
                assert len(members) == len(set(members)) and set(members) == candidate_ids
    assert total == 35


def test_T16_many_to_many_is_an_explicit_complex_transition():
    initial = [{"id": name, "title": "Atlas Tool v" + version + " release"}
               for name, version in (("a", "1.0"), ("b", "1.0"), ("c", "2.0"), ("d", "2.0"))]
    corrected = [{"id": name, "version": 2, "title": "Atlas Tool v" + version + " release"}
                 for name, version in (("a", "3.0"), ("b", "4.0"), ("c", "3.0"), ("d", "4.0"))]
    _, results = run(sequence([(0, initial), (8, corrected)]))
    before, after = results
    assert len(before.events) == len(after.events) == 2
    assert after.transitions[0].kind == "complex"
    assert set(after.transitions[0].from_keys) == {e.event_key for e in before.events}
    assert set(after.transitions[0].to_keys) == {e.event_key for e in after.events}
    assert not set(after.transitions[0].from_keys) & set(after.transitions[0].to_keys)


def test_T16_PR1_item_and_bundle_bytes_survive_PR2_corrections(tmp_path):
    from evals.intelligence_g2.contracts import G2Config, json_bytes
    from evals.intelligence_g2.pipeline import run_g2_offline

    values = sequence(merge_split_steps())
    legacy = run_g2_offline(replay_input=values[0], config=G2Config())
    paths = [tmp_path / "published-items.jsonl", tmp_path / "published-bundles.jsonl"]
    for path, records in zip(paths, (legacy.items, legacy.bundles), strict=True):
        path.write_bytes(b"".join(json_bytes(r) for r in records))
    original = {p.name: p.read_bytes() for p in paths}
    _, results = run(values)
    old_keys = {i.event_key for i in legacy.items}
    assert {link.pr1_event_key for view in results[-1].views for link in view.compatibility_links} == old_keys
    assert all(link.as_of == results[-1].cursor.as_of for view in results[-1].views
               for link in view.compatibility_links)
    assert original == {p.name: p.read_bytes() for p in paths}


def test_T15_existing_lineage_wins_over_related_unmerged_candidate_in_R0():
    _, results = run(sequence(evidence_steps()), "r0")
    before, after = results
    old_key = before.events[0].event_key
    official = next(e for e in after.events if "official:1" in e.member_doc_version_ids)
    test = next(e for e in after.events if "test:1" in e.member_doc_version_ids)
    assert official.event_key == old_key
    assert test.event_key != old_key
    assert not any(t.kind in {"split", "complex"} for t in after.transitions)
