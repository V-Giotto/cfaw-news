"""Evidence eligibility and candidate tiers, independent of Persona and G3 ranking."""

from evals.intelligence_g2.pr3.scope import statement_parts

from .contracts import GenerationRequest, RiskNote, digest
from .sensitive import sensitive_text
from .templates import sentence_count

RISK_TEXT = {
    "source_unverified": "来源声明，未独立核验；不能据此认定效果已被独立证明。",
    "scope_not_generalizable": "仅限所列声明范围，不能外推到其他任务或真实部署。",
    "scope_unknown": "适用范围存在未知维度，效果尚未核验。",
    "secondary_material": "原始正文未获得；当前仅为摘要材料提及，效果未核验。",
    "conflicting_reports": "存在相反报告，冲突尚未解决，双方均未被独立核验。",
    "historical_lifecycle": "旧声明仅作为已更正或撤回的历史记录保留。",
    "coverage_gap": "来源覆盖存在缺口；没有新材料不表示没有变化。",
}


def risk(code, ids, basis="claim_status"):
    return RiskNote(code=code, text=RISK_TEXT[code], basis_type=basis, basis_ids=tuple(sorted(ids)))


def choose(view, config):
    bundle = view.bundle
    claims = {c.claim_key: c for c in view.claims}
    refs = {r.ref_id: r for r in view.citations}
    pointers = {p.doc_version_id: p for p in view.source_pointers}
    assessments = {a.claim_key: a for a in bundle.assessments}
    candidates = [claims[k] for k in bundle.current_claim_keys
                  if assessments[k].lifecycle == "current"]
    gaps = {g.code for g in bundle.coverage_gaps}
    if any(c.startswith("unresolved_correction") or c.startswith("unresolved_withdrawal") for c in gaps):
        return None, "hold", "unresolved_lifecycle_target", ()
    if "sensitive_text_excluded" in gaps or any(sensitive_text(c.statement) for c in view.claims):
        return None, "hold", "sensitive_evidence", ()
    order = {"risk": 0, "constraint": 0, "release_fact": 1, "measured_result": 2,
             "capability_claim": 3, "other": 4}
    candidates.sort(key=lambda c: (order[c.claim_type], refs[c.evidence_ref_ids[0]].available_at,
        c.doc_version_id, refs[c.evidence_ref_ids[0]].paragraph_id, c.claim_key))
    mode, tier, reason = "ordinary", "radar", "attributed_limited_evidence"
    if view.transitions:
        transitions = sorted(view.transitions, key=lambda t: (t.effective_at, t.transition_id))
        keys = (tuple(k for t in transitions for k in t.from_claim_keys + t.to_claim_keys)
                + tuple(k for c in bundle.conflicts for k in c.claim_keys))
        candidates = [claims[k] for k in dict.fromkeys(keys)]
        mode, tier, reason = transitions[-1].kind, "focus", "validated_lifecycle_transition"
    elif bundle.conflicts:
        keys = tuple(k for c in bundle.conflicts for k in c.claim_keys)
        candidates = [claims[k] for k in dict.fromkeys(keys)]
        mode, tier, reason = "conflict", "focus", "two_sided_reported_conflict"
    else:
        # Identical visible statements have one representative; every source remains an attachment.
        unique = {}
        for c in candidates:
            # Scope source IDs/spans differ between copies; the complete original
            # statement already contains those qualifiers, without citation identity.
            unique.setdefault(digest(dict(statement=c.statement, claim_type=c.claim_type)), c)
        candidates = list(unique.values())[:config.max_display_claims]
        if candidates:
            main = candidates[0]
            secondary = main.attribution.attribution_kind == "secondary_material"
            if secondary:
                mode = "secondary"
                # Mixing original and secondary claims needs a separate safe template revision.
                candidates = [c for c in candidates if c.attribution.attribution_kind == "secondary_material"]
            elif not main.proposition.ambiguous and (
                main.claim_type == "measured_result" and not main.scope.unknown_dimensions
                and main.scope.conditions and main.proposition.quantities and main.proposition.metric
                or main.claim_type == "release_fact" and main.proposition.subject
                and main.scope.target_version and main.proposition.action
                and main.proposition.action.raw_value.casefold() in {"release", "releases", "is released", "发布"}):
                tier, reason = "focus", "grounded_complete_scope_or_release"
    if not candidates:
        return None, "hold", "no_citable_claim", ()
    if len(candidates) > config.max_display_claims:
        return None, "hold", "mandatory_claims_exceed_limit", ()
    if mode == "ordinary" and any(c.proposition.ambiguous for c in candidates):
        return None, "hold", "ambiguous_proposition", ()
    for c in candidates:
        pointer = pointers[c.doc_version_id]
        if (pointer.redistribution_rights in {"metadata_only", "unknown"}
                or not ({"excerpt", "fulltext"} & set(pointer.policy.allowed_use))):
            return None, "hold", "quote_permission_denied", ()
    if tier == "radar":
        # Scope declarations use semicolons and can remain part of a single sentence.
        # Count the actual quoted clauses too, never just the Chinese wrapper.
        if sum(sentence_count(c.statement) for c in candidates) > 1:
            return None, "hold", "radar_sentence_limit", ()
    risks = [risk("source_unverified", [c.claim_key for c in candidates])]
    if mode == "secondary":
        risks.append(risk("secondary_material", [c.claim_key for c in candidates]))
    if bundle.conflicts:
        risks.append(risk("conflicting_reports", [c.conflict_id for c in bundle.conflicts], "conflict"))
    if mode in {"corrects", "retracts"}:
        risks.append(risk("historical_lifecycle", [c.claim_key for c in candidates]))
    if any(c.proposition.quantities or c.claim_type == "measured_result" for c in candidates):
        risks.append(risk("scope_not_generalizable", [c.claim_key for c in candidates]))
    if any(c.scope.unknown_dimensions for c in candidates) and mode != "secondary":
        risks.append(risk("scope_unknown", [c.claim_key for c in candidates]))
    if bundle.coverage_gaps:
        risks.append(risk("coverage_gap", [g.code for g in bundle.coverage_gaps], "coverage"))
    if tier == "radar":
        # Keep all mandatory cautions in one second sentence, preserving every clause.
        risks = [r.model_copy(update={"text": r.text.rstrip("。")}) for r in risks]
    request = GenerationRequest(claims=tuple(candidates), assessments=tuple(assessments[c.claim_key] for c in candidates),
        citations=tuple(refs[k] for k in sorted({r for c in candidates for r in c.evidence_ref_ids})),
        transitions=view.transitions, mode=mode, required_risks=tuple(risks),
        max_visible_chars=getattr(config.budgets[config.budget_profile], tier))
    return request, tier, reason, tuple(risks)


def visible_text(item):
    if item.tier_candidate == "hold":
        return item.status_text or ""
    # Fact summaries may be rendered in a detail view, so they count against the same budget.
    values = [item.headline.text, item.what_happened.text]
    values.extend(c.statement.text for c in item.claim_summaries)
    if item.why_it_matters:
        values.append(item.why_it_matters.text)
    if item.tier_candidate == "radar" and item.risks:
        values.append("；".join(r.text for r in item.risks) + "。")
    else:
        values.extend(r.text for r in item.risks)
    return "\n".join(values)


def radar_sentences(item):
    # The headline is a label and summaries repeat the same fact; count distinct body plus cautions.
    if item.what_happened is None:
        return 0
    return sentence_count(item.what_happened.text + (" " + "；".join(r.text for r in item.risks) + "。" if item.risks else ""))


def quote_allowance(request, pointers):
    """Union source intervals, once per document even when templates repeat them."""
    used = {}
    for ref in request.citations:
        used.setdefault(ref.doc_version_id, {}).setdefault(ref.paragraph_id, []).append((ref.start, ref.end))
    for doc, paragraphs in used.items():
        amount = 0
        for spans in paragraphs.values():
            end = -1
            for a, b in sorted(spans):
                amount += max(0, b - max(a, end))
                end = max(end, b)
        pointer = pointers[doc]
        limit = pointer.policy.max_excerpt_chars
        if limit is not None and amount > limit:
            return False
    return True


def leading_claim(claim):
    return statement_parts(claim.statement)[0]
