"""Content identity and append-only time observations are intentionally separate."""

from .contracts import ItemSnapshot, data, digest


def fact_payload(item):
    return {k: data(item)[k] for k in ("headline", "what_happened", "claim_summaries",
        "selected_claim_keys", "evidence_ref_ids", "evidence_status")}


def content_payload(item):
    return {k: v for k, v in data(item).items()
            if k not in {"item_id", "content_revision", "fact_revision"}}


def identify(item):
    fact_sha = digest(fact_payload(item))
    content_sha = digest(content_payload(item))
    key = "g2:item:" + digest(dict(event_key=item.event_key, content_revision=content_sha,
                                  schema_revision=item.schema_revision))
    return item.model_copy(update={"fact_revision": fact_sha, "content_revision": content_sha, "item_id": key})


def observe(item, view, value):
    prior = value.previous_state.snapshots if value.previous_state else ()
    same = [s for s in prior if s.event_key == item.event_key]
    last_by_event = {s.event_key: s for s in prior}
    previous = same[-1:] + [last_by_event[k] for k in view.predecessor_event_keys if k in last_by_event]
    previous = list({s.snapshot_id: s for s in previous}.values())
    prior_lineage = set(same[-1].lineage_ids) if same else set()
    signal = ("identity_transition" if set(view.lineage_ids) - prior_lineage else
              "first_observed" if not same else
              "same_content_observed" if same[-1].item_id == item.item_id else "content_changed")
    sha = digest(dict(item_id=item.item_id, as_of=value.cursor.as_of.isoformat(),
                      bundle_sha256=view.bundle.bundle_sha256))
    return ItemSnapshot(snapshot_id="g2:snapshot:" + sha, item_id=item.item_id,
        event_key=item.event_key, as_of=value.cursor.as_of, bundle_id=view.bundle.bundle_id,
        bundle_sha256=view.bundle.bundle_sha256, change_signal=signal,
        previous_snapshot_ids=tuple(s.snapshot_id for s in previous), lineage_ids=view.lineage_ids)
