"""Exact native projections and publication qualification; no HTTP or database writes."""

from uuid import uuid4

from sqlalchemy import select

from evals.intelligence_g2.contracts import data, json_bytes
from evals.intelligence_v1.hashing import sha256_bytes

from .checkpoint import PersistenceError
from .contracts import canonical, digest
from .models import G4Coverage, G4Document, G4SourcePolicy, G4Version
from .persistence_contracts import BriefingView, HeadView, RunView


def parse(model, value):
    return model.model_validate_json(canonical(value))


def corpus_basis(session):
    def rows(model, fields):
        return sorted([[getattr(row, key) for key in fields] for row in session.scalars(select(model))], key=canonical)
    return digest(dict(documents=rows(G4Document, ("document_id", "head_version_id", "last_observed_at")),
        versions=rows(G4Version, ("doc_version_id", "record_sha256", "available_at")),
        policies=rows(G4SourcePolicy, ("policy_sha256", "registered_at", "data")),
        coverage=rows(G4Coverage, ("coverage_window_id", "observed_at", "data"))))


def head_view(head, epoch):
    return parse(HeadView, dict(stream_id=head.id, sequence=head.sequence, sha256=head.sha256, epoch=epoch,
        latest_snapshot_id=head.latest_snapshot_id, publication_version=head.publication_version,
        persona_version_id=head.persona_version_id))


def mutation_view(value):
    from .persistence_contracts import MutationView
    head = dict(value["head"])
    head["stream_id"] = head.pop("id")
    return parse(MutationView, {**value, "head": head})


def run_view(row):
    return parse(RunView, dict(id=row.id, version=row.version, status=row.status,
        cancel_requested=row.cancel_requested, created_at=row.created_at,
        **{key: row.data[key] for key in ("started_at", "finished_at", "as_of", "persona_version_id",
                                        "snapshot_id", "reason_codes", "input_sha256")}))


def qualification(result, mode):
    origin = "real" if mode == "real" else "synthetic"
    if result.input.record_origin != origin:
        raise PersistenceError("G4_RUNTIME_ORIGIN_MISMATCH")
    if (result.context is None or result.ranking is None or not result.stages or not result.archive_snapshot_ids
            or not result.stages[-1].evidence.claims or result.state == "evidence_not_ready"):
        raise PersistenceError(result.reason_codes[0] if result.reason_codes else "G4_EVIDENCE_NOT_READY")
    # Gaps remain diagnostics. The latest observation of each configured source must actually
    # confirm a bounded poll; a historical point does not prove unobserved intervals covered.
    for source in {p.source_id for p in result.input.sources}:
        windows = [w for w in result.input.coverage if w.source_id == source]
        if not windows:
            raise PersistenceError("G4_SOURCE_OBSERVATION_REQUIRED")
        latest = max(w.observed_at for w in windows)
        statuses = {w.status for w in windows if w.observed_at == latest and w.start_at == w.end_at == latest}
        if statuses != {"covered"}:
            raise PersistenceError("G4_SOURCE_INTERRUPTED")
    if mode == "real" and result.state == "plan_ready":
        # PR3 cannot currently qualify real independent support. Never use storage as an upgrade.
        raise PersistenceError("G4_REAL_PLAN_NOT_QUALIFIED")


def snapshot_view(result, *, run, version, generated_at, mode):
    qualification(result, mode)
    identifier = uuid4().hex
    archive, deliveries = [], []
    planned = {e.event_key: e for e in result.plan.events} if result.plan else {}
    ranked = {e.event_key: e for e in result.ranking.events}
    versions = {v.doc_version_id: v for v in result.input.versions}
    for candidate in result.context.replay.candidates:
        event = candidate.event
        members = [versions[key] for key in event.member_doc_version_ids]
        choice = planned.get(event.event_key)
        reasons = (*ranked[event.event_key].block_reasons,
                   *(r.code for r in choice.reasons)) if choice else ranked[event.event_key].block_reasons
        title = candidate.rule_item.headline.text if candidate.rule_item.headline else members[0].content.title
        archive.append(dict(id=digest([identifier, candidate.snapshot.snapshot_id]), event_key=event.event_key,
            event_revision=event.event_revision, event_snapshot_id=candidate.snapshot.snapshot_id, title=title,
            source_ids=sorted({d.source_id for d in members}), rights=sorted({d.rights for d in members}),
            content_kinds=sorted({d.content_kind for d in members}), evidence_status=candidate.rule_item.evidence_status,
            native_tier=candidate.rule_item.tier_candidate, reason_codes=sorted(set(reasons))))
    for ordinal, key in enumerate(result.plan.display_order if result.plan else ()):
        choice, row = planned[key], next(a for a in archive if a["event_key"] == key)
        if choice.tier is None:
            raise PersistenceError("G4_DELIVERY_PLAN_INVALID")
        deliveries.append(dict(id=digest(["delivery", identifier, row["event_snapshot_id"]]),
            event_snapshot_id=row["event_snapshot_id"], event_key=key, event_revision=row["event_revision"],
            ordinal=ordinal, tier=choice.tier, status=choice.status, reason_codes=[r.code for r in choice.reasons],
            estimated_reading_seconds=choice.estimated_read_seconds))
    fields = dict(id=identifier, run_id=run.id, version=version, as_of=result.input.as_of.isoformat(),
        generated_at=generated_at, mode=mode, evidence_status=result.state,
        persona_version_id=run.data["persona_version_id"], runtime_sha256=sha256_bytes(json_bytes(result)),
        runtime_policy_sha256=result.input.config.ranking_policy_sha256, reason_codes=list(result.reason_codes),
        coverage=data(result.coverage), archive_snapshot_ids=list(result.archive_snapshot_ids),
        unmet_protected_event_keys=list(result.plan.diagnostics.unmet_protected_event_keys) if result.plan else [],
        display_order=list(result.plan.display_order) if result.plan else [], deliveries=deliveries, archive=archive,
        budget_diagnostics=data(result.plan.diagnostics) if result.plan else None)
    return parse(BriefingView, {**fields, "etag": '"' + digest(fields) + '"'})
