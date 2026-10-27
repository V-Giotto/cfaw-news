import copy
import json
import subprocess
import sys

import pytest
from pydantic import ValidationError

from evals.intelligence_g2.contracts import data, digest, json_bytes
from evals.intelligence_g2.pr3.contracts import EvidenceBundle
from evals.intelligence_g2.pr4.contracts import IntelligenceItem
from evals.intelligence_g3.bridge import adapt
from evals.intelligence_g3.contracts import (
    PACKAGE,
    ROOT,
    G3ReplayInput,
    InputManifest,
    NativeStep,
    check_schemas,
    parse,
)
from evals.intelligence_g3.replay import export_input, load_input, relative
from evals.intelligence_v1.exceptions import ContractError

from .support import PINS, Scenario, interaction


def test_generated_schema_matches_native_contracts():
    assert check_schemas()
    schema = G3ReplayInput.model_json_schema()
    assert "EvidenceBundle" in schema["$defs"] and "IntelligenceItem" in schema["$defs"]


@pytest.mark.parametrize("case,count", [("E04-positive", 1), ("E06-correction", 1), ("E10-negative", 0)])
def test_public_pinned_native_fixtures(case, count):
    value = load_input(PACKAGE / "manifests" / f"pr1-{case}.json", manifest_sha256=PINS[case])
    assert len(value.candidates) == count
    assert value.parent.kind == "synthetic_contract_probe"
    assert value.diagnostic.filtered_explicit_inputs == 0
    assert value == G3ReplayInput.model_validate_json(json_bytes(value))
    for c in value.candidates:
        assert isinstance(c.bundle, EvidenceBundle) and isinstance(c.rule_item, IntelligenceItem)
        assert c.presentation.base_item == c.rule_item
        assert isinstance(c.trace_pointer, str) and c.trace_pointer == c.trace.path
    if not count:
        assert any(g.code == "coverage_unknown" for g in value.evidence.validation.coverage_gaps)


def test_native_facts_snapshots_and_historical_claims_are_unchanged():
    s = Scenario()
    value = s.load()
    last = s.payloads["fixture"]["steps"][-1]["record"]
    assert data(value.candidates[0].rule_item) == last["rule"]["items"][0]
    assert data(value.evidence) == last["evidence"]
    assert data(value.identity_state) == last["grouping"]["next_state"]
    assert len(value.published_refs) == 2
    assert len(value.evidence.next_state.claims) > len(value.evidence.claims)


def test_interaction_kinds_are_preserved_without_knowledge_inference():
    s = Scenario()
    s.payloads["history"] = [dict(interaction(s), kind=k, interaction_id=k)
                             for k in ("included", "rendered", "opened", "acknowledged", "dismissed")]
    value = s.load()
    assert {h.kind for h in value.history} == {"included", "rendered", "opened", "acknowledged", "dismissed"}
    assert data(value.persona.persona) == s.payloads["personas"][0]["persona"]


@pytest.mark.parametrize("where", ["persona", "history_occurred", "history_available", "coverage", "candidate", "alias", "citation", "handoff"])
def test_future_metadata_is_an_explicit_failure(where):
    s = Scenario()
    last = s.payloads["fixture"]["steps"][-1]
    future = "2099-01-01T00:00:00Z"
    if where == "persona":
        s.payloads["personas"][0]["persona"]["available_at"] = future
    elif where.startswith("history"):
        h = interaction(s)
        h["occurred_at" if where == "history_occurred" else "available_at"] = future
        s.payloads["history"] = [h]
    elif where == "coverage":
        last["replay_input"]["context"]["source_coverage"] = [dict(observed_at=future)]
    elif where == "candidate":
        last["replay_input"]["visible_documents"][0]["candidate"]["available_at"] = future
    elif where == "alias":
        last["record"]["grouping"]["next_state"]["aliases"] = [dict(effective_at=future)]
    elif where == "citation":
        last["record"]["evidence"]["next_state"]["citations"][0]["available_at"] = future
    else:
        last["handoff"][0]["as_of"] = future
    with pytest.raises(ContractError, match="G3_FUTURE_INPUT"):
        s.load()


@pytest.mark.parametrize("value", ["2026-01-01T12:00:00", "not-a-time", "2026-01-01T12:00:00-00:00"])
def test_ambiguous_or_invalid_time_fails(value):
    s = Scenario()
    s.manifest["as_of"] = value
    with pytest.raises(ContractError):
        s.load()


def test_equivalent_time_offsets_have_same_snapshot():
    s = Scenario()
    a = s.load()
    from datetime import timedelta, timezone

    s.manifest["as_of"] = a.as_of.astimezone(timezone(timedelta(hours=8))).isoformat()
    b = s.load()
    assert a.as_of == b.as_of and a.candidates == b.candidates


@pytest.mark.parametrize("collection", ["personas", "history", "events", "items", "handoff"])
def test_duplicate_ids_are_rejected(collection):
    s = Scenario()
    last = s.payloads["fixture"]["steps"][-1]
    if collection == "personas":
        rows = s.payloads["personas"]
    elif collection == "history":
        s.payloads["history"] = [interaction(s)]
        rows = s.payloads["history"]
    elif collection == "events":
        rows = last["record"]["grouping"]["events"]
    elif collection == "items":
        rows = last["record"]["rule"]["items"]
    else:
        rows = last["handoff"]
    rows.append(copy.deepcopy(rows[0]))
    with pytest.raises(ContractError, match="G3_DUPLICATE_ID"):
        s.load()


@pytest.mark.parametrize("fault", ["missing_event", "missing_view", "foreign_claim", "foreign_citation", "quote", "pool", "broken_prefix", "history_target", "history_persona", "view_revision"])
def test_reference_and_candidate_set_integrity(fault):
    s = Scenario()
    last = s.payloads["fixture"]["steps"][-1]
    record = last["record"]
    if fault == "missing_event":
        record["grouping"]["events"] = []
    elif fault == "missing_view":
        last["handoff"] = []
    elif fault == "foreign_claim":
        record["evidence"]["next_state"]["claims"][0]["evidence_ref_ids"] = ["foreign"]
    elif fault == "foreign_citation":
        record["evidence"]["next_state"]["citations"][0]["doc_version_id"] = "foreign"
    elif fault == "quote":
        record["evidence"]["next_state"]["citations"][0]["quote"] = "synthetic forged quote"
    elif fault == "pool":
        record["pool_sha256"] = "0" * 64
    elif fault == "broken_prefix":
        record["grouping"]["next_state"]["previous_state_sha256"] = "0" * 64
    elif fault.startswith("history"):
        h = interaction(s)
        if fault == "history_target":
            h["target"]["snapshot_id"] = "foreign"
        else:
            h["persona_id"] = "foreign"
        s.payloads["history"] = [h]
    else:
        last["handoff"][0]["event_revision"] = "0" * 64
    with pytest.raises(ContractError, match="G3_REFERENCE_(MISMATCH|NOT_FOUND)"):
        s.load()


def test_explicit_early_selection_reports_withheld_parent_steps():
    s = Scenario()
    first = s.payloads["fixture"]["steps"][0]
    s.manifest.update(step_id=first["record"]["grouping"]["cursor"]["step_id"],
                      as_of=first["record"]["grouping"]["cursor"]["as_of"])
    s.payloads["personas"][0]["persona"] = first["replay_input"]["context"]["persona"]
    s.manifest["persona_version_id"] = s.payloads["personas"][0]["persona"]["persona_version_id"]
    s.payloads["fixture"]["steps"][-1]["record"]["rule"]["items"][0]["headline"] = {"future": "opaque"}
    value = s.load()
    assert value.diagnostic.withheld_parent_steps == 1 and len(value.published_refs) == 1


def test_later_prefix_does_not_authorize_future_evidence_in_earlier_step():
    s = Scenario()
    steps = s.payloads["fixture"]["steps"]
    steps[0]["record"]["evidence"]["next_state"]["citations"][0]["available_at"] = steps[-1]["record"]["grouping"]["cursor"]["as_of"]
    with pytest.raises(ContractError, match="G3_FUTURE_INPUT"):
        s.load()


@pytest.mark.parametrize("fault", ["unknown_delivery", "future_delivery", "foreign_item"])
def test_delivery_references_and_availability_are_checked(fault):
    s = Scenario()
    h = interaction(s)
    s.payloads["history"] = [h]
    if fault == "unknown_delivery":
        h["delivery_id"] = "foreign"
    elif fault == "future_delivery":
        s.payloads["deliveries"][0]["available_at"] = "2099-01-01T00:00:00Z"
    else:
        s.payloads["deliveries"][0]["items"][0] = dict(h["target"], item_id="foreign")
    with pytest.raises(ContractError):
        s.load()


@pytest.mark.parametrize("fault", ["missing", "wrong", "config", "fixture", "unregistered_budget", "parent_kind", "duplicate_json"])
def test_pins_schema_and_configuration_fail_closed(fault):
    s = Scenario()
    pin = s.save()
    if fault in {"config", "fixture"}:
        s.manifest[fault]["sha256"] = "0" * 64
        s.path.write_bytes(json_bytes(s.manifest))
        from evals.intelligence_v1.hashing import sha256_bytes

        pin = sha256_bytes(s.path.read_bytes())
    elif fault == "unregistered_budget":
        s.manifest["attention_budget_seconds"] = 421
        pin = s.save()
    elif fault == "parent_kind":
        s.manifest["kind"] = "accepted_g2"
        pin = s.save()
    elif fault == "duplicate_json":
        s.path.write_bytes(b'{"schema_revision":"g3-pr1-1","schema_revision":"x"}')
        from evals.intelligence_v1.hashing import sha256_bytes

        pin = sha256_bytes(s.path.read_bytes())
    else:
        pin = None if fault == "missing" else "0" * 64
    with pytest.raises(ContractError):
        load_input(s.path, manifest_sha256=pin)


@pytest.mark.parametrize("path", ["../x", "a/../b", "/absolute", "C:/private", "a\\b", "a//b", "evals/intelligence_v1/labels/gold.jsonl"])
def test_paths_cannot_be_normalized_into_authority(path):
    with pytest.raises(ContractError, match="G3_PATH_INVALID"):
        relative(path)


def test_export_is_deterministic_sealed_and_does_not_overwrite():
    s = Scenario()
    pin = s.save()
    for name in ("a", "b"):
        value, manifest_pin = export_input(s.path, manifest_sha256=pin, out=s.root / name)
        seal = json.loads((s.root / name / "sealed.json").read_bytes())
        assert seal["run_manifest_sha256"] == manifest_pin
        assert digest(value) == json.loads((s.root / name / "validation_report.json").read_bytes())["input_sha256"]
    assert (s.root / "a/input_snapshot.json").read_bytes() == (s.root / "b/input_snapshot.json").read_bytes()
    assert (s.root / "a/run_manifest.json").read_bytes() == (s.root / "b/run_manifest.json").read_bytes()
    with pytest.raises(ContractError, match="G3_OUTPUT_EXISTS"):
        export_input(s.path, manifest_sha256=pin, out=s.root / "a")


def test_invalid_inputs_create_no_output_and_cli_returns_safe_diagnostic():
    s = Scenario()
    pin = s.save()
    out = s.root / "absent"
    result = subprocess.run([sys.executable, "-B", "-m", "evals.intelligence_g3.replay",
        "--manifest", str(s.path), "--manifest-sha256", "0" * 64, "--out", str(out)],
        cwd=ROOT, capture_output=True, text=True, timeout=30)
    assert pin != "0" * 64
    assert result.returncode == 1 and not out.exists()
    assert json.loads(result.stdout) == dict(ok=False, code="G3_MANIFEST_SHA_MISMATCH",
                                            stage="g3_pr1", field="manifest_sha256")


def test_model_copy_future_poison_is_rejected_before_serialization():
    s = Scenario()
    value = s.load()
    steps = tuple(parse(NativeStep, r) for r in s.payloads["fixture"]["steps"])
    doc = steps[-1].replay_input.visible_documents[0]
    poisoned = doc.model_copy(update={"candidate": doc.candidate.model_copy(update={
        "available_at": "2099-01-01T00:00:00Z", "title": object()})})
    replay = steps[-1].replay_input.model_copy(update={"visible_documents": (poisoned,)})
    steps = steps[:-1] + (steps[-1].model_copy(update={"replay_input": replay}),)
    with pytest.raises(ContractError, match="G3_FUTURE_INPUT"):
        adapt(manifest=parse(InputManifest, s.manifest), binding=value.parent, steps=steps,
              personas=s.payloads["personas"], history=[], deliveries=[], diagnostic=value.diagnostic)


def test_strict_extra_fields_and_immutable_native_objects():
    value = Scenario().load()
    raw = data(value)
    raw["rank"] = 1
    with pytest.raises(ValidationError):
        G3ReplayInput.model_validate_json(json_bytes(raw))
    with pytest.raises(ValidationError):
        value.candidates[0].rule_item.tier_candidate = "focus"


def test_prediction_imports_do_not_load_evaluators_providers_or_user_settings():
    script = '''
import sys
import evals.intelligence_g3.replay
assert not any(n.startswith("cfaw_news.") and n != "cfaw_news.retrieval" for n in sys.modules)
assert not any(n.endswith((".evaluate", ".oracle", ".reference_loader")) for n in sys.modules if n.startswith("evals."))
'''
    p = subprocess.run([sys.executable, "-B", "-c", script], cwd=ROOT, capture_output=True, text=True, timeout=30)
    assert p.returncode == 0, p.stderr
