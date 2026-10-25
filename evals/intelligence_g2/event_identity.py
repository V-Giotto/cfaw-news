"""Document-lineage placeholder identity. Cross-document event identity is PR2 work."""

from .contracts import StableEventIdentity, digest


def event_key(replay_input, document_id, identity_revision):
    return "g2:event:" + digest({
        "identity_revision": identity_revision, "dataset_id": replay_input.dataset_id,
        "timeline_id": replay_input.context.timeline_id, "anchor_document_id": document_id,
    })


def event_revision(key, candidate):
    return digest({"event_key": key, "members": [{"doc_version_id": candidate.doc_version_id,
                                                 "content_sha256": candidate.content_sha256}]})


def build_events(replay_input, config):
    seeds = {s.document_id: s for s in replay_input.identity_seeds}
    result = []
    for document in replay_input.visible_documents:
        candidate = document.candidate
        seed = seeds[candidate.document_id]
        key = event_key(replay_input, candidate.document_id, config.identity_revision)
        result.append(StableEventIdentity(event_key=key,
            identity_revision=config.identity_revision, first_visible_at=seed.first_visible_at,
            anchor_doc_version_id=seed.anchor_doc_version_id,
            member_doc_version_ids=(candidate.doc_version_id,),
            event_revision=event_revision(key, candidate)))
    return tuple(sorted(result, key=lambda e: e.event_key))
