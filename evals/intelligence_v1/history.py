"""Pure prediction-side historical identity checks and explicit exposure adjustments."""

from .exceptions import ContractError
from .hashing import canonical_json, sha256_bytes
from .temporal import visible_versions


def validate_snapshot(item, deliveries, documents, steps, grouping_revision):
    delivery = deliveries.get(item.delivery_id)
    if delivery is None:
        raise ContractError("REFERENCE_NOT_FOUND", field="delivery_id")
    references = [s for s in steps if s.previous_delivery_id == item.delivery_id]
    if not references or len({s.timeline_id for s in references}) != 1:
        raise ContractError("DELIVERY_SCOPE_INVALID")
    scopes = [set(s.family_scope_ids) for s in references]
    by_id = {d.doc_version_id: d for d in documents}
    visible = {d.doc_version_id for d in visible_versions(documents, as_of=delivery.as_of)}
    for member in item.members:
        document = by_id.get(member.doc_version_id)
        if document is None:
            raise ContractError("REFERENCE_NOT_FOUND", field="doc_version_id")
        if not all(document.family_id in scope for scope in scopes):
            raise ContractError("DELIVERY_SCOPE_INVALID")
        if member.doc_version_id not in visible:
            raise ContractError("FUTURE_OR_STALE_HISTORY_VERSION")
        if (member.document_id != document.document_id
                or member.content_sha256 != document.content_sha256):
            raise ContractError("HISTORY_SNAPSHOT_MISMATCH")
    ids = tuple(m.doc_version_id for m in item.members)
    digest = sha256_bytes(canonical_json({"members": sorted(ids),
                                         "revision": grouping_revision}).encode())
    if item.event_prediction_id != "predicted:"+digest:
        raise ContractError("HISTORY_PREDICTION_ID_MISMATCH")


def exposure_adjustment(context, candidates, item, config):
    by_id = {d.doc_version_id: d for d in candidates}
    current = [by_id[key] for key in item.doc_version_ids]
    identities = {d.document_id for d in current}
    matching = [h for h in context.delivery_history
                if identities & {m.document_id for m in h.members}]
    if not matching:
        return {"penalty": 0.0, "text_delta": "first_seen"}
    latest = max(matching, key=lambda h: (
        h.delivery_generated_at, h.delivery_as_of, h.delivery_id))
    matching = [h for h in matching if h.delivery_id == latest.delivery_id]
    prior = [m for h in matching for m in h.members]
    old_hashes = {m.content_sha256 for m in prior if m.content_sha256 is not None}
    hashes = {d.content_sha256 for d in current if d.content_sha256 is not None}
    additions = hashes-old_hashes
    if additions:
        delta = "new_text"
    elif any(d.content_sha256 is None for d in [*current, *prior]):
        delta = "unknown"
    else:
        delta = "no_change"
    targets = {h.event_prediction_id for h in matching}
    # Snapshot membership is a server inclusion, never evidence of viewport rendering.
    signals = {"included"}
    signals.update(e.kind for e in context.exposure_history
                   if e.delivery_id == latest.delivery_id and e.event_prediction_id in targets)
    weights = {"included": config.included_penalty, "rendered": config.rendered_penalty,
               "acknowledged": config.acknowledged_penalty}
    penalty = sum(weights.get(kind, 0) for kind in sorted(signals)) if delta == "no_change" else 0.0
    return {"penalty": round(penalty, config.score_decimals), "text_delta": delta,
            "history_delivery_id": latest.delivery_id,
            "history_event_prediction_ids": tuple(sorted(targets)),
            "exposure_signals": tuple(sorted(signals)), "new_content_hashes": tuple(sorted(additions))}
