"""Pure PR2 grouping step. No claims, evidence judgements or briefing allocation."""

from evals.intelligence_g2.contracts import G2Config
from evals.intelligence_g2.event_identity import event_key as pr1_event_key

from .contracts import (
    CompatibilityLink,
    EventView,
    GroupingResult,
    PR2Diagnostic,
    SourcePointer,
    digest,
)
from .features import extract_features
from .grouping import cluster_events, r0_partition
from .identity import advance_identity
from .relations import predict_relations
from .validate_output import checked_grouping_input, validate_output


def build_views(value, events, relations):
    replay = value.replay_input
    documents = {d.candidate.doc_version_id: d.candidate for d in replay.visible_documents}
    dependent = {m for r in relations if r.predicted_relation in {"exact_duplicate", "syndicated"}
                 for m in (r.left_doc_version_id, r.right_doc_version_id)}
    views = []
    for event in events:
        members = [documents[m] for m in event.member_doc_version_ids]
        representative = min(members, key=lambda d: (not any(p.text.strip() for p in d.paragraphs),
                                                     d.available_at, d.doc_version_id))
        views.append(EventView(event_key=event.event_key,
            representative_doc_version_id=representative.doc_version_id,
            member_doc_version_ids=event.member_doc_version_ids,
            source_pointers=tuple(SourcePointer(doc_version_id=d.doc_version_id,
                source_id=d.source_id, upstream_document_id=d.upstream_document_id,
                dependency="duplicate_or_reprint" if d.doc_version_id in dependent else "unknown")
                for d in members),
            compatibility_links=tuple(CompatibilityLink(pr1_event_key=pr1_event_key(
                replay, d.document_id, G2Config().identity_revision), event_key=event.event_key,
                document_id=d.document_id, as_of=value.cursor.as_of) for d in members)))
    return tuple(views)


def run_grouping_step(*, grouping_input, config):
    value, config = checked_grouping_input(grouping_input, config)
    replay = value.replay_input
    features = extract_features(replay_input=replay, previous_state=value.previous_state, config=config)
    relations = predict_relations(features=features, as_of=value.cursor.as_of,
                                  strategy=value.strategy, config=config)
    partition = (r0_partition(tuple(d.candidate for d in replay.visible_documents))
        if value.strategy == "r0" else cluster_events(candidate_ids=replay.context.candidate_doc_version_ids,
            relations=relations, strategy=value.strategy, config=config))
    update = advance_identity(replay_input=replay, features=features, clusters=partition.clusters,
        previous_state=value.previous_state, config=config, strategy=value.strategy,
        cursor=value.cursor, relations=relations)
    views = build_views(value, update.events, relations)
    counts = {"candidates": len(features), "pairs": len(relations), "events": len(update.events),
              "views": len(views), "blocked_merges": len(partition.blocked_merges),
              "transitions": len(update.transitions)}
    result = GroupingResult(input_sha256=digest(value), cursor=value.cursor, strategy=value.strategy,
        features=features, relations=relations, partition=partition, events=update.events, views=views,
        transitions=update.transitions, next_state=update.state,
        validation=PR2Diagnostic(ok=True, counts=counts))
    validate_output(result, value, config)
    return result
