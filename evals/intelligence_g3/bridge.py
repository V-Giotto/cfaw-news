"""Pure native-object projection. No files, generators, labels or alias rewriting."""

from datetime import datetime

from evals.intelligence_g2.contracts import G2Config, data, digest
from evals.intelligence_g2.pr4.snapshots import identify
from evals.intelligence_g2.pr5.pipeline import observe as observe_expression
from evals.intelligence_g2.pr6.contracts import G3InputView
from evals.intelligence_g2.pr6.handoff import views
from evals.intelligence_g2.validate_output import checked_input
from evals.intelligence_v1.contracts import StrictModel
from evals.intelligence_v1.hashing import sha256_bytes
from evals.intelligence_v1.temporal import parse_instant, utc_instant

from .contracts import (
    DeliverySnapshot,
    G3Candidate,
    G3ReplayInput,
    InputManifest,
    Interaction,
    NativeStep,
    ParentBinding,
    PersonaSnapshot,
    PublishedItemRef,
    ReplayObservation,
    fail,
    parse,
)
from .evidence import validate_evidence
from .integrity import (
    document_index,
    validate_identity,
    validate_registered_config,
    validate_snapshots,
)

TIME_FIELDS = {"as_of", "available_at", "observed_at", "created_at", "effective_at",
               "first_extracted_as_of", "first_visible_at", "end_at", "occurred_at",
               "delivery_generated_at", "delivery_as_of", "generated_at"}


def preflight(value, cutoff):
    """Read temporal metadata before serializing even model_copy-poisoned bodies."""
    if isinstance(value, StrictModel):
        pairs = ((k, getattr(value, k)) for k in type(value).model_fields)
    elif isinstance(value, dict):
        pairs = value.items()
    elif isinstance(value, (list, tuple)):
        for child in value:
            preflight(child, cutoff)
        return
    else:
        return
    for key, child in pairs:
        if key in TIME_FIELDS and child is not None:
            instant = utc_instant(child) if isinstance(child, datetime) else parse_instant(child)
            if instant > cutoff:
                fail("G3_FUTURE_INPUT", key)
        else:
            preflight(child, cutoff)


def preflight_step(value, cutoff):
    def get(row, key):
        return row[key] if isinstance(row, dict) else getattr(row, key)

    context = get(get(value, "replay_input"), "context")
    raw = get(context, "as_of")
    local = utc_instant(raw) if isinstance(raw, datetime) else parse_instant(raw)
    if local > cutoff:
        fail("G3_FUTURE_INPUT", "step.as_of")
    preflight(value, local)


def unique(rows, key, field):
    result = {}
    for row in rows:
        identity = key(row)
        if identity in result:
            fail("G3_DUPLICATE_ID", field)
        result[identity] = row
    return result


def same(left, right, field):
    if left != right:
        fail("G3_REFERENCE_MISMATCH", field)


def check_references(value, claims, refs):
    if isinstance(value, StrictModel):
        pairs = ((k, getattr(value, k)) for k in type(value).model_fields)
    elif isinstance(value, dict):
        pairs = value.items()
    elif isinstance(value, (tuple, list)):
        for child in value:
            check_references(child, claims, refs)
        return
    else:
        return
    for key, child in pairs:
        if key == "ref_id" and child not in refs:
            fail("G3_REFERENCE_NOT_FOUND", "ref_id")
        if key in {"evidence_ref_ids", "ref_ids", "trigger_ref_ids"} and not set(child) <= refs:
            fail("G3_REFERENCE_NOT_FOUND", key)
        if key in {"claim_key", "target_claim_key", "evidence_claim_key"} and child not in claims:
            fail("G3_REFERENCE_NOT_FOUND", key)
        if (key.endswith("claim_keys") or key == "claim_order") and not set(child) <= claims:
            fail("G3_REFERENCE_NOT_FOUND", key)
        check_references(child, claims, refs)


def validate_step(step, prior, documents):
    replay, record = step.replay_input, step.record
    context, cursor = replay.context, record.grouping.cursor
    same((context.timeline_id, context.step_id, context.as_of),
         (cursor.timeline_id, cursor.step_id, cursor.as_of), "cursor")
    same(cursor.ordinal, 0 if prior is None else prior.record.grouping.cursor.ordinal + 1,
         "cursor.ordinal")
    same(cursor.previous_step_id, None if prior is None else prior.record.grouping.cursor.step_id,
         "cursor.previous_step_id")
    if prior and prior.record.grouping.cursor.as_of >= cursor.as_of:
        fail("G3_INVALID_INTERVAL", "prefix_order")
    checked_input(replay, G2Config())
    same(record.pool_sha256, digest(dict(context=data(context),
         documents=[data(d) for d in replay.visible_documents], sources=[data(s) for s in replay.sources],
         manifest=replay.input_manifest_sha256)), "pool_sha256")
    for current, old, name in (
        (record.grouping.next_state, prior.record.grouping.next_state if prior else None, "identity"),
        (record.evidence.next_state, prior.record.evidence.next_state if prior else None, "evidence"),
        (record.rule.next_state, prior.record.rule.next_state if prior else None, "rule"),
        (record.expression.next_state, prior.record.expression.next_state if prior else None, "expression"),
    ):
        same(current.cursor, cursor, name + ".cursor")
        same(current.previous_state_sha256, digest(old) if old else None, name + ".parent")
        if old:
            same(current.namespace, old.namespace, name + ".namespace")
    for stage in (record.evidence, record.rule, record.expression):
        same(stage.cursor, cursor, "stage.cursor")
    if not all(v.validation.ok for v in (record.grouping, record.evidence, record.rule)):
        fail("G3_PARENT_INVALID", "validation")
    same(record.evidence.next_state.grouping_state_sha256, digest(record.grouping.next_state),
         "evidence.grouping_state")
    members = [m for e in record.grouping.events for m in e.member_doc_version_ids]
    if len(members) != len(set(members)):
        fail("G3_DUPLICATE_ID", "event.members")
    same(set(members), set(context.candidate_doc_version_ids), "candidate_documents")
    for d in replay.visible_documents:
        candidate = d.candidate
        if candidate.doc_version_id in documents:
            same(documents[candidate.doc_version_id], d, "immutable_document")
        documents[candidate.doc_version_id] = d
    validate_identity(record.grouping.next_state, record.grouping.events,
                      document_index(documents.values()))
    evidence = record.evidence
    validate_evidence(evidence, record.grouping.next_state, document_index(documents.values()),
                      context.source_coverage, prior.record.evidence if prior else None)
    refs = unique(evidence.next_state.citations, lambda c: c.ref_id, "citation.ref_id")
    claims = unique(evidence.next_state.claims, lambda c: c.claim_key, "claim_key")
    for rows, archive, key, name in (
        (evidence.citations, refs, lambda c: c.ref_id, "current_citations"),
        (evidence.claims, claims, lambda c: c.claim_key, "current_claims"),
    ):
        unique(rows, key, name)
        for row in rows:
            same(archive.get(key(row)), row, name)
    check_references((evidence, record.rule.items, record.expression.presentations),
                     set(claims), set(refs))
    if any(a.verification_state == "independently_supported" for a in evidence.next_state.assessments):
        fail("G3_REFERENCE_MISMATCH", "independent_support")
    if prior:
        for old in prior.record.evidence.next_state.claims:
            same(claims.get(old.claim_key), old, "immutable_claim")
        for old in prior.record.evidence.next_state.citations:
            same(refs.get(old.ref_id), old, "immutable_citation")
    same(record.rule.next_state.snapshots,
         (prior.record.rule.next_state.snapshots if prior else ()) + record.rule.snapshots,
         "rule.snapshot_prefix")
    validate_snapshots(record.rule.next_state.snapshots, record.grouping.next_state)
    same(record.expression.next_state.snapshots,
         (prior.record.expression.next_state.snapshots if prior else ()) + record.expression.snapshots,
         "expression.snapshot_prefix")
    for citation in refs.values():
        doc = documents.get(citation.doc_version_id)
        if doc is None:
            fail("G3_REFERENCE_NOT_FOUND", "citation.document")
        c = doc.candidate
        same((citation.document_id, citation.source_id, citation.content_sha256,
              citation.available_at, citation.record_origin),
             (c.document_id, c.source_id, c.content_sha256, c.available_at, doc.record_origin),
             "citation.provenance")
        paragraph = next((p for p in c.paragraphs if p.paragraph_id == citation.paragraph_id), None)
        if (paragraph is None or not 0 <= citation.start < citation.end <= len(paragraph.text)
                or paragraph.text[citation.start:citation.end] != citation.quote
                or sha256_bytes(citation.quote.encode()) != citation.quote_sha256):
            fail("G3_REFERENCE_MISMATCH", "citation.span")
    for claim in claims.values():
        if not set(claim.evidence_ref_ids) <= refs.keys():
            fail("G3_REFERENCE_NOT_FOUND", "claim.evidence_ref_ids")
    events = unique(record.grouping.events, lambda e: e.event_key, "event_key")
    registry = {e.event_key: e for e in record.grouping.next_state.registry}
    for event in events.values():
        if event.event_key not in registry:
            fail("G3_REFERENCE_NOT_FOUND", "event.registry")
        same(event.lineage_ids, registry[event.event_key].lineage_ids, "event.lineage")
    bundles = unique(evidence.bundles, lambda b: b.event_key, "bundle.event_key")
    items = unique(record.rule.items, lambda i: i.event_key, "item.event_key")
    snapshots = unique(record.rule.snapshots, lambda s: s.event_key, "snapshot.event_key")
    presentations = unique(record.expression.presentations, lambda p: p.event_key, "presentation.event_key")
    expression_snapshots = unique(record.expression.snapshots, lambda s: s.event_key,
                                  "expression_snapshot.event_key")
    for collection in (bundles, items, snapshots, presentations, expression_snapshots):
        same(set(collection), set(events), "candidate_set")
    unique(record.expression.next_state.snapshots, lambda s: s.snapshot_id, "expression_snapshot_id")
    previous_expressions = prior.record.expression.next_state.snapshots if prior else ()
    for key, presentation in presentations.items():
        same(expression_snapshots[key], observe_expression(presentation, snapshots[key], previous_expressions),
             "expression_snapshot")
    pointer = step.handoff_trace_pointer or step.trace.path
    expected_views = views(record, pointer)
    actual_views = tuple(parse(G3InputView, v) for v in step.handoff)
    unique(actual_views, lambda v: v.event_key, "handoff.event_key")
    same({v.event_key: data(v) for v in actual_views},
         {v.event_key: data(v) for v in expected_views}, "handoff")
    for key, event in events.items():
        bundle, item = bundles[key], items[key]
        same(bundle.current_doc_version_ids, event.member_doc_version_ids, "bundle.members")
        sha = digest({k: v for k, v in data(bundle).items() if k not in {"bundle_id", "bundle_sha256"}})
        same((bundle.bundle_id, bundle.bundle_sha256), ("g2:bundle:" + sha, sha), "bundle.digest")
        same(item, identify(item), "item.digest")
        if not set(bundle.current_claim_keys + bundle.historical_claim_keys) <= claims.keys():
            fail("G3_REFERENCE_NOT_FOUND", "bundle.claim_keys")
        if not set(item.evidence_ref_ids) <= refs.keys():
            fail("G3_REFERENCE_NOT_FOUND", "item.evidence_ref_ids")
        allowed = set(bundle.current_claim_keys + bundle.historical_claim_keys)
        if not set(item.selected_claim_keys + item.omitted_claim_keys) <= allowed:
            fail("G3_REFERENCE_MISMATCH", "item.event_claims")
        policies = {p.source_id: p for p in replay.sources}
        for source_pointer in item.source_pointers:
            doc = documents.get(source_pointer.doc_version_id)
            if doc is None:
                fail("G3_REFERENCE_NOT_FOUND", "source_pointer")
            for name in ("document_id", "source_id", "canonical_url", "available_at",
                         "content_sha256", "content_kind"):
                same(getattr(source_pointer, name), getattr(doc.candidate, name), "source_pointer." + name)
            for name in ("record_origin", "redistribution_rights", "provenance_uri"):
                same(getattr(source_pointer, name), getattr(doc, name), "source_pointer." + name)
            same(source_pointer.policy, policies.get(source_pointer.source_id), "source_pointer.policy")
        same(item.source_coverage, context.source_coverage, "source_coverage")
    return tuple(G3Candidate(event=events[v.event_key], bundle=bundles[v.event_key],
        rule_item=items[v.event_key], presentation=presentations[v.event_key],
        snapshot=snapshots[v.event_key], trace=step.trace, trace_pointer=pointer,
        g2_view_sha256=digest(v))
        for v in sorted(actual_views, key=lambda v: v.event_key))


def adapt(*, manifest, binding, steps, personas, history, deliveries, diagnostic):
    """All supplied steps/personas/interactions must be visible; nothing is silently dropped."""
    manifest, binding = parse(InputManifest, manifest), parse(ParentBinding, binding)
    same((binding.kind, binding.acceptance, binding.campaign, binding.fixture, binding.job_id,
          binding.config_file_sha256),
         (manifest.kind, manifest.acceptance, manifest.campaign, manifest.fixture, manifest.job_id,
          manifest.config.sha256), "manifest_binding")
    validate_registered_config(binding)
    for value in (*steps, *personas, *history, *deliveries):
        preflight(value, manifest.as_of)
    for step in steps:
        preflight_step(step, manifest.as_of)
    steps = tuple(parse(NativeStep, s) for s in steps)
    personas = tuple(parse(PersonaSnapshot, p) for p in personas)
    history = tuple(parse(Interaction, h) for h in history)
    deliveries = tuple(parse(DeliverySnapshot, d) for d in deliveries)
    by_persona = unique(personas, lambda p: p.persona.persona_version_id, "persona_version_id")
    if manifest.persona_version_id not in by_persona:
        fail("G3_REFERENCE_NOT_FOUND", "persona_version_id")
    persona = by_persona[manifest.persona_version_id]
    own = [p for p in personas if p.persona.persona_id == persona.persona.persona_id]
    unique(own, lambda p: p.persona.available_at, "persona.available_at")
    same(persona, max(own, key=lambda p: p.persona.available_at), "latest_persona")
    if not steps:
        fail("G3_REFERENCE_NOT_FOUND", "step")
    unique(steps, lambda s: s.record.grouping.cursor.step_id, "step_id")
    documents, targets, candidates, prior, observations = {}, [], (), None, []
    for step in steps:
        same(step.record.grouping.cursor.timeline_id, manifest.timeline_id, "timeline_id")
        candidates = validate_step(step, prior, documents)
        observations.append(ReplayObservation(identity_state=step.record.grouping.next_state,
            evidence=step.record.evidence, candidates=candidates,
            source_coverage=step.replay_input.context.source_coverage,
            source_coverage_digest=step.replay_input.source_coverage_digest))
        for c in candidates:
            targets.append(PublishedItemRef(event_key=c.event.event_key,
                event_revision=c.event.event_revision, item_id=c.rule_item.item_id,
                snapshot_id=c.snapshot.snapshot_id, as_of=c.snapshot.as_of))
        prior = step
    cursor, replay = prior.record.grouping.cursor, prior.replay_input
    same((cursor.step_id, cursor.as_of), (manifest.step_id, manifest.as_of), "selected_step")
    same(binding.pool_sha256, prior.record.pool_sha256, "binding.pool")
    same(binding.g2_input_manifest_sha256, replay.input_manifest_sha256, "binding.g2_manifest")
    unique(history, lambda h: h.interaction_id, "interaction_id")
    by_snapshot = unique(targets, lambda t: t.snapshot_id, "snapshot_id")
    by_delivery = unique(deliveries, lambda d: d.delivery.delivery_id, "delivery_id")
    for delivery in deliveries:
        same(delivery.persona_id, persona.persona.persona_id, "delivery.persona_id")
        for ref in delivery.items:
            if ref.snapshot_id not in by_snapshot:
                fail("G3_REFERENCE_NOT_FOUND", "delivery.target")
            same(ref, by_snapshot[ref.snapshot_id], "delivery.target")
    for h in history:
        if h.persona_id != persona.persona.persona_id:
            fail("G3_REFERENCE_MISMATCH", "history.persona_id")
        if h.target.snapshot_id not in by_snapshot:
            fail("G3_REFERENCE_NOT_FOUND", "history.target")
        same(h.target, by_snapshot[h.target.snapshot_id], "history.target")
        if h.delivery_id not in by_delivery:
            fail("G3_REFERENCE_NOT_FOUND", "history.delivery_id")
        delivery = by_delivery[h.delivery_id]
        if h.target not in delivery.items or h.occurred_at < delivery.delivery.generated_at:
            fail("G3_REFERENCE_MISMATCH", "history.delivery")
    context = replay.context
    return G3ReplayInput(parent=binding, timeline_id=manifest.timeline_id,
        step_id=manifest.step_id, as_of=manifest.as_of, persona=persona,
        deliveries=tuple(sorted(deliveries, key=lambda d: d.delivery.delivery_id)),
        history=tuple(sorted(history, key=lambda h: (h.available_at, h.interaction_id))),
        attention_budget_seconds=manifest.attention_budget_seconds,
        time_window_start=context.time_window_start, time_window_end=context.time_window_end,
        source_coverage=context.source_coverage, candidates=candidates,
        identity_state=prior.record.grouping.next_state, evidence=prior.record.evidence,
        published_refs=tuple(targets),
        document_archive=tuple(v for _, v in sorted(document_index(documents.values()).items())),
        item_snapshots=prior.record.rule.next_state.snapshots, observations=tuple(observations), diagnostic=diagnostic)
