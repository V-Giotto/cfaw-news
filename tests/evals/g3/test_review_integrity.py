import copy

import pytest
from pydantic import ValidationError

from evals.intelligence_g2.contracts import data, digest, json_bytes
from evals.intelligence_g3.bridge import adapt
from evals.intelligence_g3.contracts import (
    G3ReplayInput,
    InputManifest,
    NativeStep,
    ParentBinding,
    parse,
)
from evals.intelligence_g3.replay import export_input
from evals.intelligence_v1.exceptions import ContractError

from .support import Scenario


@pytest.fixture(scope="module")
def snapshot():
    return data(Scenario().load())


@pytest.mark.parametrize("field", ["candidates", "published_refs"])
def test_formal_replay_cannot_drop_current_pool_or_references(snapshot, field):
    raw = copy.deepcopy(snapshot)
    assert raw["candidates"] and raw["evidence"]["bundles"]
    raw[field] = []
    with pytest.raises((ValidationError, ContractError)):
        G3ReplayInput.model_validate_json(json_bytes(raw))


def test_parent_kind_cannot_be_relabelled_after_serialization(snapshot):
    raw = copy.deepcopy(snapshot)
    raw["parent"]["kind"] = "accepted_g2"
    with pytest.raises((ValidationError, ContractError)):
        G3ReplayInput.model_validate_json(json_bytes(raw))


@pytest.mark.parametrize("fault", ["old_revision", "document_archive", "item_snapshots"])
def test_old_or_incomplete_replay_requires_reexport(snapshot, fault):
    raw = copy.deepcopy(snapshot)
    if fault == "old_revision":
        raw["schema_revision"] = "g3-pr1-1"
    else:
        raw.pop(fault)
    with pytest.raises(ValidationError):
        G3ReplayInput.model_validate_json(json_bytes(raw))


@pytest.mark.parametrize("fault", [
    "bundles", "candidates_and_bundles", "current_ref", "ref_revision", "anchor_archive",
    "snapshot_archive", "snapshot_id", "unknown_parent", "self_parent", "future_parent",
    "duplicate_parent", "snapshot_order", "anchor", "related", "parent_manifest", "feature_ref_time",
])
def test_formal_replay_revalidates_cross_object_archives(snapshot, fault):
    raw = copy.deepcopy(snapshot)
    candidate = raw["candidates"][0]
    current = next(s for s in raw["item_snapshots"] if s["snapshot_id"] == candidate["snapshot"]["snapshot_id"])
    if fault in {"bundles", "candidates_and_bundles"}:
        raw["evidence"]["bundles"] = []
        if fault == "candidates_and_bundles":
            raw["candidates"] = []
    elif fault == "current_ref":
        raw["published_refs"] = [r for r in raw["published_refs"] if r["snapshot_id"] != current["snapshot_id"]]
    elif fault == "ref_revision":
        next(r for r in raw["published_refs"] if r["snapshot_id"] == current["snapshot_id"])["event_revision"] = "0" * 64
    elif fault == "anchor_archive":
        raw["document_archive"] = [d for d in raw["document_archive"]
                                   if d["doc_version_id"] != candidate["event"]["anchor_doc_version_id"]]
    elif fault == "snapshot_archive":
        raw["item_snapshots"] = []
    elif fault == "snapshot_id":
        old = current["snapshot_id"]
        current["snapshot_id"] = "g2:snapshot:" + "f" * 64
        candidate["snapshot"] = copy.deepcopy(current)
        next(r for r in raw["published_refs"] if r["snapshot_id"] == old)["snapshot_id"] = current["snapshot_id"]
    elif fault in {"unknown_parent", "self_parent", "future_parent", "duplicate_parent"}:
        if fault == "future_parent":
            raw["item_snapshots"][0]["previous_snapshot_ids"] = [current["snapshot_id"]]
        else:
            parent = ("missing:snapshot" if fault == "unknown_parent" else current["snapshot_id"]
                      if fault == "self_parent" else current["previous_snapshot_ids"][0])
            current["previous_snapshot_ids"] = [parent] * (2 if fault == "duplicate_parent" else 1)
            candidate["snapshot"] = copy.deepcopy(current)
    elif fault == "snapshot_order":
        raw["item_snapshots"].reverse()
    elif fault in {"anchor", "related"}:
        candidate["event"]["anchor_doc_version_id" if fault == "anchor" else "related_event_keys"] = (
            "missing:anchor" if fault == "anchor" else ["missing:event"])
    elif fault == "feature_ref_time":
        raw["identity_state"]["registry"][0]["last_features"][0]["refs"][0]["available_at"] = "2025-01-01T00:00:00Z"
        raw["evidence"]["next_state"]["grouping_state_sha256"] = digest(raw["identity_state"])
    else:
        raw["parent"]["g2_input_manifest_sha256"] = "0" * 64
    with pytest.raises((ValidationError, ContractError)):
        G3ReplayInput.model_validate_json(json_bytes(raw))


@pytest.mark.parametrize("history", ["merge_split", "version_update", "dormancy", "upstream"])
def test_native_legal_identity_histories_remain_valid(history):
    from evals.intelligence_g2.pr4.contracts import PR4Config
    from evals.intelligence_g2.pr4.replay import run_sequence
    from evals.intelligence_g3.integrity import (
        document_index,
        validate_identity,
        validate_snapshots,
    )
    from tests.evals.g2.pr2.support import evidence_steps, make_input, merge_split_steps, sequence
    from tests.evals.g2.pr3.support import evidence_for

    steps = (merge_split_steps() if history == "merge_split" else evidence_steps()
             if history == "version_update" else [(0, [{"id": "a"}]), (1, []), (2, [{"id": "a"}])])
    values = sequence(steps)
    if history == "dormancy":
        # Preserve immutable document availability across an absent observation.
        values = values[:2] + (make_input([{"id": "a"}], day=2, previous=values[0]),)
    elif history == "upstream":
        parent = {"id": "a"}
        child = {"id": "b", "title": "Atlas Tool reprint", "upstream": "a",
                 "body": "This reprint repeats the announcement."}
        values = sequence([(0, [parent]), (1, [parent, child])])
    inputs, evidence = evidence_for(values)
    _, rules = run_sequence(inputs, evidence, config=PR4Config())
    if history == "upstream":
        assert any(r.doc_version_id != f.doc_version_id
                   for e in inputs[-1].grouping_result.next_state.registry for f in e.last_features for r in f.refs)
    documents = {}
    for value, rule in zip(inputs, rules, strict=True):
        documents.update(document_index(value.grouping_input.replay_input.visible_documents))
        state = value.grouping_result.next_state
        validate_identity(state, value.grouping_result.events, documents)
        validate_snapshots(rule.next_state.snapshots, state)


@pytest.mark.parametrize("fault", ["anchor", "related", "created", "registry_anchor", "registry_created", "feature_document", "trigger_document"])
@pytest.mark.parametrize("mode", ["load", "export"])
def test_identity_references_cannot_be_sealed(fault, mode):
    s = Scenario()
    record = s.payloads["fixture"]["steps"][-1]["record"]
    event = record["grouping"]["events"][0]
    state = record["grouping"]["next_state"]
    registered = next(e for e in state["registry"] if e["event_key"] == event["event_key"])
    if fault == "anchor":
        event["anchor_doc_version_id"] = "missing:anchor"
    elif fault == "related":
        event["related_event_keys"] = ["missing:event"]
    elif fault == "created":
        event["created_at"] = "2025-01-01T00:00:00Z"
    elif fault == "registry_anchor":
        registered["anchor_doc_version_id"] = event["anchor_doc_version_id"] = "missing:anchor"
    elif fault == "registry_created":
        registered["created_at"] = event["created_at"] = "2025-01-01T00:00:00Z"
    elif fault == "feature_document":
        registered["last_features"][0]["doc_version_id"] = "missing:feature"
    else:
        state["transitions"][0]["trigger_doc_version_ids"] = ["missing:trigger"]
    record["evidence"]["next_state"]["grouping_state_sha256"] = digest(state)
    with pytest.raises(ContractError):
        if mode == "load":
            s.load()
        else:
            export_input(s.path, manifest_sha256=s.save(), out=s.root / "rejected")
    assert not (s.root / "rejected").exists()


def tamper_snapshot(s, fault, *, expression=False):
    steps = s.payloads["fixture"]["steps"]
    collection = "expression" if expression else "rule"
    target_step = steps[0] if fault == "future_predecessor" else steps[-1]
    original = target_step["record"][collection]["snapshots"][0]
    target_id = original["snapshot_id"]
    if fault == "id":
        change = dict(snapshot_id="g2:forged-snapshot:" + "f" * 64)
    elif fault == "self":
        change = dict(previous_snapshot_ids=[target_id])
    elif fault == "duplicate":
        previous = original["previous_snapshot_ids"][0]
        change = dict(previous_snapshot_ids=[previous, previous])
    elif fault == "future_predecessor":
        change = dict(previous_snapshot_ids=[steps[-1]["record"][collection]["snapshots"][0]["snapshot_id"]])
    else:
        change = dict(previous_snapshot_ids=["missing:snapshot"])
    prior = None
    for step in steps:
        stage = step["record"][collection]
        for row in stage["snapshots"] + stage["next_state"]["snapshots"]:
            if row["snapshot_id"] == target_id:
                row.update(copy.deepcopy(change))
        if not expression:
            for view in step["handoff"]:
                if view["snapshot"]["snapshot_id"] == target_id:
                    view["snapshot"].update(copy.deepcopy(change))
        stage["next_state"]["previous_state_sha256"] = digest(prior) if prior else None
        prior = stage["next_state"]


@pytest.mark.parametrize("fault", ["unknown", "self", "duplicate", "id", "future_predecessor"])
@pytest.mark.parametrize("expression", [False, True])
@pytest.mark.parametrize("mode", ["load", "export"])
def test_snapshot_graph_and_ids_cannot_be_sealed(fault, expression, mode):
    s = Scenario()
    tamper_snapshot(s, fault, expression=expression)
    with pytest.raises(ContractError):
        if mode == "load":
            s.load()
        else:
            export_input(s.path, manifest_sha256=s.save(), out=s.root / "rejected")
    assert not (s.root / "rejected").exists()


@pytest.mark.parametrize("fault", ["job_id", "config_file_sha256", "fixture", "kind"])
def test_pure_adapter_checks_manifest_binding_consistency(fault):
    s = Scenario()
    value = s.load()
    changes = {"job_id": "foreign", "config_file_sha256": "0" * 64,
               "fixture": None, "kind": "accepted_g2"}
    binding = value.parent.model_copy(update={fault: changes[fault]})
    with pytest.raises(ContractError):
        adapt(manifest=parse(InputManifest, s.manifest), binding=binding,
              steps=tuple(parse(NativeStep, v) for v in s.payloads["fixture"]["steps"]),
              personas=s.payloads["personas"], history=[], deliveries=[], diagnostic=value.diagnostic)


@pytest.mark.parametrize("kind,acceptance,campaign,fixture", [
    ("accepted_g2", None, None, "keep"),
    ("accepted_g2", "directory", "directory", "keep"),
    ("synthetic_contract_probe", "directory", None, "keep"),
    ("synthetic_contract_probe", None, None, None),
])
def test_parent_binding_variants_are_exclusive(snapshot, kind, acceptance, campaign, fixture):
    raw = copy.deepcopy(snapshot["parent"])
    directory = dict(path=".tmp/evals/g2/example", manifest_sha256="a" * 64)
    raw.update(kind=kind, acceptance=directory if acceptance else None,
               campaign=directory if campaign else None, fixture=raw["fixture"] if fixture else None)
    with pytest.raises((ValidationError, ContractError)):
        ParentBinding.model_validate_json(json_bytes(raw))
