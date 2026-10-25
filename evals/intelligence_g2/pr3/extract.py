"""Full paragraphs only. No generated facts, sentence truncation or reference access."""

import re
from collections import Counter

from evals.intelligence_g2.validate_output import preflight_time
from evals.intelligence_v1.hashing import sha256_bytes

from .contracts import (
    Citation,
    ClaimCandidate,
    CoverageGap,
    ExtractionResult,
    SourceAttribution,
    data,
    digest,
    fail,
)
from .scope import grounded, parse_fields

CUE = re.compile(r"\breleas|\bclaims?\b|\breports?\b|\btest|\bmeasur|\bcompatib|\bplugin|"
    r"\bconstraint|\brisk|\bvulnerab|\bunsafe|\bcorrect|\bwithdraw|\bretract|\blimited|"
    r"\btable|\bprovides|宣称|报告|发布|提升|风险|更正|撤回|仅限", re.I)
SENSITIVE = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----|"
    r"\b(?:api[_ -]?key|password|access[_ -]?token|secret)\s*[:=]\s*\S{8,}", re.I)


def citation_key(ref):
    return "g2:ref:" + digest({k: v for k, v in data(ref).items() if k != "ref_id"})


def claim_key(doc, ref, config, dataset_id):
    return "g2:claim:" + digest(dict(dataset_id=dataset_id, doc_version_id=doc.doc_version_id,
        paragraph_id=ref.paragraph_id, quote_sha256=ref.quote_sha256,
        extractor_revision=config.extractor_revision, scope_revision=config.scope_revision))


def kind(text):
    if re.search(r"table.*(?:omitted|missing|unavailable)", text, re.I):
        return "constraint"
    if re.search(r"speed gain|speed improvement|speedup|速度提升|速度未提升|correction|withdraw|retract|更正|撤回", text, re.I):
        return "measured_result"
    if re.search(r"\brisk|\bvulnerab|unsafe|风险", text, re.I):
        return "risk"
    if re.search(r"limited to|only.*tested|constraint|仅限", text, re.I):
        return "constraint"
    if re.search(r"\breleas|发布", text, re.I):
        return "release_fact"
    if re.search(r"\bcapabil|\bcompatib|\boffers|\bprovides|\bplugin|支持|能够", text, re.I):
        return "capability_claim"
    return "other"


def extract_claims(*, replay_input, events, config):
    preflight_time(replay_input)
    owner = {m: e.event_key for e in events for m in e.member_doc_version_ids}
    sources = {s.source_id: s for s in replay_input.sources}
    claims, refs, gaps = [], [], []
    by_event = Counter()
    for wrapped in replay_input.visible_documents:
        doc = wrapped.candidate
        source = sources[doc.source_id]
        if not doc.paragraphs:
            gaps.append(CoverageGap(code="no_citable_paragraph", source_id=doc.source_id,
                                    doc_version_id=doc.doc_version_id))
        count = 0
        for paragraph in doc.paragraphs:
            text = paragraph.text
            if SENSITIVE.search(text):
                gaps.append(CoverageGap(code="sensitive_text_excluded", source_id=doc.source_id,
                                        doc_version_id=doc.doc_version_id))
                continue
            maximum = min(config.max_quote_chars, source.max_excerpt_chars or config.max_quote_chars)
            if len(text) > maximum:
                gaps.append(CoverageGap(code="whole_paragraph_quote_limit", source_id=doc.source_id,
                                        doc_version_id=doc.doc_version_id))
                continue
            if not CUE.search(text):
                gaps.append(CoverageGap(code="unsupported_grammar", source_id=doc.source_id,
                                        doc_version_id=doc.doc_version_id))
                continue
            if re.search(r"table.*(?:omitted|missing|unavailable)|表格.*(?:丢失|缺失|省略)", text, re.I):
                gaps.append(CoverageGap(code="table_unavailable", source_id=doc.source_id,
                                        doc_version_id=doc.doc_version_id))
            if doc.content_kind in {"publisher_text", "quoted_excerpt"}:
                gaps.append(CoverageGap(code="cleaning_completeness_unknown", source_id=doc.source_id,
                                        doc_version_id=doc.doc_version_id))
            ref = Citation(ref_id="pending", doc_version_id=doc.doc_version_id,
                document_id=doc.document_id, paragraph_id=paragraph.paragraph_id, start=0, end=len(text),
                quote=text, quote_sha256=sha256_bytes(text.encode()), source_id=doc.source_id,
                available_at=doc.available_at, content_sha256=doc.content_sha256,
                record_origin=wrapped.record_origin)
            ref = ref.model_copy(update={"ref_id": citation_key(ref)})
            scope, proposition, marker = parse_fields(ref)
            secondary = doc.content_kind in {"feed_summary", "archive_authored"}
            attributed = re.search(r"(?:according to|据|转述)\s*([^.;。\n]+)", text, re.I)
            attribution = SourceAttribution(publisher_source_id=doc.source_id,
                asserted_by_source_id=None if secondary or attributed else doc.source_id,
                asserted_by_text=grounded(ref, *attributed.span(1)) if attributed else None,
                attribution_kind="secondary_material" if secondary else "reported_speech" if attributed
                                 else "publisher_statement")
            limitations = ["semantic_truth_not_evaluated", "independence_unknown"]
            if scope.unknown_dimensions:
                limitations.append("scope_incomplete")
            if proposition.ambiguous:
                limitations.append("ambiguous_proposition")
            if secondary:
                proposition = proposition.model_copy(update={"quantities": (), "polarity": "unknown", "ambiguous": True})
                limitations.append("primary_text_unavailable")
                gaps.append(CoverageGap(code="primary_text_unavailable", source_id=doc.source_id,
                                        doc_version_id=doc.doc_version_id))
            if re.search(r"independent|独立", text, re.I):
                limitations.append("independence_statement_not_verified")
            claim = ClaimCandidate(claim_key=claim_key(doc, ref, config, replay_input.dataset_id),
                origin_event_key=owner[doc.doc_version_id], first_extracted_as_of=replay_input.context.as_of,
                doc_version_id=doc.doc_version_id, statement=text,
                claim_type="other" if secondary else kind(text), attribution=attribution, scope=scope,
                proposition=proposition, evidence_ref_ids=(ref.ref_id,), limitations=tuple(limitations),
                record_origin=wrapped.record_origin, marker="none" if secondary else marker)
            refs.append(ref)
            claims.append(claim)
            count += 1
            by_event[owner[doc.doc_version_id]] += 1
            if count > config.max_claims_per_document:
                fail("G2_PR3_BUDGET_EXCEEDED", "extract", "claims_per_document", doc.doc_version_id)
            if by_event[owner[doc.doc_version_id]] > config.max_claims_per_event:
                fail("G2_PR3_BUDGET_EXCEEDED", "extract", "claims_per_event", owner[doc.doc_version_id])
    return ExtractionResult(claims=tuple(sorted(claims, key=lambda c: c.claim_key)),
        citations=tuple(sorted(refs, key=lambda r: r.ref_id)), coverage_gaps=tuple(gaps))
