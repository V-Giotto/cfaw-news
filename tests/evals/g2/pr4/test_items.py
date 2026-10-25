"""T29-T35: positive controls and specific adversarial assertions."""

from datetime import timedelta

import pytest

from evals.intelligence_g2.contracts import G2Error, data, digest
from evals.intelligence_g2.pr3.contracts import PR3Config
from evals.intelligence_g2.pr3.extract import extract_claims
from evals.intelligence_g2.pr3.pipeline import bundle_digest
from evals.intelligence_g2.pr4.contracts import PR4Config, parse
from evals.intelligence_g2.pr4.pipeline import generate_items
from evals.intelligence_g2.pr4.policy import choose, radar_sentences, visible_text
from evals.intelligence_g2.pr4.replay import run_sequence
from evals.intelligence_g2.pr4.snapshots import identify
from evals.intelligence_g2.pr4.templates import RuleItemGenerator, fact
from evals.intelligence_g2.pr4.validate_output import validate_output

from ..pr2.support import make_input, sequence
from ..pr3.support import evidence_for, inputs_for
from .support import FIXTURE, cases, replay_values, run


def rejected(call, code, stage, field, record_id=None):
    with pytest.raises(G2Error) as caught:
        call()
    e = caught.value
    assert (e.code, e.stage, e.field) == (code, stage, field)
    if record_id is not None:
        assert e.record_id == record_id


def replace_item(result, item):
    return result.model_copy(update={"items": (item,)})


def test_frozen_development_expectations():
    from evals.intelligence_g2.contracts import read_json
    from evals.intelligence_v1.hashing import sha256_bytes

    raw = (FIXTURE / "reference/expectations.json").read_bytes()
    manifest = read_json((FIXTURE / "reference/manifest.json").read_bytes())
    assert sha256_bytes(raw) == manifest["files"][0]["sha256"]
    refs = {r["case_id"]: r for r in read_json(raw)["cases"]}
    assert len(cases()) == len(refs) == 13
    for case in cases():
        _, results = run(case["case_id"])
        assert [sorted(i.tier_candidate for i in r.items) for r in results] == refs[case["case_id"]]["tiers"]


def test_T29_ten_duplicates_one_item_all_sources_reachable():
    values, results = run("T29")
    item = results[0].items[0]
    assert len(values[0].events) == len(results[0].items) == 1
    assert len(item.selected_claim_keys) == 1
    assert len(item.omitted_claim_keys) == 9
    assert len(item.source_pointers) == len({p.doc_version_id for p in item.source_pointers}) == 10
    assert len(results[0].citations) == 1
    assert all(p.canonical_url == "synthetic://example/release" for p in item.source_pointers)
    bad = results[0].model_copy(update={"items": (item, item)})
    rejected(lambda: validate_output(bad, values[0], PR4Config()),
        "G2_PR4_DUPLICATE_EVENT", "output", "event_key", item.event_key)


def test_T29_no_focus_or_radar_quota_or_unrelated_merging():
    parents, evidence = evidence_for([make_input([
        {"id": str(i), "title": f"Project {i} Tool v1.0 release", "body": f"Project {i} Tool v1.0 releases plugins."}
        for i in range(15)])])
    _, results = run_sequence(parents, evidence, config=PR4Config())
    assert len(results[0].items) == 15
    assert len({i.event_key for i in results[0].items}) == 15
    assert all(i.tier_candidate == "focus" for i in results[0].items)


def test_T30_complete_single_source_focus_is_attributed_with_scope():
    values, rows = run("T30")
    item = rows[0].items[0]
    assert item.tier_candidate == "focus" and item.evidence_status == "attributed"
    assert len(item.claim_summaries) == 1
    summary = item.claim_summaries[0]
    assert summary.scope.unknown_dimensions == ()
    assert summary.verification_state == "source_attributed"
    assert {r.code for r in item.risks} >= {"source_unverified", "scope_not_generalizable"}
    assert item.why_it_matters.kind == "inference" and item.why_it_matters.text.startswith("推断：")
    assert len(visible_text(item)) <= 1200 and item.estimated_read_seconds == 90
    assert "40%" in item.what_happened.text
    assert values[0].events[0].bundle.event_revision == item.event_revision


@pytest.mark.parametrize("mode", ["risk", "scope", "independent"])
def test_T30_omitted_risk_scope_or_independent_upgrade_rejected(mode):
    values, rows = run("T30")
    item = rows[0].items[0]
    if mode == "risk":
        bad = item.model_copy(update={"risks": ()})
        rejected(lambda: validate_output(replace_item(rows[0], bad), values[0], PR4Config()),
            "G2_PR4_SCOPE_RISK_MISSING", "output", "risks", item.event_key)
    elif mode == "scope":
        c = item.claim_summaries[0]
        bad_scope = c.scope.model_copy(update={"task": None})
        bad = identify(item.model_copy(update={"claim_summaries": (c.model_copy(update={"scope": bad_scope}),)}))
        rejected(lambda: validate_output(replace_item(rows[0], bad), values[0], PR4Config()),
            "G2_PR4_SCOPE_RISK_MISSING", "output", "items")
    else:
        c = item.claim_summaries[0].model_copy(update={"verification_state": "independently_supported"})
        bad = item.model_copy(update={"claim_summaries": (c,)})
        rejected(lambda: validate_output(replace_item(rows[0], bad), values[0], PR4Config()),
            "SCHEMA_INVALID", "output", "items.0.claim_summaries.0.verification_state")


def test_T30_budget_hold_keeps_omitted_keys_never_truncates():
    body = replay_values("T30")[0].visible_documents[0].candidate.paragraphs[0].text
    body = body.replace("batch=1", "batch=1; Conditions: " + "x" * 360)
    parents, evidence = evidence_for([make_input([{"id": "a", "body": body}])])
    _, rows = run_sequence(parents, evidence, config=PR4Config(budget_profile="low"))
    item = rows[0].items[0]
    assert item.tier_candidate == "hold" and item.tier_reason_codes == ("visible_budget_exceeded",)
    assert item.headline is item.what_happened is None
    assert item.evidence_ref_ids == rows[0].citations == ()
    assert item.omitted_claim_keys and len(visible_text(item)) <= 160


def test_T31_radar_is_short_and_long_quote_cannot_hide_in_wrapper():
    _, rows = run("T31")
    item = rows[0].items[0]
    assert item.tier_candidate == "radar" and radar_sentences(item) <= 2
    assert item.why_it_matters is None and item.estimated_read_seconds == 12
    _, long = run("LONG_RADAR")
    assert long[0].items[0].tier_candidate == "hold"
    assert long[0].items[0].tier_reason_codes == ("radar_sentence_limit",)


def test_T31_contract_only_secondary_projection_does_not_claim_live_source():
    # G1 synthetic bridge intentionally requires synthetic_text. Exercise secondary
    # rendering with an explicit synthetic contract projection, not a fake real-source run.
    replay = replay_values("T30")[0]
    wrapped = replay.visible_documents[0]
    replay = replay.model_copy(update={"visible_documents": (wrapped.model_copy(update={"candidate":
        wrapped.candidate.model_copy(update={"content_kind": "feed_summary"})}),)})
    _, groups = inputs_for(replay_values("T30"))
    extracted = extract_claims(replay_input=replay, events=groups[0].events, config=PR3Config())
    values, _ = run("T30")
    original = values[0].events[0]
    c = extracted.claims[0]
    a = original.bundle.assessments[0].model_copy(update={"verification_state": "unverified"})
    b = original.bundle.model_copy(update={"current_claim_keys": (c.claim_key,), "assessments": (a,)})
    # Use a short secondary sentence so that the radar body fits its honest two-sentence limit.
    # The long T30 whole paragraph plus mandatory secondary risks safely degrades to hold.
    b = b.model_copy(update={"bundle_sha256": bundle_digest(b)})
    view = original.model_copy(update={"bundle": b, "claims": extracted.claims,
        "source_pointers": tuple(p.model_copy(update={"content_kind": "feed_summary"}) for p in original.source_pointers)})
    value = values[0].model_copy(update={"events": (view,)})
    result = generate_items(generation_input=value, config=PR4Config())
    assert result.items[0].tier_candidate == "hold"
    replay = replay_values("T31")[0]
    wrapped = replay.visible_documents[0]
    replay = replay.model_copy(update={"visible_documents": (wrapped.model_copy(update={"candidate":
        wrapped.candidate.model_copy(update={"content_kind": "feed_summary"})}),)})
    values, _ = run("T31")
    original = values[0].events[0]
    extracted = extract_claims(replay_input=replay, events=inputs_for(replay_values("T31"))[1][0].events, config=PR3Config())
    a = original.bundle.assessments[0].model_copy(update={"verification_state": "unverified"})
    b = original.bundle.model_copy(update={"assessments": (a,)})
    b = b.model_copy(update={"bundle_sha256": bundle_digest(b)})
    view = original.model_copy(update={"claims": extracted.claims, "bundle": b,
        "source_pointers": tuple(p.model_copy(update={"content_kind": "feed_summary"}) for p in original.source_pointers)})
    value = values[0].model_copy(update={"events": (view,)})
    result = generate_items(generation_input=value, config=PR4Config())
    assert result.items[0].tier_candidate == "radar"
    assert result.items[0].evidence_status == "attributed"
    assert result.items[0].claim_summaries[0].verification_state == "unverified"
    request, tier, _, risks = choose(view, PR4Config())
    assert tier == "radar" and request.mode == "secondary"
    assert "secondary_material" in {r.code for r in risks}
    assert request.claims[0].proposition.quantities == ()
    assert RuleItemGenerator().generate(request).what_happened.text.startswith("摘要材料：")


def test_T32_empty_and_body_loss_are_observable_not_filled():
    values, rows = run("T32_EMPTY")
    assert rows[0].items == rows[0].snapshots == rows[0].citations == ()
    assert rows[0].validation.coverage_gaps
    assert values[0].events == ()
    _, rows = run("T32_BODY")
    item = rows[0].items[0]
    assert item.tier_candidate == "hold" and item.headline is item.what_happened is None
    assert item.evidence_status == "insufficient" and item.selected_claim_keys == ()
    assert "no_change" not in str(data(rows[0])) and "世界无变化" not in str(data(rows[0]))


@pytest.mark.parametrize("change", [("40%", "400%"), ("up to", "average"), ("v1.0", "v2.0")])
def test_T33_fact_text_must_be_reconstructable(change):
    values, rows = run("T33")
    item = rows[0].items[0]
    text = item.what_happened.model_copy(update={"text": item.what_happened.text.replace(*change)})
    bad = item.model_copy(update={"what_happened": text})
    rejected(lambda: validate_output(replace_item(rows[0], bad), values[0], PR4Config()),
        "G2_PR4_FACT_PROVENANCE_INVALID", "facts", "text", item.selected_claim_keys[0])


def test_T33_span_and_task_metric_injection_rejected():
    values, rows = run("T30")
    item = rows[0].items[0]
    text = item.what_happened
    bindings = tuple(b.model_copy(update={"end": b.end - 1}) if b.field == "statement" else b for b in text.bindings)
    bad = item.model_copy(update={"what_happened": text.model_copy(update={"bindings": bindings})})
    rejected(lambda: validate_output(replace_item(rows[0], bad), values[0], PR4Config()),
        "G2_PR4_FACT_PROVENANCE_INVALID", "facts", "binding.value", item.selected_claim_keys[0])
    view = values[0].events[0]
    claim = view.claims[0]
    metric = claim.scope.task
    changed = claim.model_copy(update={"proposition": claim.proposition.model_copy(update={"metric": metric})})
    bad_view = view.model_copy(update={"claims": (changed,)})
    rejected(lambda: generate_items(generation_input=values[0].model_copy(update={"events": (bad_view,)}), config=PR4Config()),
        "G2_PR3_FIELD_PROVENANCE_INVALID", "scope", "grounded_fields", claim.claim_key)


@pytest.mark.parametrize("unit", ["40 percentage points", "approximately 40%", "at least 40%"])
def test_T33_nonstandard_units_and_qualifiers_not_rewritten(unit):
    replay = replay_values("T30")[0]
    body = replay.visible_documents[0].candidate.paragraphs[0].text.replace("40%", unit)
    parents, rows = evidence_for([make_input([{"id": "a", "body": body}])])
    values, result = run_sequence(parents, rows, config=PR4Config())
    item = result[0].items[0]
    if item.what_happened:
        assert unit in item.what_happened.text
    else:
        assert item.tier_candidate == "hold"
    ref = values[0].events[0].citations[0]
    assert unit in fact("attributed_quote", values[0].events[0].claims, {ref.ref_id: ref}).text


@pytest.mark.parametrize("case,kind,state", [("T34", "corrects", "superseded"), ("T34_RETRACT", "retracts", "retracted")])
def test_T34_lifecycle_requires_transition_both_refs_and_immutable_prior(case, kind, state):
    values, rows = run(case)
    before = digest(rows[0])
    item = rows[-1].items[0]
    assert item.event_key == rows[0].items[0].event_key
    assert item.event_revision != rows[0].items[0].event_revision
    assert values[-1].events[0].transitions[0].kind == kind
    assert len(item.selected_claim_keys) == len(item.evidence_ref_ids) == 2
    assert state in {c.lifecycle for c in item.claim_summaries}
    assert item.what_happened.template_id == "lifecycle" and len(rows[-1].citations) == 2
    assert rows[-1].snapshots[0].previous_snapshot_ids == (rows[0].snapshots[0].snapshot_id,)
    assert digest(rows[0]) == before


def test_T34_scope_metric_withdrawal_remains_unresolved_hold():
    values, rows = run("T34_UNRESOLVED")
    assert values[-1].events[0].transitions == ()
    assert rows[-1].items[0].tier_reason_codes == ("unresolved_lifecycle_target",)
    assert all(c.lifecycle != "retracted" for c in values[-1].events[0].bundle.assessments)


def test_T34_negative_intention_and_unmarked_number_change_not_lifecycle():
    old = replay_values("T30")[0].visible_documents[0].candidate.paragraphs[0].text
    scope = old[old.index("Task:"):]
    for body in ("Atlas Tool v1.0 reports it will not withdraw its previous speed gain of 40%.",
                 "Atlas Tool v1.0 claims a speed gain of 4%."):
        parents, evidence = evidence_for(sequence([(0, [{"id": "a", "body": old}]),
            (8, [{"id": "a", "version": 2, "body": body + " " + scope}])]))
        _, rows = run_sequence(parents, evidence, config=PR4Config())
        assert evidence[-1].transitions == ()
        assert all(c.lifecycle != "retracted" for c in evidence[-1].assessments)
        assert rows[-1].items[0].what_happened is None or rows[-1].items[0].what_happened.template_id != "lifecycle"


def test_T35_persona_changes_never_enter_request_or_facts():
    replay = replay_values("T35")[0]
    model = replay.context.persona
    edits = {name: ("PERSONA-PRIVATE-CANARY",) for name in (
        "domain_interests", "current_goals", "hard_constraints", "knowledge_known")}
    edits.update(locale="PERSONA-PRIVATE-CANARY", exploration_preference="PERSONA-PRIVATE-CANARY", attention_budget_seconds=1)
    altered = replay.model_copy(update={"context": replay.context.model_copy(update={
        "persona": model.model_copy(update=edits), "attention_budget_seconds": 1})})
    a, ar = run_sequence(*evidence_for([replay]), config=PR4Config())
    b, br = run_sequence(*evidence_for([altered]), config=PR4Config())
    assert data(a[0]) == data(b[0])
    assert data(ar[0]) == data(br[0])
    assert "PERSONA-PRIVATE-CANARY" not in str(data(br[0]))
    assert altered.context.persona != model


def test_inference_must_not_be_inserted_as_fact():
    values, rows = run("T30")
    item = rows[0].items[0]
    bad = item.model_copy(update={"headline": item.headline.model_copy(update={"text": "推断：该效果很重要"})})
    rejected(lambda: validate_output(replace_item(rows[0], bad), values[0], PR4Config()),
        "G2_PR4_INFERENCE_IN_FACT", "facts", "text")


def test_temporal_preflight_before_invalid_quote_shape():
    values, _ = run("T30")
    row = data(values[0])
    row["events"][0]["citations"][0]["available_at"] = (values[0].cursor.as_of + timedelta(days=1)).isoformat()
    row["events"][0]["citations"][0]["quote"] = {"invalid": "FUTURE-POISON"}
    rejected(lambda: generate_items(generation_input=row, config=PR4Config()),
        "FUTURE_VERSION", "temporal", "available_at", "a:1")


def test_contract_strictness_schema_and_fixed_budget_revision():
    from evals.intelligence_g2.pr4.contracts import check_schemas

    assert check_schemas()
    for edit in ({"unknown": True}, {"max_display_claims": "3"}):
        rejected(lambda: parse(PR4Config, {**data(PR4Config()), **edit}), "SCHEMA_INVALID", "input", next(iter(edit)))
    with pytest.raises(G2Error):
        parse(PR4Config, {**data(PR4Config()), "budgets": {"standard": {"focus": 1, "radar": 1, "hold": 160}}})
