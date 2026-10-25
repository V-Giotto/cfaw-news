"""Pure PR1 vertical slice: singleton events, source excerpts and hold items."""

from evals.intelligence_v1.hashing import sha256_bytes

from .contracts import (
    ClaimCandidate,
    DiagnosticReport,
    EvidenceBundle,
    EvidenceRef,
    G2Config,
    G2ReplayInput,
    G2Result,
    IntelligenceItem,
    SourceLineage,
    data,
    digest,
)
from .event_identity import build_events
from .validate_output import (
    bundle_digest,
    checked_input,
    coverage_gaps,
    item_digest,
    item_key,
    run_key,
    validate_output,
)


def run_g2_offline(*, replay_input: G2ReplayInput, config: G2Config) -> G2Result:
    value, config = checked_input(replay_input, config)
    context = value.context
    events = build_events(value, config)
    documents = {d.candidate.doc_version_id: d for d in value.visible_documents}
    bundles, items = [], []
    gaps = coverage_gaps(context)
    for event in events:
        document = documents[event.member_doc_version_ids[0]]
        candidate = document.candidate
        claims, refs = (), ()
        uncertainties = ("pr1_placeholder", "semantic_support_not_evaluated",
                         "observed_sources_only")
        if candidate.paragraphs:
            paragraph = candidate.paragraphs[0]
            quote = paragraph.text[:config.max_quote_chars]
            if quote.strip():
                ref = EvidenceRef(doc_version_id=candidate.doc_version_id,
                    paragraph_id=paragraph.paragraph_id, quote=quote,
                    quote_sha256=sha256_bytes(quote.encode("utf-8")), direction="mentions")
                refs = (ref,)
                limitations = ("semantic_support_not_evaluated", "scope_unknown")
                if len(paragraph.text) > len(quote):
                    limitations += ("excerpt_truncated",)
                claim_key = "g2:claim:" + digest({"event_key": event.event_key,
                    "refs": [data(ref)], "extractor_revision": config.claim_strategy})
                claims = (ClaimCandidate(claim_key=claim_key, event_key=event.event_key,
                    statement=quote, asserted_by=candidate.source_id, evidence_refs=refs,
                    limitations=limitations),)
        if not refs:
            uncertainties += ("no_citable_paragraph",)
        bundle = EvidenceBundle(bundle_id="pending", event_key=event.event_key,
            as_of=context.as_of, doc_version_ids=event.member_doc_version_ids,
            claim_candidates=claims, source_lineage=(SourceLineage(
                doc_version_id=candidate.doc_version_id, source_id=candidate.source_id,
                upstream_document_id=candidate.upstream_document_id),),
            unverified_refs=refs, coverage_gaps=gaps, uncertainties=uncertainties,
            bundle_sha256="0" * 64)
        bundle_sha = bundle_digest(bundle)
        bundle = bundle.model_copy(update={"bundle_sha256": bundle_sha,
                                            "bundle_id": "g2:bundle:" + bundle_sha})
        bundles.append(bundle)
        item = IntelligenceItem(item_id="pending", content_revision="0" * 64,
            event_key=event.event_key, event_revision=event.event_revision,
            bundle_id=bundle.bundle_id, as_of=context.as_of,
            headline="来源材料：" + candidate.title,
            what_happened="来源段落摘录：" + refs[0].quote if refs else None,
            claim_keys=tuple(c.claim_key for c in claims), evidence_refs=refs,
            evidence_status="attributed" if refs else "insufficient", uncertainties=uncertainties,
            source_coverage=context.source_coverage, record_origin=document.record_origin)
        item = item.model_copy(update={"content_revision": item_digest(item)})
        items.append(item.model_copy(update={"item_id": item_key(item)}))
    counts = {"candidates": len(documents), "events": len(events), "bundles": len(bundles),
              "items": len(items), "relations": 0,
              "claims": sum(len(b.claim_candidates) for b in bundles), "coverage_gaps": len(gaps)}
    result = G2Result(run_id=run_key(value, config), input_sha256=digest(value),
        timeline_id=context.timeline_id, step_id=context.step_id, as_of=context.as_of,
        relations=(), events=events, bundles=tuple(bundles), items=tuple(items),
        validation=DiagnosticReport(ok=True, counts=counts, coverage_gaps=gaps))
    validate_output(result, value, config)
    return result
