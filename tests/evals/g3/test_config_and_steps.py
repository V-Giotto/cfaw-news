"""Formal replay must share the adapter's configuration and step identity gates."""

import copy

import pytest
from pydantic import ValidationError

from evals.intelligence_g2.contracts import data, digest, json_bytes
from evals.intelligence_g3.bridge import adapt
from evals.intelligence_g3.contracts import (
    G3Config,
    G3ReplayInput,
    InputManifest,
    NativeStep,
    parse,
)
from evals.intelligence_v1.exceptions import ContractError

from .support import Scenario


@pytest.fixture(scope="module")
def replay():
    return data(Scenario().load())


@pytest.mark.parametrize("unregistered", ["0" * 64, "f" * 64])
def test_formal_replay_rejects_unregistered_config_digest(replay, unregistered):
    raw = copy.deepcopy(replay)
    assert raw["parent"]["config_sha256"] == digest(G3Config())
    raw["parent"]["config_sha256"] = unregistered
    with pytest.raises((ValidationError, ContractError), match="G3_REFERENCE_MISMATCH"):
        G3ReplayInput.model_validate_json(json_bytes(raw))


def test_adapter_uses_same_registered_config_check():
    s = Scenario()
    value = s.load()
    binding = value.parent.model_copy(update={"config_sha256": "0" * 64})
    with pytest.raises(ContractError, match="G3_REFERENCE_MISMATCH") as caught:
        adapt(manifest=parse(InputManifest, s.manifest), binding=binding,
              steps=tuple(parse(NativeStep, step) for step in s.payloads["fixture"]["steps"]),
              personas=s.payloads["personas"], history=[], deliveries=[], diagnostic=value.diagnostic)
    assert caught.value.field == "binding.config_sha256"


def rebind_cursors(raw, step_ids, *, self_reference=False):
    """Keep times, ordinals, state parents and evidence bindings valid after renaming."""
    previous = None
    for observation, step_id in zip(raw["observations"], step_ids, strict=True):
        state, evidence = observation["identity_state"], observation["evidence"]
        cursor = state["cursor"]
        cursor["step_id"] = step_id
        cursor["previous_step_id"] = previous["identity_state"]["cursor"]["step_id"] if previous else None
        if self_reference and previous:
            cursor["previous_step_id"] = step_id
        state["previous_state_sha256"] = digest(previous["identity_state"]) if previous else None
        evidence["cursor"] = copy.deepcopy(cursor)
        evidence["next_state"]["cursor"] = copy.deepcopy(cursor)
        evidence["next_state"]["grouping_state_sha256"] = digest(state)
        evidence["next_state"]["previous_state_sha256"] = digest(previous["evidence"]["next_state"]) if previous else None
        previous = observation
    raw["identity_state"] = copy.deepcopy(previous["identity_state"])
    raw["evidence"] = copy.deepcopy(previous["evidence"])
    raw["step_id"] = previous["identity_state"]["cursor"]["step_id"]


@pytest.mark.parametrize("name", ["D0", "D8"])
def test_repeated_step_id_rejected_with_valid_ordinals_times_and_parent_hashes(replay, name):
    raw = copy.deepcopy(replay)
    assert len(raw["observations"]) == 2
    rebind_cursors(raw, [name, name])
    first, second = raw["observations"]
    a, b = first["identity_state"]["cursor"], second["identity_state"]["cursor"]
    assert (a["ordinal"], b["ordinal"]) == (0, 1)
    assert a["as_of"] < b["as_of"]
    assert b["previous_step_id"] == a["step_id"] == b["step_id"]
    assert second["identity_state"]["previous_state_sha256"] == digest(first["identity_state"])
    assert second["evidence"]["next_state"]["previous_state_sha256"] == digest(first["evidence"]["next_state"])
    assert second["evidence"]["next_state"]["grouping_state_sha256"] == digest(second["identity_state"])
    with pytest.raises((ValidationError, ContractError), match="G3_DUPLICATE_ID"):
        G3ReplayInput.model_validate_json(json_bytes(raw))


def test_observation_self_reference_has_explicit_failure(replay):
    raw = copy.deepcopy(replay)
    names = [o["identity_state"]["cursor"]["step_id"] for o in raw["observations"]]
    assert len(names) == len(set(names))
    rebind_cursors(raw, names, self_reference=True)
    with pytest.raises((ValidationError, ContractError), match="G3_REFERENCE_MISMATCH") as caught:
        G3ReplayInput.model_validate_json(json_bytes(raw))
    error = caught.value
    fields = ([error.field] if isinstance(error, ContractError) else
              [getattr(row.get("ctx", {}).get("error"), "field", None) for row in error.errors(include_input=False)])
    assert "observation.self_reference" in fields
