"""Permission, lifecycle, scope and snapshot boundaries specific to PR4."""

from evals.intelligence_g2.contracts import data, digest
from evals.intelligence_g2.pr3.pipeline import bundle_digest
from evals.intelligence_g2.pr4.contracts import PR4Config
from evals.intelligence_g2.pr4.pipeline import generate_items
from evals.intelligence_g2.pr4.replay import projection_record, run_sequence
from evals.intelligence_g2.pr4.validate_output import validate_output
from evals.intelligence_v1.contracts import CoverageWindow, Paragraph
from evals.intelligence_v1.hashing import content_sha256

from ..pr2.support import make_input, sequence
from ..pr3.support import evidence_for
from .support import replay_values, run
from .test_items import rejected, replace_item


def test_permission_degradation_exports_no_unauthorized_quote():
    values, _ = run("T30")
    value = values[0]
    view = value.events[0]
    for rights in ("unknown", "metadata_only"):
        pointers = tuple(p.model_copy(update={"redistribution_rights": rights,
            "policy": p.policy.model_copy(update={"redistribution_rights": rights, "allowed_use": ("metadata",)})})
            for p in view.source_pointers)
        modified = value.model_copy(update={"events": (view.model_copy(update={"source_pointers": pointers}),)})
        result = generate_items(generation_input=modified, config=PR4Config())
        assert result.items[0].tier_candidate == "hold" and result.citations == ()
        assert result.items[0].tier_reason_codes == ("quote_permission_denied",)
        assert "40%" not in str(data(result))


def test_quote_allowance_unions_spans_across_claims_and_templates():
    value = make_input([{"id": "a"}])
    original = replay_values("T30")[0].visible_documents[0].candidate.paragraphs[0].text
    paragraphs = tuple(Paragraph(paragraph_id=f"p{i}", text=original.replace("40%", f"{40+i}%")) for i in range(3))
    wrapped = value.visible_documents[0]
    candidate = wrapped.candidate.model_copy(update={"paragraphs": paragraphs,
        "content_sha256": content_sha256(wrapped.candidate.title, None, paragraphs)})
    value = value.model_copy(update={"visible_documents": (wrapped.model_copy(update={"candidate": candidate,
        "visible_lineage": tuple(row.model_copy(update={"content_sha256": candidate.content_sha256}) for row in wrapped.visible_lineage)}),),
        "sources": tuple(p.model_copy(update={"max_excerpt_chars": 250}) for p in value.sources)})
    parents, evidence = evidence_for([value])
    assert len(evidence[0].claims) == 3
    _, results = run_sequence(parents, evidence, config=PR4Config(budget_profile="high"))
    item = results[0].items[0]
    assert item.tier_candidate == "hold" and item.tier_reason_codes == ("quote_allowance_exceeded",)
    assert results[0].citations == ()
    # A single paragraph appears in the body and summary but is charged only once.
    values, _ = run("T30")
    view = values[0].events[0]
    pointer = view.source_pointers[0]
    pointer = pointer.model_copy(update={"policy": pointer.policy.model_copy(update={"max_excerpt_chars": len(view.citations[0].quote)})})
    value = values[0].model_copy(update={"events": (view.model_copy(update={"source_pointers": (pointer,)}),)})
    assert generate_items(generation_input=value, config=PR4Config()).items[0].tier_candidate == "focus"


def test_forged_transition_for_different_metric_is_rejected():
    values, _ = run("T34")
    view = values[1].events[0]
    transition = view.transitions[0]
    # Keep a valid locator but substitute a target of the wrong type. The full
    # original paragraph remains the same; only the alleged transition is forged.
    forged = transition.model_copy(update={"kind": "retracts"})
    value = values[1].model_copy(update={"events": (view.model_copy(update={"transitions": (forged,)}),)})
    rejected(lambda: generate_items(generation_input=value, config=PR4Config()),
        "G2_PR4_LIFECYCLE_INVALID", "lifecycle", "target", transition.transition_id)


def test_conflict_keeps_both_reports_and_explicit_risk():
    _, rows = run("CONFLICT")
    item = rows[0].items[0]
    assert item.tier_candidate == "focus" and item.evidence_status == "disputed"
    assert len(item.selected_claim_keys) == len(item.evidence_ref_ids) == 2
    assert {c.verification_state for c in item.claim_summaries} == {"disputed"}
    assert "conflicting_reports" in {r.code for r in item.risks}
    assert item.what_happened.template_id == "conflict" and item.why_it_matters is None


def test_fact_slot_cannot_be_unknown_or_swapped():
    values, rows = run("T30")
    item = rows[0].items[0]
    fact = item.what_happened
    bindings = (fact.bindings[0].model_copy(update={"slot": "unrecognized"}),) + fact.bindings[1:]
    bad = item.model_copy(update={"what_happened": fact.model_copy(update={"bindings": bindings})})
    rejected(lambda: validate_output(replace_item(rows[0], bad), values[0], PR4Config()),
        "G2_PR4_FACT_PROVENANCE_INVALID", "facts", "binding.slot", item.selected_claim_keys[0])


def test_source_offline_and_zero_event_coverage_survive_without_network():
    replay = replay_values("T30")[0]
    now = replay.context.as_of
    source = replay.visible_documents[0].candidate.source_id
    window = CoverageWindow(coverage_window_id="offline", source_id=source, start_at=now,
        end_at=now, observed_at=now, status="service_offline", reason="Synthetic source offline")
    replay = replay.model_copy(update={"context": replay.context.model_copy(update={"source_coverage": (window,)}),
        "source_coverage_digest": digest([data(window)])})
    values, rows = run_sequence(*evidence_for([replay]), config=PR4Config())
    assert rows[0].items[0].source_coverage == (window,)
    assert "source_service_offline" in {g.code for g in rows[0].validation.coverage_gaps}
    assert rows[0].items[0].what_happened is not None
    # Projection is an audit of IDs and hashes, not a repeated full text archive.
    export = str(projection_record(values[0]))
    assert "claims a speed gain" not in export and "persona" not in export


def test_reused_document_new_release_does_not_inherit_old_claims():
    original = replay_values("T30")[0].visible_documents[0].candidate.paragraphs[0].text
    parents, evidence = evidence_for(sequence([(0, [{"id": "a", "body": original}]),
        (8, [{"id": "a", "version": 2, "title": "Atlas Tool v2.0 release",
              "body": original.replace("v1.0", "v2.0").replace("40%", "60%")}])]))
    _, rows = run_sequence(parents, evidence, config=PR4Config())
    old_key = rows[0].items[0].event_key
    assert rows[-1].items[0].event_key != old_key
    assert rows[-1].snapshots[0].previous_snapshot_ids == ()
    assert "40%" not in str(data(rows[-1].items[0]))
    assert rows[0].snapshots[0] in rows[-1].next_state.snapshots


def test_scope_risk_cannot_be_removed_even_with_recomputed_hash():
    from evals.intelligence_g2.pr4.snapshots import identify

    values, rows = run("T30")
    item = rows[0].items[0]
    bad = identify(item.model_copy(update={"risks": tuple(r for r in item.risks if r.code != "scope_not_generalizable")}))
    rejected(lambda: validate_output(replace_item(rows[0], bad), values[0], PR4Config()),
        "G2_PR4_SCOPE_RISK_MISSING", "output", "items")


def test_event_revision_is_not_a_substitute_for_lifecycle_evidence():
    values, _ = run("T30")
    view = values[0].events[0]
    bundle = view.bundle.model_copy(update={"event_revision": "1" * 64})
    bundle = bundle.model_copy(update={"bundle_sha256": bundle_digest(bundle)})
    value = values[0].model_copy(update={"events": (view.model_copy(update={"bundle": bundle}),)})
    item = generate_items(generation_input=value, config=PR4Config()).items[0]
    assert item.what_happened.template_id == "attributed_quote"
    assert not {"更正", "撤回"} & set(item.what_happened.text)


def test_multiple_mandatory_lifecycle_pairs_are_not_silently_dropped():
    original = replay_values("T30")[0].visible_documents[0].candidate.paragraphs[0].text
    scope = original[original.index("Task:"):]
    specs = [(0, [{"id": "a", "body": original}, {"id": "b", "body": original.replace("40%", "30%")}]),
        (8, [{"id": "a", "version": 2, "body": "Atlas Tool v1.0 correction: the previous speed gain of 40% is corrected to 4%. " + scope},
             {"id": "b", "version": 2, "body": "Atlas Tool v1.0 correction: the previous speed gain of 30% is corrected to 3%. " + scope}])]
    parents, evidence = evidence_for(sequence(specs))
    assert len(evidence[-1].bundles) == 1 and len(evidence[-1].transitions) == 2
    _, result = run_sequence(parents, evidence, config=PR4Config())
    item = result[-1].items[0]
    assert item.tier_candidate == "hold" and item.tier_reason_codes == ("mandatory_claims_exceed_limit",)
    assert len(item.omitted_claim_keys) == 4 and item.selected_claim_keys == ()


def test_lifecycle_and_conflict_sides_share_the_mandatory_limit():
    original = replay_values("T30")[0].visible_documents[0].candidate.paragraphs[0].text
    scope = original[original.index("Task:"):]
    parents, evidence = evidence_for(sequence([(0, [{"id": "a", "body": original}]), (8, [
        {"id": "a", "version": 2, "body": "Atlas Tool v1.0 correction: the previous speed gain of 40% is corrected to 4%. " + scope},
        {"id": "c", "body": original}, {"id": "d", "body": "Atlas Tool v1.0 reports no speed gain. " + scope}])]))
    assert len(evidence[-1].transitions) == len(evidence[-1].conflicts) == 1
    _, result = run_sequence(parents, evidence, config=PR4Config())
    item = result[-1].items[0]
    assert item.tier_candidate == "hold" and item.tier_reason_codes == ("mandatory_claims_exceed_limit",)
    assert len(item.omitted_claim_keys) == 4


def test_sensitive_paragraph_excluded_upstream_holds_whole_item():
    from evals.intelligence_g2.pr3.contracts import CoverageGap

    values, _ = run("T30")
    view = values[0].events[0]
    gap = CoverageGap(code="sensitive_text_excluded", doc_version_id="a:1")
    bundle = view.bundle.model_copy(update={"coverage_gaps": view.bundle.coverage_gaps + (gap,)})
    bundle = bundle.model_copy(update={"bundle_sha256": bundle_digest(bundle)})
    value = values[0].model_copy(update={"events": (view.model_copy(update={"bundle": bundle}),)})
    result = generate_items(generation_input=value, config=PR4Config())
    assert result.items[0].tier_candidate == "hold" and result.items[0].tier_reason_codes == ("sensitive_evidence",)
    assert result.citations == () and result.items[0].what_happened is None
