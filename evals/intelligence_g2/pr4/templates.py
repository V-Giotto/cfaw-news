"""Closed templates. Bindings preserve original language, numbers and qualifiers."""

import re

from .contracts import Binding, ClaimSummary, FactText, GenerationDraft, Inference, fail

INFERENCE = "推断：若在相同条件下复现，可作为该任务进一步评估的线索。"


def sentence_count(text):
    # Decimal/version dots and abbreviations without a following separator are not sentence ends.
    ends = list(re.finditer(r"[。！？!?]+|(?<!\d)\.(?=\s|$)|(?<=\d)\.(?=\s|$)", text))
    count = len(ends)
    tail = text[ends[-1].end():] if ends else text
    if tail.strip(' \n\t」』";；:：'):
        count += 1
    return max(count, 1) if text.strip() else 0


def binding(claim, ref, slot, field):
    is_statement = field == "statement"
    return Binding(slot=slot, claim_key=claim.claim_key, field=field, ref_id=ref.ref_id,
        start=0, end=len(ref.quote) if is_statement else 0,
        value=claim.statement if is_statement else claim.attribution.publisher_source_id)


def fact(template, claims, refs):
    rows = []
    for i, claim in enumerate(claims):
        ref = refs[claim.evidence_ref_ids[0]]
        rows.append(binding(claim, ref, "source" + str(i), "publisher_source_id"))
        if template != "attributed_headline":
            rows.append(binding(claim, ref, "quote" + str(i), "statement"))
    value = FactText(text="pending", template_id=template, claim_keys=tuple(c.claim_key for c in claims),
        bindings=tuple(rows))
    return value.model_copy(update={"text": reconstruct(value)})


def reconstruct(value):
    slots = {b.slot: b.value for b in value.bindings}
    if len(slots) != len(value.bindings):
        fail("G2_PR4_FACT_PROVENANCE_INVALID", "facts", "binding.slot")
    template = value.template_id
    if template == "attributed_headline":
        return "来源 " + slots["source0"] + " 的声明"
    pieces = ["来源 " + slots["source" + str(i)] + " 称：「" + slots["quote" + str(i)] + "」"
              for i in range(len(value.claim_keys))]
    if template == "secondary_quote":
        return "摘要材料：" + "；".join(pieces)
    if template == "lifecycle":
        return "来源生命周期记录（旧声明／当前声明）：" + "；".join(pieces)
    if template == "conflict":
        return "同一声明范围的相反报告：" + "；".join(pieces)
    return "；".join(pieces)


class RuleItemGenerator:
    def generate(self, request):
        refs = {r.ref_id: r for r in request.citations}
        assessments = {a.claim_key: a for a in request.assessments}
        summaries = []
        for claim in request.claims:
            assessment = assessments[claim.claim_key]
            summaries.append(ClaimSummary(claim_key=claim.claim_key,
                statement=fact("secondary_quote" if request.mode == "secondary" else "attributed_quote",
                               (claim,), refs), attribution=claim.attribution.publisher_source_id,
                scope=claim.scope, verification_state=assessment.verification_state,
                lifecycle=assessment.lifecycle, ref_ids=claim.evidence_ref_ids, limitations=claim.limitations))
        template = ("lifecycle" if request.mode in {"corrects", "retracts"} else
                    "conflict" if request.mode == "conflict" else
                    "secondary_quote" if request.mode == "secondary" else "attributed_quote")
        inference = None
        if request.mode == "ordinary" and any(c.claim_type == "measured_result"
                and not c.scope.unknown_dimensions for c in request.claims):
            inference = Inference(text=INFERENCE, premise_claim_keys=tuple(c.claim_key for c in request.claims),
                limitations=("conditional_inference", "not_source_fact", "not_independent_verification"))
        return GenerationDraft(headline=fact("attributed_headline", request.claims[:1], refs),
            what_happened=fact(template, request.claims, refs), why_it_matters=inference,
            claim_summaries=tuple(summaries))
