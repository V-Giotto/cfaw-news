"""Pure cross-object validation. No paths are opened, and reference answers are never used."""

from datetime import datetime
from urllib.parse import urlsplit

from evals.intelligence_v1.exceptions import ContractError
from evals.intelligence_v1.hashing import content_sha256, sha256_bytes
from evals.intelligence_v1.provenance import https_host
from evals.intelligence_v1.temporal import (
    parse_instant,
    require_visible_version,
    utc_instant,
    version_chains,
)

from .contracts import (
    DiagnosticReport,
    G2Config,
    G2Error,
    G2ReplayInput,
    G2Result,
    PredictedRelation,
    data,
    digest,
    parse,
)
from .event_identity import event_key, event_revision


def fail(code, stage, field, record_id=""):
    raise G2Error(code, stage=stage, field=field, record_id=record_id)


def unique(rows, key, *, field, stage="bridge"):
    result = {}
    for row in rows:
        value = key(row)
        if value in result:
            fail("DUPLICATE_ID", stage, field, str(value))
        result[value] = row
    return result


def check_permissions(document, source):
    candidate = document.candidate
    key = candidate.doc_version_id
    if candidate.source_type != source.source_type:
        fail("SOURCE_TYPE_MISMATCH", "bridge", "candidate.source_type", key)
    if document.record_origin != source.record_origin:
        fail("ORIGIN_MISMATCH", "bridge", "record_origin", key)
    rights = document.redistribution_rights
    source_rights = source.redistribution_rights
    has_body = bool(candidate.text_excerpt or candidate.paragraphs)
    if document.record_origin == "synthetic":
        try:
            url = urlsplit(candidate.canonical_url or "")
        except ValueError:
            fail("PROVENANCE_INVALID", "bridge", "candidate.canonical_url", key)
        if (rights != "synthetic" or source_rights != "synthetic"
                or candidate.content_kind != "synthetic_text" or url.scheme != "synthetic"
                or not url.netloc):
            fail("ORIGIN_MISMATCH", "bridge", "redistribution_rights", key)
        if has_body and "fulltext" not in source.allowed_use:
            fail("RIGHTS_USE_NOT_ALLOWED", "bridge", "allowed_use", key)
        # Provenance was controlled-path checked in the bridge. Check syntax here without IO.
        uri = document.provenance_uri
        if (uri.startswith(("/", "\\")) or ":" in uri or "\\" in uri
                or any(p.casefold() in {"", ".", "..", ".local", ".git", "dev-diaries"}
                       or p.casefold().startswith(".env") for p in uri.split("/"))):
            fail("PROVENANCE_INVALID", "bridge", "provenance_uri", key)
        return
    if "synthetic" in {rights, source_rights} or candidate.content_kind == "synthetic_text":
        fail("ORIGIN_MISMATCH", "bridge", "redistribution_rights", key)
    try:
        https_host(document.provenance_uri)
        https_host(candidate.canonical_url or "")
    except ContractError as error:
        fail(error.code, "bridge", "provenance_uri", key)
    if source_rights in {"unknown", "metadata_only"} and set(source.allowed_use) != {"metadata"}:
        fail("RIGHTS_USE_NOT_ALLOWED", "bridge", "allowed_use", key)
    allowed = {"unknown": {"unknown", "metadata_only"},
               "metadata_only": {"metadata_only", "unknown"},
               "excerpt_only": {"excerpt_only", "metadata_only", "unknown"},
               "permitted": {"permitted", "excerpt_only", "metadata_only", "unknown"}}
    if rights not in allowed[source_rights]:
        fail("RIGHTS_USE_NOT_ALLOWED", "bridge", "redistribution_rights", key)
    if has_body and "unknown" in {rights, source_rights}:
        fail("RIGHTS_UNKNOWN_FULLTEXT", "bridge", "redistribution_rights", key)
    if not has_body:
        if "metadata" not in source.allowed_use:
            fail("SOURCE_NOT_ALLOWED", "bridge", "allowed_use", key)
    elif "metadata_only" in {rights, source_rights}:
        fail("RIGHTS_USE_NOT_ALLOWED", "bridge", "redistribution_rights", key)
    elif "excerpt_only" in {rights, source_rights}:
        count = len(candidate.text_excerpt or "") + sum(len(p.text) for p in candidate.paragraphs)
        if (candidate.content_kind != "quoted_excerpt" or "excerpt" not in source.allowed_use
                or source.max_excerpt_chars is None or count > source.max_excerpt_chars):
            fail("RIGHTS_USE_NOT_ALLOWED", "bridge", "max_excerpt_chars", key)
    elif "fulltext" not in source.allowed_use:
        fail("RIGHTS_USE_NOT_ALLOWED", "bridge", "allowed_use", key)


def preflight_time(value):
    """Inspect only temporal/identity metadata before any nested payload serialization."""
    def get(record, name, default=None):
        return record.get(name, default) if isinstance(record, dict) else getattr(record, name, default)

    def instant(raw, field):
        try:
            return utc_instant(raw) if isinstance(raw, datetime) else parse_instant(raw)
        except ContractError as error:
            fail(error.code, "bridge", field)

    context = get(value, "context")
    cutoff_raw = get(context, "as_of")
    if cutoff_raw is None:
        return  # The strict schema reports missing/wrong-shaped fields next.
    cutoff = instant(cutoff_raw, "context.as_of")
    persona = get(context, "persona")
    available = get(persona, "available_at")
    if available is not None and instant(available, "context.persona.available_at") > cutoff:
        fail("FUTURE_PERSONA", "bridge", "context.persona.available_at")
    for collection, fields, code in (
            ("exposure_history", ("occurred_at",), "FUTURE_EXPOSURE"),
            ("source_coverage", ("observed_at", "end_at"), "FUTURE_COVERAGE"),
            ("delivery_history", ("delivery_generated_at", "delivery_as_of"), "FUTURE_DELIVERY")):
        records = get(context, collection, ())
        if not isinstance(records, (list, tuple)):
            continue
        for record in records:
            for field in fields:
                raw = get(record, field)
                if raw is not None and instant(raw, "context." + collection + "." + field) > cutoff:
                    fail(code, "bridge", "context." + collection + "." + field)
    documents = get(value, "visible_documents", ())
    if isinstance(documents, (list, tuple)):
        for document in documents:
            candidate = get(document, "candidate")
            available = get(candidate, "available_at")
            if available is not None and instant(available, "candidate.available_at") > cutoff:
                fail("FUTURE_VERSION", "bridge", "candidate.available_at",
                     str(get(candidate, "doc_version_id", "")))


def checked_input(replay_input, config):
    preflight_time(replay_input)
    config = parse(G2Config, config, stage="bridge")
    value = parse(G2ReplayInput, replay_input, stage="bridge")
    context = value.context
    if value.config_sha256 != digest(config) or value.pipeline_revision != config.pipeline_revision:
        fail("CONFIG_NOT_PINNED", "bridge", "config_sha256")
    sources = unique(value.sources, lambda s: s.source_id, field="sources")
    documents = unique(value.visible_documents, lambda d: d.candidate.doc_version_id,
                       field="visible_documents")
    ids = context.candidate_doc_version_ids
    if set(ids) != set(documents):
        fail("VISIBLE_SET_MISMATCH", "bridge", "context.candidate_doc_version_ids")
    unique(value.visible_documents, lambda d: d.candidate.document_id,
           field="visible_documents.document_id")
    seeds = unique(value.identity_seeds, lambda s: s.document_id, field="identity_seeds")
    if set(seeds) != {d.candidate.document_id for d in documents.values()}:
        fail("G2_IDENTITY_SEED_INVALID", "identity", "identity_seeds")
    for document in documents.values():
        candidate = document.candidate
        key = candidate.doc_version_id
        try:
            require_visible_version(candidate, as_of=context.as_of)
        except ContractError as error:
            fail(error.code, "bridge", "candidate.available_at", key)
        if candidate.available_at < candidate.observed_at:
            fail("AVAILABLE_BEFORE_OBSERVED", "bridge", "candidate.available_at", key)
        unique(candidate.paragraphs, lambda p: p.paragraph_id, field="candidate.paragraphs")
        if content_sha256(candidate.title, candidate.text_excerpt, candidate.paragraphs) != (
                candidate.content_sha256):
            fail("SHA_MISMATCH", "bridge", "candidate.content_sha256", key)
        if candidate.source_id not in sources:
            fail("SOURCE_NOT_FOUND", "bridge", "candidate.source_id", key)
        check_permissions(document, sources[candidate.source_id])
        lineage = document.visible_lineage
        if any(v.document_id != candidate.document_id or v.available_at > context.as_of
               for v in lineage):
            fail("G2_IDENTITY_SEED_INVALID", "identity", "visible_lineage", key)
        try:
            chain = version_chains(lineage)[candidate.document_id]
        except (ContractError, KeyError):
            fail("G2_IDENTITY_SEED_INVALID", "identity", "visible_lineage", key)
        seed = seeds[candidate.document_id]
        if (seed.anchor_doc_version_id != chain[0].doc_version_id
                or seed.first_visible_at != chain[0].available_at):
            fail("G2_IDENTITY_SEED_INVALID", "identity", "identity_seeds", key)
        if (chain[-1].doc_version_id != key
                or chain[-1].content_sha256 != candidate.content_sha256
                or chain[-1].available_at != candidate.available_at):
            fail("VISIBLE_SET_MISMATCH", "bridge", "visible_lineage", key)
    for window in context.source_coverage:
        if window.source_id not in sources:
            fail("SOURCE_NOT_FOUND", "bridge", "context.source_coverage", window.source_id)
    if value.source_coverage_digest != digest([data(w) for w in context.source_coverage]):
        fail("SHA_MISMATCH", "bridge", "source_coverage_digest")
    # Normalize order without repairing duplicates or an incomplete candidate set.
    return value.model_copy(update={
        "visible_documents": tuple(documents[key] for key in ids),
        "sources": tuple(sources[key] for key in sorted(sources)),
        "identity_seeds": tuple(seeds[key] for key in sorted(seeds)),
    }), config


def coverage_gaps(context):
    if not context.source_coverage:
        return ("coverage_unknown",)
    return tuple(sorted(f"coverage:{w.coverage_window_id}:{w.status}"
                        for w in context.source_coverage if w.status != "covered"))


def validate_relation(relation, replay_input):
    relation = parse(PredictedRelation, relation, stage="identity")
    ids = set(replay_input.context.candidate_doc_version_ids)
    if not {relation.left_doc_version_id, relation.right_doc_version_id} <= ids:
        fail("GROUP_MEMBERS_INVALID", "identity", "relation.doc_version_ids")
    if relation.as_of != replay_input.context.as_of:
        fail("G2_CONTEXT_MISMATCH", "identity", "relation.as_of")
    return relation


def check_ref(ref, event, documents, config):
    key = ref.doc_version_id
    if key not in documents:
        fail("CITATION_NOT_FOUND", "evidence", "doc_version_id", key)
    if key not in event.member_doc_version_ids:
        fail("G2_EVIDENCE_NOT_IN_EVENT", "evidence", "doc_version_id", key)
    paragraphs = {p.paragraph_id: p for p in documents[key].candidate.paragraphs}
    if ref.paragraph_id not in paragraphs:
        fail("CITATION_NOT_FOUND", "evidence", "paragraph_id", key)
    if (not paragraphs[ref.paragraph_id].text.startswith(ref.quote)
            or len(ref.quote) > config.max_quote_chars
            or ref.quote_sha256 != sha256_bytes(ref.quote.encode("utf-8"))):
        fail("G2_QUOTE_MISMATCH", "evidence", "quote", key)
    if ref.direction != "mentions":
        fail("G2_PLACEHOLDER_STATUS_INVALID", "evidence", "direction", key)


def bundle_digest(bundle):
    return digest({k: v for k, v in data(bundle).items() if k not in {"bundle_id", "bundle_sha256"}})


def item_digest(item):
    return digest({k: v for k, v in data(item).items() if k not in {"item_id", "content_revision"}})


def item_key(item):
    return "g2:item:" + digest({"event_key": item.event_key,
                                "content_revision": item.content_revision,
                                "schema_revision": item.schema_revision})


def run_key(value, config):
    return "g2:run:" + digest({"input_sha256": digest(value), "config_sha256": digest(config),
                               "pipeline_revision": config.pipeline_revision})


def validate_output(result, replay_input, config):
    """Reject an entire result on any invalid member/reference/text/hash; never partly publish."""
    value, config = checked_input(replay_input, config)
    result = parse(G2Result, result, stage="output")
    context = value.context
    if ((result.timeline_id, result.step_id, result.as_of) != (
            context.timeline_id, context.step_id, context.as_of)
            or result.input_sha256 != digest(value) or result.run_id != run_key(value, config)):
        fail("G2_CONTEXT_MISMATCH", "output", "result.context")
    documents = {d.candidate.doc_version_id: d for d in value.visible_documents}
    events = unique(result.events, lambda e: e.event_key, field="events", stage="identity")
    members = [m for e in result.events for m in e.member_doc_version_ids]
    if len(members) != len(set(members)) or set(members) != set(documents):
        fail("GROUP_MEMBERS_INVALID", "identity", "member_doc_version_ids")
    seeds = {s.document_id: s for s in value.identity_seeds}
    for event in result.events:
        if len(event.member_doc_version_ids) != 1:
            fail("GROUP_MEMBERS_INVALID", "identity", "member_doc_version_ids", event.event_key)
        candidate = documents[event.member_doc_version_ids[0]].candidate
        seed = seeds[candidate.document_id]
        if (event.event_key != event_key(value, candidate.document_id, config.identity_revision)
                or event.anchor_doc_version_id != seed.anchor_doc_version_id
                or event.first_visible_at != seed.first_visible_at
                or event.event_revision != event_revision(event.event_key, candidate)):
            fail("G2_IDENTITY_SEED_INVALID", "identity", "event_key", event.event_key)
        if (event.canonical_subject is not None or event.related_event_keys
                or event.previous_identity_key is not None or event.identity_conflict is not None
                or event.merge_lineage):
            fail("G2_PLACEHOLDER_STATUS_INVALID", "identity", "lineage", event.event_key)
    if result.relations:
        for relation in result.relations:
            validate_relation(relation, value)
        fail("G2_PLACEHOLDER_STATUS_INVALID", "identity", "relations")
    bundles = unique(result.bundles, lambda b: b.event_key, field="bundles", stage="evidence")
    items = unique(result.items, lambda i: i.event_key, field="items", stage="item")
    if set(bundles) != set(events) or set(items) != set(events):
        fail("GROUP_MEMBERS_INVALID", "output", "event_bundle_item_coverage")
    unique(result.bundles, lambda b: b.bundle_id, field="bundle_id", stage="evidence")
    unique(result.items, lambda i: i.item_id, field="item_id", stage="item")
    unique([c for b in result.bundles for c in b.claim_candidates], lambda c: c.claim_key,
           field="claim_key", stage="evidence")
    gaps = coverage_gaps(context)
    for key, event in events.items():
        bundle, item = bundles[key], items[key]
        document = documents[event.member_doc_version_ids[0]]
        candidate = document.candidate
        if bundle.doc_version_ids != event.member_doc_version_ids:
            fail("GROUP_MEMBERS_INVALID", "evidence", "doc_version_ids", key)
        if bundle.as_of != context.as_of or item.as_of != context.as_of:
            fail("G2_CONTEXT_MISMATCH", "output", "as_of", key)
        if bundle.supporting_refs or bundle.refuting_refs:
            fail("G2_PLACEHOLDER_STATUS_INVALID", "evidence", "supporting_refs", key)
        for ref in (*bundle.unverified_refs, *item.evidence_refs,
                    *(r for c in bundle.claim_candidates for r in c.evidence_refs)):
            check_ref(ref, event, documents, config)
        if len(bundle.claim_candidates) > 1:
            fail("G2_PLACEHOLDER_STATUS_INVALID", "evidence", "claim_candidates", key)
        refs = tuple(r for c in bundle.claim_candidates for r in c.evidence_refs)
        expected_quote = (candidate.paragraphs[0].text[:config.max_quote_chars]
                          if candidate.paragraphs else "")
        if bool(refs) != bool(expected_quote.strip()):
            fail("G2_QUOTE_MISMATCH", "evidence", "claim_candidates", key)
        for claim in bundle.claim_candidates:
            if (len(claim.evidence_refs) != 1 or claim.statement != claim.evidence_refs[0].quote):
                fail("G2_QUOTE_MISMATCH", "evidence", "statement", claim.claim_key)
            if claim.event_key != key or claim.asserted_by != candidate.source_id:
                fail("G2_EVIDENCE_NOT_IN_EVENT", "evidence", "asserted_by", claim.claim_key)
            if (claim.evidence_refs[0].paragraph_id != candidate.paragraphs[0].paragraph_id
                    or claim.statement != expected_quote):
                fail("G2_QUOTE_MISMATCH", "evidence", "statement", claim.claim_key)
            limits = ("semantic_support_not_evaluated", "scope_unknown")
            if len(candidate.paragraphs[0].text) > config.max_quote_chars:
                limits += ("excerpt_truncated",)
            if claim.limitations != limits:
                fail("G2_PLACEHOLDER_STATUS_INVALID", "evidence", "limitations", claim.claim_key)
            expected = "g2:claim:" + digest({"event_key": key, "refs": [data(r) for r in
                claim.evidence_refs], "extractor_revision": claim.extractor_revision})
            if claim.claim_key != expected:
                fail("SHA_MISMATCH", "evidence", "claim_key", claim.claim_key)
        if refs != bundle.unverified_refs or refs != item.evidence_refs:
            fail("G2_EVIDENCE_NOT_IN_EVENT", "evidence", "unverified_refs", key)
        expected_lineage = [{"doc_version_id": candidate.doc_version_id,
                             "source_id": candidate.source_id,
                             "upstream_document_id": candidate.upstream_document_id,
                             "independence": "unknown"}]
        if [data(s) for s in bundle.source_lineage] != expected_lineage:
            fail("G2_PLACEHOLDER_STATUS_INVALID", "evidence", "source_lineage", key)
        uncertainties = ("pr1_placeholder", "semantic_support_not_evaluated", "observed_sources_only")
        if not refs:
            uncertainties += ("no_citable_paragraph",)
        if bundle.coverage_gaps != gaps or bundle.uncertainties != uncertainties:
            fail("G2_CONTEXT_MISMATCH", "evidence", "coverage_gaps", key)
        if bundle.bundle_sha256 != bundle_digest(bundle) or bundle.bundle_id != (
                "g2:bundle:" + bundle.bundle_sha256):
            fail("SHA_MISMATCH", "evidence", "bundle_sha256", key)
        if (item.bundle_id != bundle.bundle_id or item.event_revision != event.event_revision
                or item.claim_keys != tuple(c.claim_key for c in bundle.claim_candidates)):
            fail("G2_EVIDENCE_NOT_IN_EVENT", "item", "bundle_id", key)
        expected_fact = "来源段落摘录：" + refs[0].quote if refs else None
        if item.what_happened != expected_fact:
            fail("G2_QUOTE_MISMATCH", "item", "what_happened", key)
        if (item.headline != "来源材料：" + candidate.title or item.why_it_matters is not None
                or item.evidence_status != ("attributed" if refs else "insufficient")
                or item.uncertainties != uncertainties):
            fail("G2_PLACEHOLDER_STATUS_INVALID", "item", "evidence_status", key)
        if item.record_origin != document.record_origin:
            fail("ORIGIN_MISMATCH", "item", "record_origin", key)
        if item.source_coverage != context.source_coverage:
            fail("G2_CONTEXT_MISMATCH", "item", "source_coverage", key)
        if item.content_revision != item_digest(item) or item.item_id != item_key(item):
            fail("SHA_MISMATCH", "item", "content_revision", key)
    counts = {"candidates": len(documents), "events": len(events), "bundles": len(bundles),
              "items": len(items), "relations": 0,
              "claims": sum(len(b.claim_candidates) for b in result.bundles),
              "coverage_gaps": len(gaps)}
    report = DiagnosticReport(ok=True, counts=counts, coverage_gaps=gaps)
    if result.validation != report:
        fail("G2_CONTEXT_MISMATCH", "output", "validation")
    return report
