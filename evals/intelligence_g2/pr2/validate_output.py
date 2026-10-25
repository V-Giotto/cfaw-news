"""Pure preflight, state-chain and output cross-validation."""

from datetime import datetime
from itertools import combinations

from evals.intelligence_g2.contracts import G2Config, digest, parse
from evals.intelligence_g2.validate_output import checked_input, preflight_time
from evals.intelligence_v1.temporal import parse_instant, utc_instant

from .contracts import GroupingInput, GroupingResult, PR2Config, fail
from .features import extract_features
from .grouping import cluster_events, r0_partition
from .identity import advance_identity, namespace, validate_graph
from .relations import MERGE_RELATIONS, predict_relations


def get(value, field, default=None):
    return value.get(field, default) if isinstance(value, dict) else getattr(value, field, default)


def instant(value):
    return utc_instant(value) if isinstance(value, datetime) else parse_instant(value)


def preflight_history(state, cutoff):
    if state is None:
        return
    cursor = get(state, "cursor")
    own_time = get(cursor, "as_of")
    if own_time is not None and instant(own_time) > cutoff:
        fail("G2_PR2_HISTORY_FUTURE", "identity", "previous_state.cursor")
    bound = instant(own_time) if own_time is not None else cutoff
    for collection, time_fields in (("registry", ("created_at",)),
                                    ("transitions", ("effective_at",)),
                                    ("aliases", ("effective_at",))):
        for row in get(state, collection, ()):
            for field in time_fields:
                value = get(row, field)
                if value is not None and instant(value) > bound:
                    fail("G2_PR2_HISTORY_FUTURE", "identity", collection + "." + field)
            for feature in get(row, "last_features", ()):
                available = get(feature, "available_at")
                if available is not None and instant(available) > bound:
                    fail("G2_PR2_HISTORY_FUTURE", "identity", "last_features.available_at")
                for ref in get(feature, "refs", ()):
                    if instant(get(ref, "available_at")) > bound:
                        fail("G2_PR2_HISTORY_FUTURE", "identity", "feature_refs.available_at")


def checked_grouping_input(grouping_input, config):
    replay = get(grouping_input, "replay_input")
    preflight_time(replay)  # Reject future bodies before nested serialization.
    cutoff = get(get(replay, "context"), "as_of")
    if cutoff is not None:
        preflight_history(get(grouping_input, "previous_state"), instant(cutoff))
    config = parse(PR2Config, config)
    value = parse(GroupingInput, grouping_input)
    replay, _ = checked_input(value.replay_input, G2Config())
    value = value.model_copy(update={"replay_input": replay})
    cursor, context, prior = value.cursor, replay.context, value.previous_state
    if value.grouping_config_sha256 != digest(config):
        fail("CONFIG_NOT_PINNED", "input", "grouping_config_sha256")
    if (cursor.timeline_id, cursor.step_id, cursor.as_of) != (
            context.timeline_id, context.step_id, context.as_of):
        fail("G2_CONTEXT_MISMATCH", "input", "cursor")
    if prior is None:
        if cursor.ordinal != 0 or cursor.previous_step_id is not None or value.previous_state_sha256 is not None:
            fail("G2_PR2_STATE_CHAIN_INVALID", "identity", "cursor")
    else:
        if (value.previous_state_sha256 != digest(prior)
                or prior.namespace != namespace(replay, value.strategy, config)
                or prior.grouping_config_sha256 != digest(config)
                or prior.input_manifest_sha256 != replay.input_manifest_sha256
                or cursor.ordinal != prior.cursor.ordinal + 1
                or cursor.previous_step_id != prior.cursor.step_id
                or cursor.as_of <= prior.cursor.as_of):
            fail("G2_PR2_STATE_CHAIN_INVALID", "identity", "previous_state")
        validate_graph(prior)
    return value, config


def validate_output(result, grouping_input, config):
    value, config = checked_grouping_input(grouping_input, config)
    preflight_history(get(result, "next_state"), value.cursor.as_of)
    result = parse(GroupingResult, result, stage="output")
    replay = value.replay_input
    if (result.input_sha256 != digest(value) or result.cursor != value.cursor
            or result.strategy != value.strategy):
        fail("G2_CONTEXT_MISMATCH", "output", "result")
    expected_features = extract_features(replay_input=replay, previous_state=value.previous_state,
                                         config=config)
    if result.features != expected_features:
        fail("G2_PR2_FEATURE_PROVENANCE_INVALID", "features", "features")
    for f in result.features:
        if any(r.available_at > value.cursor.as_of for r in f.refs):
            fail("G2_PR2_HISTORY_FUTURE", "features", "refs", f.doc_version_id)
    ids = tuple(sorted(replay.context.candidate_doc_version_ids))
    pairs = {(r.left_doc_version_id, r.right_doc_version_id): r for r in result.relations}
    expected_relations = predict_relations(features=expected_features, as_of=value.cursor.as_of,
                                          strategy=value.strategy, config=config)
    if (len(pairs) != len(result.relations) or (value.strategy != "r0" and
            set(pairs) != set(combinations(ids, 2))) or (value.strategy == "r0" and pairs)):
        fail("G2_PR2_PAIR_SET_INVALID", "relations", "relations")
    if result.relations != expected_relations:
        fail("G2_PR2_FEATURE_PROVENANCE_INVALID", "relations", "relations")
    members = [m for g in result.partition.clusters for m in g.member_doc_version_ids]
    if len(members) != len(set(members)) or set(members) != set(ids):
        fail("GROUP_MEMBERS_INVALID", "grouping", "member_doc_version_ids")
    if value.strategy != "r0":
        for group in result.partition.clusters:
            for a, b in combinations(group.member_doc_version_ids, 2):
                pair = pairs[tuple(sorted((a, b)))]
                if pair.cannot_link or pair.predicted_relation not in MERGE_RELATIONS:
                    fail("G2_PR2_CANNOT_LINK_VIOLATION", "grouping", "member_doc_version_ids", a)
    expected_partition = (r0_partition(tuple(d.candidate for d in replay.visible_documents))
        if value.strategy == "r0" else cluster_events(candidate_ids=ids, relations=result.relations,
            strategy=value.strategy, config=config))
    if result.partition != expected_partition:
        fail("GROUP_MEMBERS_INVALID", "grouping", "partition")
    update = advance_identity(replay_input=replay, features=expected_features,
        clusters=expected_partition.clusters, previous_state=value.previous_state, config=config,
        strategy=value.strategy, cursor=value.cursor, relations=result.relations)
    validate_graph(result.next_state)
    if (result.events != update.events or result.transitions != update.transitions
            or result.next_state != update.state):
        fail("G2_PR2_REVISION_MISMATCH", "identity", "events_or_state")
    from .pipeline import build_views

    if result.views != build_views(value, result.events, result.relations):
        fail("GROUP_MEMBERS_INVALID", "output", "views")
    expected_counts = {"candidates": len(ids), "pairs": len(pairs), "events": len(result.events),
        "views": len(result.views), "blocked_merges": len(result.partition.blocked_merges),
        "transitions": len(result.transitions)}
    if not result.validation.ok or result.validation.errors or result.validation.counts != expected_counts:
        fail("G2_CONTEXT_MISMATCH", "output", "validation")
    return result.validation
