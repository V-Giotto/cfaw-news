"""Boundary tests target observable refusals and provenance, not duplicated implementations."""

from copy import deepcopy

import pytest
from pydantic import ValidationError

from evals.intelligence_g2.contracts import data, json_bytes
from evals.intelligence_g4.contracts import (
    G4Error,
    RuntimeInput,
    RuntimeInteraction,
    RuntimeStatus,
    decode,
    parse,
)
from evals.intelligence_g4.schema import check_schemas, payloads
from evals.intelligence_v1.hashing import sha256_bytes

from .support import LATER, NOW, case, repeat


def rejected(value, code):
    with pytest.raises(G4Error) as caught:
        decode(json_bytes(value))
    assert caught.value.code == code


@pytest.mark.parametrize("field", ["kind", "gold", "acceptance", "extra"])
def test_runtime_does_not_accept_offline_parent_or_gold_channels(field):
    value = case()
    value[field] = "accepted_g2" if field == "kind" else "untrusted"
    rejected(value, "G4_SCHEMA_INVALID")


@pytest.mark.parametrize("target", ["document", "persona", "coverage"])
def test_future_metadata_rejected_before_bad_document_body_hash(target):
    value = case()
    step = value["steps"][0]
    step["documents"][0]["candidate"]["content_sha256"] = "0" * 64
    row = (step["documents"][0]["candidate"] if target == "document" else
           step["persona"]["persona"] if target == "persona" else step["source_coverage"][0])
    row["observed_at" if target == "coverage" else "available_at"] = LATER
    rejected(value, "G4_FUTURE_INPUT")


@pytest.mark.parametrize("target", ["document", "source", "persona"])
def test_real_and_synthetic_cannot_mix(target):
    value = case()
    row = (value["steps"][0]["documents"][0] if target == "document" else
           value["sources"][0]["policy"] if target == "source" else value["steps"][0]["persona"])
    row["record_origin"] = "real"
    rejected(value, "G4_PROVENANCE_INVALID" if target != "persona" else "G4_NATIVE_G2_REJECTED")


def test_unknown_rights_with_body_is_rejected_not_relabelled_as_original_text():
    rejected(case(origin="real"), "G4_RIGHTS_INVALID")
    value = case(body="", origin="real")
    assert decode(json_bytes(value)).record_origin == "real"
    value["sources"][0]["policy"]["allowed_use"] = ["fulltext"]
    rejected(value, "G4_RIGHTS_INVALID")


@pytest.mark.parametrize("fault,code", [
    ("duplicate_source", "G4_DUPLICATE_ID"), ("duplicate_step", "G4_DUPLICATE_ID"),
    ("missing_coverage", "G4_REFERENCE_MISMATCH"), ("unknown_source", "G4_REFERENCE_MISMATCH"),
    ("interval", "G4_INVALID_INTERVAL"), ("hash", "G4_HASH_MISMATCH"),
    ("naive", "G4_NATIVE_G2_REJECTED"), ("algorithm", "G4_SCHEMA_INVALID"),
    ("old_policy", "G4_SCHEMA_INVALID"), ("too_many_steps", "G4_SCHEMA_INVALID"),
])
def test_hard_gates(fault, code):
    value = case()
    step = value["steps"][0]
    if fault == "duplicate_source":
        value["sources"].append(deepcopy(value["sources"][0]))
    elif fault == "duplicate_step":
        value["steps"].append(deepcopy(step))
    elif fault == "missing_coverage":
        step["source_coverage"] = []
    elif fault == "unknown_source":
        step["documents"][0]["candidate"]["source_id"] = "missing"
    elif fault == "interval":
        step["time_window_start"] = LATER
    elif fault == "hash":
        step["documents"][0]["candidate"]["content_sha256"] = "0" * 64
    elif fault == "naive":
        step["as_of"] = "2026-01-02T12:00:00"
    elif fault == "algorithm":
        value["config"]["algorithm"] = "p1"
    elif fault == "old_policy":
        value["config"]["fact_signature_policy_sha256"] = "0" * 64
    else:
        value["steps"] *= 9
    rejected(value, code)


def test_replay_preserves_exact_versions_and_rejects_changed_or_invented_history():
    value = repeat(case())
    assert len(decode(json_bytes(value)).steps) == 2
    value["steps"][1]["documents"][0]["source_article_id"] = "changed"
    rejected(value, "G4_HASH_MISMATCH")
    value = case()
    value["steps"][0]["documents"][0]["visible_lineage"][0]["doc_version_id"] = "uncaptured"
    rejected(value, "G4_REFERENCE_MISMATCH")


def test_public_parser_rejects_copied_and_constructed_poisoned_instances():
    value = decode(json_bytes(case()))
    poisoned = value.model_copy(update={"kind": "accepted_g2"})
    with pytest.raises(G4Error, match="G4_SCHEMA_INVALID"):
        parse(RuntimeInput, poisoned)


def test_persona_versions_are_immutable_and_cannot_roll_back_between_steps():
    value = repeat(case())
    value["steps"][1]["persona"]["persona"]["domain_interests"] = ["changed"]
    rejected(value, "G4_HASH_MISMATCH")
    value = repeat(case())
    p = value["steps"][1]["persona"]["persona"]
    p.update(persona_version_id="ambiguous:v2")
    rejected(value, "G4_SEQUENCE_INVALID")


def test_explicit_budget_and_limits_are_required_without_p1_promotion():
    value = case()
    value["config"].pop("budget")
    rejected(value, "G4_SCHEMA_INVALID")
    value = case()
    value["config"]["max_documents_per_step"] = 1000
    rejected(value, "G4_SCHEMA_INVALID")


def test_empty_budget_object_cannot_inherit_native_70_30_default():
    value = case()
    value["config"]["budget"] = {}
    rejected(value, "G4_SCHEMA_INVALID")


def interaction(kind="opened"):
    return dict(interaction_id="i1", idempotency_key="key", persona_id="local", delivery_id="d1",
        target=dict(event_key="event", event_revision="a" * 64, item_id="item", snapshot_id="snap",
                    as_of=NOW), kind=kind, occurred_at=NOW, available_at=NOW,
        source="explicit_user", record_origin="real", provenance_uri="https://example.com/")


def test_interactions_preserve_signal_and_do_not_infer_acknowledgment():
    value = parse(RuntimeInteraction, interaction())
    assert value.kind == "opened" and value.feedback is None
    raw = interaction("rendered")
    with pytest.raises(G4Error, match="G4_INTERACTION_INVALID"):
        parse(RuntimeInteraction, raw)
    raw.update(source="client")
    assert parse(RuntimeInteraction, raw).kind == "rendered"


@pytest.mark.parametrize("change", [dict(feedback="known"), dict(retracts_id="old"),
                                  dict(kind="retract", retracts_id="i1")])
def test_invalid_feedback_and_retractions_are_rejected(change):
    with pytest.raises(G4Error, match="G4_INTERACTION_INVALID"):
        parse(RuntimeInteraction, {**interaction(), **change})


def test_status_cannot_claim_validated_runtime_or_publishable_synthetic():
    raw = dict(record_origin="synthetic", state="raw_news_only", code="G4_G3_RUNTIME_ADAPTER_REQUIRED")
    for field in ("publishable", "g3_runtime_validated"):
        with pytest.raises(G4Error, match="G4_SCHEMA_INVALID"):
            parse(RuntimeStatus, {**raw, field: True})
    with pytest.raises(G4Error, match="G4_OUTPUT_MISMATCH"):
        parse(RuntimeStatus, {**raw, "state": "insufficient_evidence"})


def test_schema_check_compares_real_bytes_and_complete_file_set(tmp_path):
    assert check_schemas()
    for name, raw in payloads().items():
        (tmp_path / name).write_bytes(raw)
    assert check_schemas(tmp_path)
    one = next(tmp_path.glob("*.schema.json"))
    one.write_bytes(b"{}")
    assert not check_schemas(tmp_path)
    one.write_bytes(payloads()[one.name])
    (tmp_path / "extra.schema.json").write_bytes(b"{}")
    assert not check_schemas(tmp_path)


def test_json_duplicates_and_unknown_fields_are_rejected():
    with pytest.raises(G4Error, match="G4_SCHEMA_INVALID"):
        decode(b'{"kind":"runtime_local_v1","kind":"accepted_g2"}')
    raw = data(parse(RuntimeInput, case()))
    raw["steps"][0]["documents"][0]["invented_evidence"] = True
    with pytest.raises((G4Error, ValidationError)):
        decode(json_bytes(raw))
    assert len(sha256_bytes(json_bytes(raw))) == 64


@pytest.mark.parametrize("field,bad", [("steps", None), ("steps", 1)])
def test_malformed_top_level_shapes_have_safe_errors(field, bad):
    value = case()
    value[field] = bad
    rejected(value, "G4_SCHEMA_INVALID")


@pytest.mark.parametrize("field,bad", [("documents", None), ("persona", "invalid"),
                                      ("source_coverage", 1)])
def test_malformed_nested_shapes_have_safe_errors(field, bad):
    value = case()
    value["steps"][0][field] = bad
    rejected(value, "G4_SCHEMA_INVALID")
