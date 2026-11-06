"""Ledger projection into unchanged, checked native G2 stages. No claims are authored here."""

from collections import defaultdict
from datetime import datetime, timezone

from evals.intelligence_g2.contracts import (
    G2Config,
    G2ReplayInput,
    G2SourcePolicy,
    G2VisibleDocument,
    IdentitySeed,
    VersionIdentity,
    checked_relative_path,
    data,
    digest,
    json_bytes,
)
from evals.intelligence_g2.pr2.contracts import GroupingInput, PR2Config, ReplayCursor
from evals.intelligence_g2.pr2.pipeline import run_grouping_step
from evals.intelligence_g2.pr3.contracts import EvidenceInput, PR3Config
from evals.intelligence_g2.pr3.pipeline import run_evidence_step
from evals.intelligence_g2.pr4.contracts import PR4Config
from evals.intelligence_g2.pr4.pipeline import generate_items
from evals.intelligence_g2.pr4.project import project_step
from evals.intelligence_g2.pr5.pipeline import rule_presentation
from evals.intelligence_g2.pr6.contracts import FilePin, G3InputView
from evals.intelligence_g2.validate_output import checked_input
from evals.intelligence_g3.contracts import G3Candidate, ReplayObservation
from evals.intelligence_g3.integrity import (
    validate_candidate_evidence,
    validate_identity,
    validate_snapshots,
)
from evals.intelligence_v1.contracts import (
    CandidateDocumentVersion,
    CoverageWindow,
    Paragraph,
    ReplayContext,
)
from evals.intelligence_v1.hashing import content_sha256, sha256_bytes

from .contracts import LedgerError
from .contracts import digest as ledger_digest


def validate_ledger(value):
    if value.as_of > datetime.now(timezone.utc):
        raise LedgerError("G4_RUNTIME_FUTURE_INPUT")
    if not value.time_window_start <= value.time_window_end <= value.as_of:
        raise LedgerError("G4_RUNTIME_INTERVAL_INVALID")
    if value.persona.record_origin != value.record_origin:
        raise LedgerError("G4_RUNTIME_ORIGIN_MISMATCH")
    if value.persona.persona.available_at > value.as_of:
        raise LedgerError("G4_RUNTIME_FUTURE_INPUT")
    if (value.record_origin == "synthetic") != (value.synthetic_provenance_uri is not None):
        raise LedgerError("G4_RUNTIME_ORIGIN_MISMATCH")
    if value.synthetic_provenance_uri:
        checked_relative_path(value.synthetic_provenance_uri)
    policies = {ledger_digest(s.model_dump(mode="json")): s for s in value.sources}
    if len(policies) != len(value.sources):
        raise LedgerError("G4_RUNTIME_DUPLICATE_ID")
    ids, documents = set(), defaultdict(list)
    for doc in value.versions:
        if max(datetime.fromisoformat(doc.available_at), datetime.fromisoformat(doc.observed_at)) > value.as_of:
            raise LedgerError("G4_RUNTIME_FUTURE_INPUT")
        policy = policies.get(doc.source_policy_sha256)
        if (policy is None or policy.source_id != doc.source_id or policy.rights != doc.rights
                or policy.source_url != doc.provenance_uri or doc.record_origin != value.record_origin
                or policy.record_origin != value.record_origin):
            raise LedgerError("G4_RUNTIME_POLICY_MISMATCH")
        if doc.doc_version_id in ids:
            raise LedgerError("G4_RUNTIME_DUPLICATE_ID")
        ids.add(doc.doc_version_id)
        expected_document = "g4doc:" + ledger_digest([doc.source_id, doc.canonical_url])
        expected_version = "g4ver:" + ledger_digest([doc.document_id, doc.supersedes_version_id,
            doc.observed_at, doc.available_at, doc.payload_sha256, doc.content_sha256,
            doc.source_policy_sha256])
        if doc.document_id != expected_document or doc.doc_version_id != expected_version:
            raise LedgerError("G4_RUNTIME_LEDGER_ID_MISMATCH")
        documents[doc.document_id].append(doc)
    if len(documents) > 100:
        raise LedgerError("G4_RUNTIME_RESOURCE_LIMIT")
    for chain in documents.values():
        chain.sort(key=lambda d: d.sequence)
        for n, doc in enumerate(chain):
            if (doc.sequence != n + 1 or doc.supersedes_version_id != (
                    chain[n - 1].doc_version_id if n else None)
                    or (n and (doc.available_at < chain[n - 1].available_at
                               or doc.observed_at <= chain[n - 1].observed_at))):
                raise LedgerError("G4_RUNTIME_LINEAGE_INVALID")
    sources = {s.source_id for s in value.sources}
    if any(s.record_origin != value.record_origin for s in value.sources):
        raise LedgerError("G4_RUNTIME_ORIGIN_MISMATCH")
    if len({c.coverage_window_id for c in value.coverage}) != len(value.coverage):
        raise LedgerError("G4_RUNTIME_DUPLICATE_ID")
    for window in value.coverage:
        if window.source_id not in sources:
            raise LedgerError("G4_RUNTIME_SOURCE_NOT_FOUND")
        if datetime.fromisoformat(window.observed_at) > value.as_of:
            raise LedgerError("G4_RUNTIME_FUTURE_INPUT")


def native_doc(doc, value):
    paragraphs = tuple(Paragraph(paragraph_id=f"p{n + 1}", text=t)
                       for n, t in enumerate(doc.content.paragraphs))
    candidate = CandidateDocumentVersion(doc_version_id=doc.doc_version_id, document_id=doc.document_id,
        canonical_url=("synthetic://g4-runtime-test/" + doc.doc_version_id
                       if doc.record_origin == "synthetic" else doc.canonical_url), source_id=doc.source_id,
        source_type=next(s.source_role for s in value.sources if ledger_digest(
            s.model_dump(mode="json")) == doc.source_policy_sha256),
        content_kind=doc.content_kind,
        title=doc.content.title, language="und", text_excerpt=doc.content.text_excerpt,
        paragraphs=paragraphs, content_sha256=content_sha256(doc.content.title,
            doc.content.text_excerpt, paragraphs), published_at=doc.published_at,
        observed_at=doc.observed_at, available_at=doc.available_at, upstream_document_id=None)
    return candidate


def run_native(value, input_pin, checkpoint):
    from .runtime_contracts import NativeStep, Projection, RuntimeEnvelope
    checkpoint("native_replay")
    value = RuntimeEnvelope.model_validate_json(json_bytes(value))
    if sha256_bytes(json_bytes(value)) != input_pin:
        raise LedgerError("G4_RUNTIME_INPUT_PIN_MISMATCH")
    require_persona_prefix(value)
    policies = {}
    for source in value.sources:
        if source.source_id in policies:
            raise LedgerError("G4_RUNTIME_POLICY_TRANSITION_UNSUPPORTED")
        policies[source.source_id] = G2SourcePolicy(source_id=source.source_id,
            source_type=source.source_role, record_origin=source.record_origin,
            redistribution_rights=source.rights, allowed_use=source.allowed_use,
            max_excerpt_chars=source.max_excerpt_chars)
    projected = {d.doc_version_id: native_doc(d, value) for d in value.versions}
    metadata = {d.doc_version_id: d for d in value.versions}
    identities = {key: VersionIdentity(doc_version_id=key, document_id=c.document_id,
        available_at=c.available_at, supersedes_version_id=metadata[key].supersedes_version_id,
        content_sha256=c.content_sha256) for key, c in projected.items()}
    integrated = value.schema_revision == "g4-h09-runtime-envelope-v2"
    from .runtime_history import native_basis
    native_pin = digest(native_basis(value)) if integrated else input_pin
    # No historical user profile is invented before the first actual version. The
    # ledger retains those observations; native computation starts at availability.
    first_persona = value.persona_history[0].persona.available_at if integrated else None
    times = {max(c.available_at, first_persona) if integrated else c.available_at for c in projected.values()}
    times.add(value.as_of)
    if len(times) > 32:
        raise LedgerError("G4_RUNTIME_RESOURCE_LIMIT")
    prior_group = prior_evidence = prior_rule = None
    stages, observations = [], []
    for ordinal, when in enumerate(sorted(times)):
        checkpoint("native_step")
        persona = max((p for p in value.persona_history if p.persona.available_at <= when),
                      key=lambda p: (p.persona.available_at, value.persona_history.index(p))) if integrated else value.persona
        heads = {}
        for doc in value.versions:
            if projected[doc.doc_version_id].available_at <= when:
                old = heads.get(doc.document_id)
                if old is None or old.sequence < doc.sequence:
                    heads[doc.document_id] = doc
        documents = tuple(G2VisibleDocument(candidate=projected[doc.doc_version_id],
            record_origin=doc.record_origin, redistribution_rights=doc.rights,
            provenance_uri=value.synthetic_provenance_uri or doc.provenance_uri,
            visible_lineage=tuple(identities[d.doc_version_id] for d in sorted(value.versions,
                key=lambda x: x.sequence) if d.document_id == doc.document_id
                and projected[d.doc_version_id].available_at <= when))
            for doc in sorted(heads.values(), key=lambda d: d.document_id))
        windows = tuple(CoverageWindow(**{k: getattr(w, k) for k in (
            "coverage_window_id", "source_id", "start_at", "end_at", "observed_at", "status")},
            reason=w.reason_code) for w in value.coverage if datetime.fromisoformat(w.observed_at) <= when)
        context = ReplayContext(timeline_id=value.stream_id, step_id=f"runtime:{ordinal}", as_of=when,
            persona=persona.persona, candidate_doc_version_ids=tuple(
                d.candidate.doc_version_id for d in documents), previous_delivery_id=None,
            attention_budget_seconds=persona.persona.attention_budget_seconds if integrated else value.config.attention_budget_seconds,
            time_window_start=min(value.time_window_start, when),
            time_window_end=min(value.time_window_end, when), source_coverage=windows, exposure_history=())
        replay = G2ReplayInput(dataset_id="g4:runtime-local:" + value.record_origin,
            dataset_revision="g4-runtime-native-v1", input_manifest_sha256=native_pin, context=context,
            visible_documents=documents, sources=tuple(policies[s] for s in sorted(policies)),
            identity_seeds=tuple(IdentitySeed(document_id=d.candidate.document_id,
                anchor_doc_version_id=d.visible_lineage[0].doc_version_id,
                first_visible_at=d.visible_lineage[0].available_at) for d in documents),
            source_coverage_digest=digest([data(w) for w in windows]), pipeline_revision=G2Config().pipeline_revision,
            config_sha256=digest(G2Config()))
        replay, _ = checked_input(replay, G2Config())
        checkpoint("native_input_validated")
        cursor = ReplayCursor(timeline_id=value.stream_id, step_id=context.step_id, as_of=when,
            ordinal=ordinal, previous_step_id=prior_group.cursor.step_id if prior_group else None)
        gi = GroupingInput(replay_input=replay, strategy="r1", grouping_config_sha256=digest(PR2Config()),
            cursor=cursor, previous_state=prior_group,
            previous_state_sha256=digest(prior_group) if prior_group else None)
        group = run_grouping_step(grouping_input=gi, config=PR2Config())
        checkpoint("grouping")
        ei = EvidenceInput(grouping_input=gi, grouping_result=group, grouping_config=PR2Config(),
            config_sha256=digest(PR3Config()), previous_state=prior_evidence,
            previous_state_sha256=digest(prior_evidence) if prior_evidence else None)
        evidence = run_evidence_step(evidence_input=ei, config=PR3Config())
        checkpoint("evidence")
        rule = generate_items(generation_input=project_step(ei, evidence, previous_state=prior_rule,
            config=PR4Config(), evidence_config=PR3Config()), config=PR4Config())
        presentations = tuple(rule_presentation(i) for i in rule.items)
        stage = NativeStep(replay_input=replay, grouping=group, evidence=evidence, rule=rule,
                           presentations=presentations)
        checkpoint("rule")
        stages.append(stage)
        candidates = []
        for event, bundle, item, snapshot, presentation in zip(
                sorted(group.events, key=lambda x: x.event_key),
                sorted(evidence.bundles, key=lambda x: x.event_key),
                sorted(rule.items, key=lambda x: x.event_key),
                sorted(rule.snapshots, key=lambda x: x.event_key),
                sorted(presentations, key=lambda x: x.event_key), strict=True):
            pointer = f"/stages/{ordinal}"
            view = G3InputView(event_key=event.event_key, event_revision=event.event_revision,
                as_of=when.isoformat(), bundle=data(bundle), rule_item=data(item),
                presentation=data(presentation), snapshot=data(snapshot),
                source_coverage=tuple(data(w) for w in item.source_coverage),
                lineage_ids=snapshot.lineage_ids, trace_pointer=pointer)
            candidate = G3Candidate(event=event, bundle=bundle, rule_item=item, snapshot=snapshot,
                presentation=presentation, trace=FilePin(path=f"stages/{ordinal}.json",
                    sha256=sha256_bytes(json_bytes(stage))),
                trace_pointer=pointer, g2_view_sha256=digest(view))
            validate_candidate_evidence(candidate, {c.claim_key: c for c in evidence.next_state.claims},
                                        {r.ref_id: r for r in evidence.next_state.citations})
            candidates.append(candidate)
        available_ids = {k: v for k, v in identities.items() if v.available_at <= when}
        validate_identity(group.next_state, group.events, available_ids)
        validate_snapshots(rule.next_state.snapshots, group.next_state)
        observations.append(ReplayObservation(identity_state=group.next_state, evidence=evidence,
            candidates=tuple(candidates), source_coverage=windows,
            source_coverage_digest=digest([data(w) for w in windows])))
        prior_group, prior_evidence, prior_rule = group.next_state, evidence.next_state, rule.next_state
    projections = tuple(Projection(doc_version_id=d.doc_version_id,
        ledger_record_sha256=ledger_digest(d.model_dump(mode="json")),
        native_content_sha256=projected[d.doc_version_id].content_sha256,
        native_canonical_url=projected[d.doc_version_id].canonical_url,
        native_content_kind=projected[d.doc_version_id].content_kind) for d in value.versions)
    return tuple(stages), tuple(observations), tuple(identities.values()), projections


def require_persona_prefix(value):
    if value.schema_revision == "g4-h09-runtime-envelope-v2":
        versions = value.persona_history
        if (not versions or versions[-1] != value.persona
                or len({p.persona.persona_version_id for p in versions}) != len(versions)
                or any(p.record_origin != value.record_origin or p.persona.persona_id != value.persona.persona.persona_id
                       or p.persona.available_at > value.as_of for p in versions)
                or any(a.persona.available_at > b.persona.available_at for a, b in zip(versions, versions[1:]))):
            raise LedgerError("G4_RUNTIME_PERSONA_HISTORY_REQUIRED")
        return
    # There is no historical-Persona/state input in v1. Never backdate the current Persona
    # or shift old document observations to its availability; either would invent continuity.
    if value.versions and value.persona.persona.available_at > min(
            datetime.fromisoformat(d.available_at) for d in value.versions):
        raise LedgerError("G4_RUNTIME_PERSONA_HISTORY_REQUIRED")
