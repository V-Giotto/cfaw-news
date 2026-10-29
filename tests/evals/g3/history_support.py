"""Authored native G2 synthetic inputs only; prediction never imports this module."""

from functools import lru_cache
from uuid import uuid4

import pytest

from evals.intelligence_g2.contracts import data, read_json
from evals.intelligence_g3.contracts import PACKAGE, ROOT, G3ReplayInput, parse
from evals.intelligence_g3.history import append_event, disruptive
from evals.intelligence_g3.history_contracts import (
    HistoryEvent,
    HistoryInput,
    HistoryJournal,
    HistoryMapping,
)
from tests.evals.g2.pr2.support import merge_split_steps

from .ranking_support import delivered, native_replay


@pytest.fixture
def g3_tmp_path():
    """Independent allowed workspace for storage/export tests under any pytest entry."""
    path = ROOT / ".tmp/evals/g3/tests/storage" / uuid4().hex
    path.mkdir(parents=True, exist_ok=False)
    return path


@lru_cache
def revisit_case(days=1, mode="repeat"):
    specs = read_json((PACKAGE / "fixtures/pr3/v1/scenarios.json").read_bytes())
    start = specs["initial"]
    update = specs["updates"].get(mode, start)
    return native_replay([(0, start), (days, update)])


@lru_cache
def identity_case(stage="merge"):
    steps = merge_split_steps()
    return native_replay(steps[:2] if stage == "merge" else steps)


def event_for(replay, kind="opened", *, interaction_id="interaction:1", feedback=None,
              retracts_id=None, delivery_index=0, target_index=0, available_at=None):
    delivery = replay.deliveries[delivery_index]
    stamp = available_at or delivery.available_at
    return HistoryEvent(interaction_id=interaction_id, persona_id=delivery.persona_id,
        delivery_id=delivery.delivery.delivery_id, target=delivery.items[target_index], kind=kind,
        feedback=feedback, retracts_id=retracts_id, occurred_at=stamp, available_at=stamp,
        source={"included": "server", "rendered": "client"}.get(kind, "explicit_user"),
        source_id="synthetic:test", provenance_uri="synthetic:g3-pr3-test")


def with_history(replay, kinds=("opened",), *, mappings=()):
    replay = delivered(replay, ())
    journal = HistoryJournal()
    for i, kind in enumerate(kinds):
        journal = append_event(journal, event_for(replay, kind, interaction_id=f"interaction:{i}"))
    return HistoryInput(replay=replay, journal=journal, mappings=mappings)


def all_old_deliveries(replay):
    raw = data(replay)
    persona = replay.persona.persona.persona_id
    raw["deliveries"] = []
    for i, candidate in enumerate(replay.observations[0].candidates):
        target = next(r for r in replay.published_refs if r.snapshot_id == candidate.snapshot.snapshot_id)
        stamp = data(target)["as_of"]
        raw["deliveries"].append(dict(schema_revision="g3-pr1-1", persona_id=persona,
            delivery=dict(delivery_id=f"delivery:{i}", as_of=stamp, generated_at=stamp),
            available_at=stamp, items=[data(target)], record_origin="synthetic",
            provenance_uri="synthetic:g3-pr3-test"))
    return parse(G3ReplayInput, raw)


def mappings_for(replay, certainty="confirmed"):
    result = []
    archive = {c.snapshot.snapshot_id: c for o in replay.observations for c in o.candidates}
    for delivery in replay.deliveries:
        for old in delivery.items:
            for current in replay.candidates:
                transitions = disruptive(replay, archive[old.snapshot_id], current)
                if not transitions:
                    continue
                new = next(r for r in replay.published_refs if r.snapshot_id == current.snapshot.snapshot_id)
                result.append(HistoryMapping(mapping_id=f"mapping:{len(result)}", from_target=old,
                    to_target=new, transition_ids=tuple(t.transition_id for t in transitions),
                    certainty=certainty, available_at=replay.as_of, reason="authored structural migration",
                    provenance_uri="synthetic:g3-pr3-test"))
    return tuple(result)


def add_current_delivery(replay, candidate_index=0):
    raw = data(replay)
    candidate = replay.candidates[candidate_index]
    target = next(r for r in replay.published_refs if r.snapshot_id == candidate.snapshot.snapshot_id)
    stamp = data(target)["as_of"]
    raw["deliveries"].append(dict(schema_revision="g3-pr1-1",
        persona_id=replay.persona.persona.persona_id,
        delivery=dict(delivery_id="delivery:current", as_of=stamp, generated_at=stamp),
        available_at=stamp, items=[data(target)], record_origin="synthetic",
        provenance_uri="synthetic:g3-pr3-current-delivery-test"))
    return parse(G3ReplayInput, raw)
