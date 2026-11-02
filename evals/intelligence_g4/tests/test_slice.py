"""Native G2 execution, honest G3 boundary and isolated frozen G3 reuse."""

from copy import deepcopy

import pytest

from evals.intelligence_g2.contracts import data, json_bytes
from evals.intelligence_g3.budget import plan_briefing
from evals.intelligence_g3.contracts import ROOT
from evals.intelligence_g3.history_contracts import HistoryInput, HistoryJournal
from evals.intelligence_g3.replay import load_input
from evals.intelligence_g3.revisit import rank_revisit
from evals.intelligence_g4.contracts import G4Error, RuntimeBriefing, parse
from evals.intelligence_g4.slice import run_slice
from evals.intelligence_v1.hashing import sha256_bytes

from .support import case, repeat, wire


def test_compliant_synthetic_native_pipeline_stops_at_unregistered_g3_boundary():
    raw, pin = wire(case())
    result = run_slice(raw, expected_sha256=pin)
    native = result.native_steps[-1]
    assert native.grouping.validation.ok and native.evidence.validation.ok and native.rule.validation.ok
    assert native.evidence.citations and native.rule.items[0].tier_candidate != "hold"
    assert native.presentations[0].selection == "rule"
    assert native.presentations[0].base_item == native.rule.items[0]
    assert result.status.code == "G4_G3_RUNTIME_ADAPTER_REQUIRED"
    assert result.status.record_origin == "synthetic" and result.status.publishable is False
    assert result.plan is None and result.display_order == ()
    assert result.archive_snapshot_ids == tuple(s.snapshot_id for s in native.rule.snapshots)
    assert raw == json_bytes(result.input)


@pytest.mark.parametrize("origin", ["real", "synthetic"])
def test_metadata_only_and_hold_remain_archivable_without_fake_briefing(origin):
    raw, pin = wire(case(body="", origin=origin))
    result = run_slice(raw, expected_sha256=pin)
    assert result.status.state == "insufficient_evidence"
    assert result.status.code == "G4_EVIDENCE_NOT_ELIGIBLE"
    assert result.native_steps[-1].rule.items[0].tier_candidate == "hold"
    assert result.archive_snapshot_ids and not result.display_order
    assert not result.native_steps[-1].evidence.citations


def test_empty_pool_keeps_source_coverage_unknown():
    value = case()
    value["steps"][0]["documents"] = []
    raw, pin = wire(value)
    result = run_slice(raw, expected_sha256=pin)
    assert result.archive_snapshot_ids == ()
    assert result.input.steps[0].source_coverage[0].status == "unknown"
    assert result.native_steps[0].evidence.validation.coverage_gaps


def test_native_prefix_replay_and_serialized_outputs_are_deterministic():
    raw, pin = wire(repeat(case()))
    before = bytes(raw)
    first = run_slice(raw, expected_sha256=pin)
    second = run_slice(raw, expected_sha256=pin)
    assert json_bytes(first) == json_bytes(second) and raw == before
    assert parse(RuntimeBriefing, data(first)) == first
    assert first.native_steps[0].grouping.events[0].event_key == first.native_steps[1].grouping.events[0].event_key
    assert first.native_steps[1].rule.snapshots[0].previous_snapshot_ids


@pytest.mark.parametrize("fault", ["wrong", "missing", "changed", "noncanonical", "oversize"])
def test_supplied_pin_and_byte_limits_fail_closed(fault):
    raw, pin = wire(case())
    expected = "G4_INPUT_PIN_MISMATCH"
    if fault == "wrong":
        pin = "0" * 64
    elif fault == "missing":
        pin = None
    elif fault == "changed":
        raw += b" "
    elif fault == "noncanonical":
        raw += b" "
        pin = sha256_bytes(raw)
        expected = "G4_CANONICAL_REQUIRED"
    else:
        raw = b"x" * 2_000_001
        expected = "G4_RESOURCE_LIMIT"
    with pytest.raises(G4Error, match=expected):
        run_slice(raw, expected_sha256=pin)


@pytest.mark.parametrize("fault", ["archive", "claim", "publish", "display", "hash"])
def test_serialized_output_cannot_forge_facts_or_publishability(fault):
    raw, pin = wire(case())
    value = data(run_slice(raw, expected_sha256=pin))
    if fault == "archive":
        value["archive_snapshot_ids"] = []
    elif fault == "claim":
        value["native_steps"][0]["evidence"]["claims"][0]["statement"] = "fabricated"
    elif fault == "publish":
        value["status"]["publishable"] = True
    elif fault == "display":
        value["display_order"] = ["invented"]
    else:
        value["input_sha256"] = "0" * 64
    with pytest.raises(G4Error):
        parse(RuntimeBriefing, value)


def test_pipeline_does_not_invoke_network_model_database_or_g3_runtime(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("unauthorized effect")

    import socket

    import httpx
    from cfaw_news.database import Database
    from cfaw_news.providers import CompatibleProvider

    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(httpx, "AsyncClient", forbidden)
    monkeypatch.setattr(Database, "__init__", forbidden)
    monkeypatch.setattr(CompatibleProvider, "__init__", forbidden)
    monkeypatch.setattr("evals.intelligence_g3.revisit.rank_revisit", forbidden)
    raw, pin = wire(case())
    assert run_slice(raw, expected_sha256=pin).plan is None


def test_frozen_g3_probe_can_rank_and_plan_but_is_never_runtime_acceptance():
    # External, previously documented probe pin; no manufactured parent or copied fixture identity.
    replay = load_input(ROOT / "evals/intelligence_g3/manifests/pr1-E06-correction.json",
        manifest_sha256="d037b501299e941ced69a614cc669a2323cea4d0ccd0c43b37ccb6b85b1ee380")
    value = HistoryInput(replay=replay, journal=HistoryJournal())
    ranking = rank_revisit(value, "b4")
    plan = plan_briefing(value, ranking)
    assert replay.parent.kind == "synthetic_contract_probe"
    assert ranking.algorithm_id == "b4"
    assert len(plan.archive_snapshot_ids) == len(replay.candidates)
    raw, pin = wire(case())
    output = data(run_slice(raw, expected_sha256=pin))
    output["plan"] = deepcopy(data(plan))
    with pytest.raises(G4Error, match="G4_G3_RUNTIME_ADAPTER_REQUIRED"):
        parse(RuntimeBriefing, output)
