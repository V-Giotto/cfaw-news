"""Shared structural proofs for both native loading and serialized replay inputs."""

from evals.intelligence_g2.contracts import data, digest
from evals.intelligence_g2.pr2.identity import validate_graph
from evals.intelligence_g2.pr4.contracts import EventEvidenceView
from evals.intelligence_g2.pr4.snapshots import identify
from evals.intelligence_g2.pr4.validate_output import check_fact
from evals.intelligence_g2.pr5.pipeline import identify as identify_presentation
from evals.intelligence_g2.pr6.contracts import G3InputView
from evals.intelligence_v1.temporal import version_chains

from .contracts import fail
from .evidence import validate_evidence


def indexed(rows, field):
    result = {}
    for row in rows:
        key = getattr(row, field)
        if key in result:
            fail("G3_DUPLICATE_ID", field)
        result[key] = row
    return result


def equal(actual, expected, field):
    if actual != expected:
        fail("G3_REFERENCE_MISMATCH", field)


def validate_registered_config(binding):
    from .contracts import G3Config

    equal(binding.config_sha256, digest(G3Config()), "binding.config_sha256")


def document_index(documents):
    """Retain visible lineage metadata, without adding historical bodies."""
    records = {}
    for document in documents:
        for identity in document.visible_lineage:
            old = records.get(identity.doc_version_id)
            if old is not None:
                equal(old, identity, "immutable_document_identity")
            records[identity.doc_version_id] = identity
    return records


def validate_identity(state, events, documents):
    validate_graph(state)
    registry = indexed(state.registry, "event_key")
    events = indexed(events, "event_key")
    active = {key for key, r in registry.items() if r.status == "active"}
    equal(set(events), active, "active_event_set")
    chains = version_chains(documents.values())
    positions = {v.doc_version_id: n for chain in chains.values() for n, v in enumerate(chain)}
    for transition in state.transitions:
        for key in transition.trigger_doc_version_ids:
            if key not in documents:
                fail("G3_REFERENCE_NOT_FOUND", "transition.trigger_document")
            if documents[key].available_at > transition.effective_at:
                fail("G3_INVALID_INTERVAL", "transition.trigger_document")
    for key, registered in registry.items():
        anchor = documents.get(registered.anchor_doc_version_id)
        if anchor is None:
            fail("G3_REFERENCE_NOT_FOUND", "registry.anchor_document")
        if anchor.available_at > registered.created_at:
            fail("G3_INVALID_INTERVAL", "registry.anchor_created_at")
        births = [t for t in state.transitions if key in t.to_keys
                  and t.kind in {"birth", "split", "complex"}]
        if len(births) != 1 or births[0].effective_at != registered.created_at:
            fail("G3_REFERENCE_MISMATCH", "registry.created_at")
        features = indexed(registered.last_features, "doc_version_id")
        if not any(f.document_id == anchor.document_id
                   and f.doc_version_id in documents
                   and positions[f.doc_version_id] >= positions[anchor.doc_version_id]
                   for f in features.values()):
            fail("G3_REFERENCE_MISMATCH", "registry.anchor_lineage")
        for feature in features.values():
            doc = documents.get(feature.doc_version_id)
            if doc is None:
                fail("G3_REFERENCE_NOT_FOUND", "registry.feature_document")
            equal((feature.document_id, feature.available_at, feature.content_sha256),
                  (doc.document_id, doc.available_at, doc.content_sha256), "registry.feature_metadata")
            for ref in feature.refs:
                if ref.doc_version_id not in documents:
                    fail("G3_REFERENCE_NOT_FOUND", "feature.ref_document")
                # Native PR2 features may inherit refs from a visible upstream document.
                equal(ref.available_at, documents[ref.doc_version_id].available_at,
                      "feature.ref_document")
    for key, event in events.items():
        registered = registry[key]
        equal((event.anchor_doc_version_id, event.created_at, event.lineage_ids),
              (registered.anchor_doc_version_id, registered.created_at, registered.lineage_ids),
              "event.registry_identity")
        if len(event.related_event_keys) != len(set(event.related_event_keys)):
            fail("G3_DUPLICATE_ID", "related_event_keys")
        if key in event.related_event_keys or not set(event.related_event_keys) <= active:
            fail("G3_REFERENCE_NOT_FOUND", "related_event_keys")
        members = set(event.member_doc_version_ids)
        if len(members) != len(event.member_doc_version_ids):
            fail("G3_DUPLICATE_ID", "event.members")
        if not members <= documents.keys() or not members <= {f.doc_version_id for f in registered.last_features}:
            fail("G3_REFERENCE_NOT_FOUND", "event.member_document")


def validate_snapshots(snapshots, state):
    """Native PR4 identity formula and exact as-of predecessor construction."""
    indexed(snapshots, "snapshot_id")
    registry = indexed(state.registry, "event_key")
    transitions = {t.transition_id: t for t in state.transitions}
    seen, latest, last_time, event_times = {}, {}, None, set()
    for snapshot in snapshots:
        if last_time is not None and snapshot.as_of < last_time:
            fail("G3_INVALID_INTERVAL", "snapshot_order")
        last_time = snapshot.as_of
        event_time = (snapshot.event_key, snapshot.as_of)
        if event_time in event_times:
            fail("G3_DUPLICATE_ID", "snapshot.event_as_of")
        event_times.add(event_time)
        registered = registry.get(snapshot.event_key)
        if registered is None:
            fail("G3_REFERENCE_NOT_FOUND", "snapshot.event_key")
        if snapshot.as_of < registered.created_at:
            fail("G3_INVALID_INTERVAL", "snapshot.created_at")
        sha = digest(dict(item_id=snapshot.item_id, as_of=snapshot.as_of.isoformat(),
                          bundle_sha256=snapshot.bundle_sha256))
        equal(snapshot.snapshot_id, "g2:snapshot:" + sha, "snapshot_id")
        if len(snapshot.previous_snapshot_ids) != len(set(snapshot.previous_snapshot_ids)):
            fail("G3_DUPLICATE_ID", "previous_snapshot_ids")
        for parent in snapshot.previous_snapshot_ids:
            if parent == snapshot.snapshot_id or parent not in seen:
                fail("G3_REFERENCE_NOT_FOUND", "previous_snapshot_ids")
            if seen[parent].as_of >= snapshot.as_of:
                fail("G3_INVALID_INTERVAL", "previous_snapshot_ids")
        lineage = tuple(tid for tid in registered.lineage_ids
                        if transitions[tid].effective_at <= snapshot.as_of)
        equal(snapshot.lineage_ids, lineage, "snapshot.lineage_ids")
        previous = [latest[snapshot.event_key]] if snapshot.event_key in latest else []
        predecessor_keys = sorted({key for t in state.transitions
                                  if t.effective_at <= snapshot.as_of and snapshot.event_key in t.to_keys
                                  for key in t.from_keys if key != snapshot.event_key})
        previous += [latest[key] for key in predecessor_keys if key in latest]
        expected = tuple(dict.fromkeys(s.snapshot_id for s in previous))
        equal(snapshot.previous_snapshot_ids, expected, "snapshot.predecessors")
        same_event = latest.get(snapshot.event_key)
        old_lineage = set(same_event.lineage_ids) if same_event else set()
        signal = ("identity_transition" if set(snapshot.lineage_ids) - old_lineage else
                  "first_observed" if same_event is None else
                  "same_content_observed" if same_event.item_id == snapshot.item_id else "content_changed")
        equal(snapshot.change_signal, signal, "snapshot.change_signal")
        seen[snapshot.snapshot_id] = snapshot
        latest[snapshot.event_key] = snapshot
    equal(set(latest), set(registry), "snapshot_registry_set")
    for key, registered in registry.items():
        first = min(s.as_of for s in snapshots if s.event_key == key)
        equal(first, registered.created_at, "snapshot_birth_observation")
    return seen


def validate_candidate(candidate):
    """Compare native digests with the supplied bytes; never repair an identity."""
    bundle, item, presentation = candidate.bundle, candidate.rule_item, candidate.presentation
    sha = digest({k: v for k, v in data(bundle).items() if k not in {"bundle_id", "bundle_sha256"}})
    equal((bundle.bundle_id, bundle.bundle_sha256), ("g2:bundle:" + sha, sha), "bundle.digest")
    equal(item, identify(item), "item.digest")
    equal(presentation, identify_presentation(item, presentation.headline, presentation.body,
          presentation.style_id, presentation.claim_order, presentation.selection), "presentation.digest")
    view = G3InputView(event_key=item.event_key, event_revision=item.event_revision,
        as_of=candidate.snapshot.as_of.isoformat(), bundle=data(bundle), rule_item=data(item),
        presentation=data(presentation), snapshot=data(candidate.snapshot),
        source_coverage=tuple(data(w) for w in item.source_coverage),
        lineage_ids=candidate.snapshot.lineage_ids, trace_pointer=candidate.trace_pointer)
    equal(candidate.g2_view_sha256, digest(view), "g2_view_sha256")


def validate_candidate_evidence(candidate, claims, refs):
    from .bridge import check_references

    bundle, item = candidate.bundle, candidate.rule_item
    check_references((bundle, item, candidate.presentation), set(claims), set(refs))
    allowed = set(bundle.current_claim_keys + bundle.historical_claim_keys)
    if not set(item.selected_claim_keys + item.omitted_claim_keys) <= allowed:
        fail("G3_REFERENCE_MISMATCH", "item.event_claims")
    if (set(item.selected_claim_keys) & set(item.omitted_claim_keys)
            or len(item.selected_claim_keys) != len(set(item.selected_claim_keys))
            or len(item.omitted_claim_keys) != len(set(item.omitted_claim_keys))):
        fail("G3_REFERENCE_MISMATCH", "item.claim_partition")
    equal(set(item.selected_claim_keys + item.omitted_claim_keys), allowed, "item.claim_partition")
    equal(item.uncertainties, tuple(sorted(set(bundle.uncertainties))), "item.uncertainties")
    chosen = tuple(claims[k] for k in sorted(allowed))
    selected_refs = tuple(refs[k] for k in sorted({r for c in chosen for r in c.evidence_ref_ids}))
    view = EventEvidenceView(bundle=bundle, claims=chosen, citations=selected_refs, transitions=(),
        source_pointers=item.source_pointers, lineage_ids=candidate.event.lineage_ids, predecessor_event_keys=())
    for fact in (item.headline, item.what_happened) + tuple(c.statement for c in item.claim_summaries):
        if fact:
            check_fact(fact, view)


def validate_replay(value):
    """Recheck every original observation, not just mutually consistent final copies."""
    from .bridge import preflight
    from .contracts import PublishedItemRef

    validate_registered_config(value.parent)
    indexed((o.identity_state.cursor for o in value.observations), "step_id")
    documents = indexed(value.document_archive, "doc_version_id")
    expected_snapshots, expected_refs, prior = [], [], None
    for observation in value.observations:
        state, evidence = observation.identity_state, observation.evidence
        cursor = state.cursor
        if cursor.step_id == cursor.previous_step_id:
            fail("G3_REFERENCE_MISMATCH", "observation.self_reference")
        preflight(observation, cursor.as_of)
        equal((cursor.ordinal, cursor.previous_step_id, cursor.timeline_id),
              (prior.identity_state.cursor.ordinal + 1 if prior else 0,
               prior.identity_state.cursor.step_id if prior else None, value.timeline_id), "observation.cursor")
        equal(state.previous_state_sha256, digest(prior.identity_state) if prior else None, "observation.parent")
        if prior and prior.identity_state.cursor.as_of >= cursor.as_of:
            fail("G3_INVALID_INTERVAL", "observation.order")
        equal(state.input_manifest_sha256, value.parent.g2_input_manifest_sha256, "observation.input_manifest")
        equal(observation.source_coverage_digest, digest([data(w) for w in observation.source_coverage]),
              "source_coverage_digest")
        indexed(observation.source_coverage, "coverage_window_id")
        candidates = {c.event.event_key: c for c in observation.candidates}
        if len(candidates) != len(observation.candidates):
            fail("G3_DUPLICATE_ID", "observation.event_key")
        validate_identity(state, tuple(c.event for c in observation.candidates), documents)
        claims, refs = validate_evidence(evidence, state, documents, observation.source_coverage,
                                         prior.evidence if prior else None)
        bundles = indexed(evidence.bundles, "event_key")
        equal(set(candidates), set(bundles), "candidate_bundle_set")
        for key, candidate in candidates.items():
            equal(candidate.bundle, bundles[key], "candidate.bundle")
            equal(candidate.event.member_doc_version_ids, candidate.bundle.current_doc_version_ids,
                  "candidate.member_documents")
            equal(candidate.snapshot.as_of, cursor.as_of, "candidate.as_of")
            equal(candidate.rule_item.source_coverage, observation.source_coverage, "candidate.coverage")
            validate_candidate_evidence(candidate, claims, refs)
            expected_snapshots.append(candidate.snapshot)
            expected_refs.append(PublishedItemRef(event_key=key, event_revision=candidate.event.event_revision,
                item_id=candidate.rule_item.item_id, snapshot_id=candidate.snapshot.snapshot_id,
                as_of=candidate.snapshot.as_of))
        prior = observation
    equal((value.identity_state, value.evidence, value.candidates, value.source_coverage),
          (prior.identity_state, prior.evidence, prior.candidates, prior.source_coverage), "current_observation")
    equal((value.step_id, value.as_of), (prior.identity_state.cursor.step_id, prior.identity_state.cursor.as_of),
          "selected_observation")
    equal(value.item_snapshots, tuple(expected_snapshots), "snapshot_observations")
    validate_snapshots(value.item_snapshots, value.identity_state)
    equal(value.published_refs, tuple(expected_refs), "published_observations")
