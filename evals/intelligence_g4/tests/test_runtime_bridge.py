"""Controlled native runtime; no provider, network, HTTP or production database."""

import json
from copy import deepcopy

import pytest
from cfaw_news.intelligence.runtime import run
from cfaw_news.intelligence.runtime_contracts import RuntimeResult

from evals.intelligence_g2.contracts import json_bytes

from .runtime_support import envelope, wire


def test_synthetic_native_runtime_complete_pool_and_replay():
    raw, pin = wire(envelope())
    result = run(raw, expected_sha256=pin)
    assert result.plan is not None and result.plan.display_order
    assert not result.publishable and result.state == "plan_ready"
    assert len(result.ranking.events) == len(result.context.replay.candidates)
    assert result.archive_snapshot_ids == result.plan.archive_snapshot_ids
    assert run(raw, expected_sha256=pin) == result
    assert RuntimeResult.model_validate_json(result.model_dump_json()) == result


@pytest.mark.parametrize("rights", ["excerpt_only", "unknown", "metadata_only"])
def test_real_uncertainty_has_no_focus_or_radar(rights):
    raw, pin = wire(envelope("real", rights=rights))
    result = run(raw, expected_sha256=pin)
    assert result.state == "raw_news_only" and result.plan is None
    if rights == "excerpt_only":
        assert result.ranking is None and result.stages == ()
        assert result.reason_codes == ("G4_NATIVE_G2_REJECTED:RIGHTS_USE_NOT_ALLOWED",)
        assert result.input.versions[0].content_kind == "feed_summary"
        return
    assert result.ranking is not None and result.archive_snapshot_ids
    from cfaw_news.intelligence.g3_adapter import plan_fields
    from cfaw_news.intelligence.runtime_contracts import RuntimeBudgetInput
    with pytest.raises(ValueError, match="EVIDENCE_NOT_READY"):
        plan_fields(RuntimeBudgetInput(history_input=result.context, ranking=result.ranking,
                                       config=result.input.config.budget))


def test_hold_only_retains_excluded_archive_and_unknown_coverage():
    raw, pin = wire(envelope(body=""))
    result = run(raw, expected_sha256=pin)
    assert result.state == "evidence_not_ready"
    assert not result.plan.display_order and result.plan.diagnostics.excluded_event_keys
    assert result.archive_snapshot_ids and result.coverage.has_gap


@pytest.mark.parametrize("part", ["pool", "snapshot", "quote", "ranking", "plan"])
def test_output_mutation_rejected(part):
    raw, pin = wire(envelope())
    data = json.loads(run(raw, expected_sha256=pin).model_dump_json())
    if part == "pool":
        data["context"]["replay"]["candidates"] = []
    elif part == "snapshot":
        data["archive_snapshot_ids"] = []
    elif part == "quote":
        data["stages"][-1]["evidence"]["citations"][0]["quote"] = "invented evidence"
    elif part == "ranking":
        data["ranking"]["events"][0]["score"] += 1
    else:
        data["plan"]["display_order"] = []
    with pytest.raises(ValueError):
        RuntimeResult.model_validate_json(json_bytes(data))


def test_wrong_pin_and_noncanonical_input_rejected():
    raw, pin = wire(envelope())
    with pytest.raises(ValueError, match="PIN_MISMATCH"):
        run(raw, expected_sha256="0" * 64)
    from evals.intelligence_v1.hashing import sha256_bytes
    raw += b"\n"
    with pytest.raises(ValueError, match="CANONICAL_REQUIRED"):
        run(raw, expected_sha256=sha256_bytes(raw))


def test_mode_mixture_and_accepted_parent_rejected():
    value = envelope()
    for mutation in (dict(kind="accepted_g2"), dict(parent={"kind": "accepted_g2"}),
                     dict(record_origin="real")):
        bad = {**deepcopy(value), **mutation}
        with pytest.raises(ValueError):
            wire(bad)
