"""One deterministic, conservative candidate item per current event."""

from .contracts import Diagnostic, GenerationResult, IntelligenceItem, SnapshotState, digest
from .policy import choose, quote_allowance, visible_text
from .snapshots import identify, observe
from .templates import RuleItemGenerator

HOLD = {
    "no_citable_claim": "暂缓生成：缺少可安全引用的正文声明。",
    "ambiguous_proposition": "暂缓生成：声明存在歧义，无法安全表达。",
    "unresolved_lifecycle_target": "暂缓生成：更正或撤回的目标尚未解析。",
    "sensitive_evidence": "暂缓生成：材料包含敏感片段。",
    "quote_permission_denied": "暂缓生成：缺少必要的原文引用权限。",
    "quote_allowance_exceeded": "暂缓生成：必要引用超过来源额度。",
    "mandatory_claims_exceed_limit": "暂缓生成：必要的双方声明无法完整呈现。",
    "radar_sentence_limit": "暂缓生成：完整原句及限制无法在两句内安全表达。",
    "visible_budget_exceeded": "暂缓生成：必要的原句、限定和风险超过成文预算。",
}


def assemble(value, config):
    items, snapshots, refs = [], [], {}
    for view in value.events:
        bundle = view.bundle
        request, tier, reason, risks = choose(view, config)
        pointers = {p.doc_version_id: p for p in view.source_pointers}
        if request and not quote_allowance(request, pointers):
            request, tier, reason, risks = None, "hold", "quote_allowance_exceeded", ()
        draft = RuleItemGenerator().generate(request) if request else None
        selected = tuple(c.claim_key for c in request.claims) if request else ()
        all_keys = set(bundle.current_claim_keys + bundle.historical_claim_keys)
        item = IntelligenceItem(item_id="pending", content_revision="0" * 64, fact_revision="0" * 64,
            event_key=bundle.event_key, event_revision=bundle.event_revision,
            headline=draft.headline if draft else None, what_happened=draft.what_happened if draft else None,
            why_it_matters=draft.why_it_matters if draft else None,
            claim_summaries=draft.claim_summaries if draft else (), selected_claim_keys=selected,
            omitted_claim_keys=tuple(sorted(all_keys - set(selected))),
            evidence_ref_ids=tuple(r.ref_id for r in request.citations) if request else (),
            source_pointers=view.source_pointers,
            evidence_status="insufficient" if tier == "hold" else "disputed" if bundle.conflicts else "attributed",
            risks=risks, uncertainties=tuple(sorted(set(bundle.uncertainties))),
            source_coverage=value.source_coverage, tier_candidate=tier, tier_reason_codes=(reason,),
            status_text=HOLD[reason] if tier == "hold" else None,
            estimated_read_seconds=0 if tier == "hold" else config.focus_read_seconds if tier == "focus" else config.radar_read_seconds,
            record_origin="synthetic" if all(p.record_origin == "synthetic" for p in view.source_pointers) else "real")
        if tier != "hold" and len(visible_text(item)) > getattr(config.budgets[config.budget_profile], tier):
            item = item.model_copy(update={"headline": None, "what_happened": None, "why_it_matters": None,
                "claim_summaries": (), "selected_claim_keys": (), "omitted_claim_keys": tuple(sorted(all_keys)),
                "evidence_ref_ids": (), "evidence_status": "insufficient", "risks": (), "tier_candidate": "hold",
                "tier_reason_codes": ("visible_budget_exceeded",), "status_text": HOLD["visible_budget_exceeded"],
                "estimated_read_seconds": 0})
        elif request:
            refs.update({r.ref_id: r for r in request.citations})
        item = identify(item)
        items.append(item)
        snapshots.append(observe(item, view, value))
    prior = value.previous_state
    metadata = {p.doc_version_id: p for p in prior.source_metadata} if prior else {}
    for view in value.events:
        metadata.update({p.doc_version_id: p for p in view.source_pointers})
    state = SnapshotState(namespace=value.namespace, config_sha256=digest(config), cursor=value.cursor,
        previous_state_sha256=digest(prior) if prior else None,
        source_metadata=tuple(metadata[k] for k in sorted(metadata)),
        snapshots=(prior.snapshots if prior else ()) + tuple(snapshots))
    return GenerationResult(cursor=value.cursor, items=tuple(items), snapshots=tuple(snapshots),
        citations=tuple(refs[k] for k in sorted(refs)), next_state=state,
        validation=Diagnostic(ok=True, counts={"events": len(value.events), "items": len(items),
            "focus": sum(i.tier_candidate == "focus" for i in items),
            "radar": sum(i.tier_candidate == "radar" for i in items),
            "hold": sum(i.tier_candidate == "hold" for i in items), "citations": len(refs),
            "model_calls": 0}, coverage_gaps=value.coverage_gaps))


def generate_items(*, generation_input, config):
    from .validate_output import checked_input, validate_output

    value, config = checked_input(generation_input, config)
    result = assemble(value, config)
    validate_output(result, value, config)
    return result
