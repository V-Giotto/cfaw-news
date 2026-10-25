"""Immutable snapshots and append-only merge/split/alias history."""

from itertools import combinations

from .contracts import (
    AliasRecord,
    EventSnapshot,
    IdentityState,
    IdentityTransition,
    IdentityUpdate,
    RegisteredEvent,
    data,
    digest,
    fail,
)
from .features import target_conflicts
from .relations import same_target


def namespace(replay_input, strategy, config):
    return digest({"dataset_id": replay_input.dataset_id,
        "timeline_id": replay_input.context.timeline_id, "strategy": strategy,
        "identity_revision": config.identity_revision})


def semantic_state(state):
    if state is None:
        return digest(None)
    value = data(state)
    for field in ("input_manifest_sha256", "previous_state_sha256"):
        value.pop(field)
    return digest(value)


def revision(key, features, relations, related_keys, lineage_ids, config):
    ids = {f.doc_version_id for f in features}
    pairs = [{"left": r.left_doc_version_id, "right": r.right_doc_version_id,
              "relation": r.predicted_relation, "rule_id": r.rule_id,
              "cannot_link": r.cannot_link}
             for r in relations if {r.left_doc_version_id, r.right_doc_version_id} <= ids]
    return digest({"event_key": key, "features": [data(f) for f in features], "pairs": pairs,
        "related_event_keys": related_keys, "lineage_ids": lineage_ids,
        "feature_revision": config.feature_revision, "relation_revision": config.relation_revision,
        "identity_revision": config.identity_revision})


def advance_identity(*, replay_input, features, clusters, previous_state, config,
                     strategy="r1", cursor=None, relations=()):
    """Reconcile a bipartite old-identity/current-cluster graph without largest-overlap guessing."""
    ns = namespace(replay_input, strategy, config)
    prior = previous_state
    registry = {e.event_key: e for e in prior.registry} if prior else {}
    transitions = list(prior.transitions) if prior else []
    aliases = list(prior.aliases) if prior else []
    new_transitions = []
    by_id = {f.doc_version_id: f for f in features}
    groups = [tuple(by_id[m] for m in c.member_doc_version_ids) for c in clusters]
    old_events = [e for e in registry.values() if e.status in {"active", "dormant"}]
    edges = {i: set() for i in range(len(groups))}
    for old in sorted(old_events, key=lambda e: e.event_key):
        old_docs = {f.document_id: f for f in old.last_features}
        overlaps = [i for i, group in enumerate(groups)
                    if any(f.document_id in old_docs for f in group)]
        # Multiple present descendants expose a partition of an earlier registration. All
        # descendants get new keys, including the old anchor child, rather than rewriting it.
        if len(overlaps) > 1:
            for i in overlaps:
                edges[i].add(old.event_key)
            continue
        continuity_matches = []
        strong_matches = []
        for i, group in enumerate(groups):
            shared = [f for f in group if f.document_id in old_docs]
            # An unchanged immutable version continues its own registration even when
            # its subject is ambiguous. This grants no cross-document semantic match.
            continuity = bool(shared) and all(
                (f.doc_version_id == old_docs[f.document_id].doc_version_id and
                 f.content_sha256 == old_docs[f.document_id].content_sha256) or
                (not f.ambiguous and not target_conflicts(old_docs[f.document_id], f))
                for f in shared)
            strong = (not shared and bool(old.last_features) and
                      all(not target_conflicts(a, b) for a in group for b in old.last_features)
                      and any(same_target(a, b) for a in group for b in old.last_features))
            if continuity:
                continuity_matches.append(i)
            elif strong:
                strong_matches.append(i)
        # An existing document lineage wins over new metadata-only affinities. Otherwise a
        # new related-but-unmerged candidate could manufacture a split (especially in R0).
        # Multiple strong-only matches are ambiguous; do not guess a largest-overlap winner.
        selected = continuity_matches if continuity_matches else (
            strong_matches if len(strong_matches) == 1 else [])
        for i in selected:
            edges[i].add(old.event_key)
    # Connected components of old keys <-> current groups include explicit many-to-many cases.
    remaining = set(range(len(groups)))
    components = []
    while remaining:
        selected = {min(remaining)}
        parents = set()
        while True:
            next_parents = set().union(*(edges[i] for i in selected))
            next_selected = selected | {i for i in remaining if edges[i] & next_parents}
            if next_selected == selected and next_parents == parents:
                break
            selected, parents = next_selected, next_parents
        remaining -= selected
        components.append((sorted(selected), sorted(parents)))
    assignments = {}
    for old in old_events:
        registry[old.event_key] = old.model_copy(update={"status": "dormant"})

    def transition(kind, parents, indexes, keys):
        # Only this component's visible observations determine transition identity; whole-bundle
        # pins, generated_at and unrelated events are audit data, not semantic key material.
        visible = [[data(f) for f in groups[i]] for i in indexes]
        tid = "g2:transition:" + digest({"namespace": ns, "kind": kind,
            "parents": parents, "as_of": cursor.as_of.isoformat(), "observations": visible})
        result = IdentityTransition(transition_id=tid, kind=kind, from_keys=tuple(parents),
            to_keys=tuple(keys), effective_at=cursor.as_of, step_id=cursor.step_id,
            trigger_doc_version_ids=tuple(sorted(f.doc_version_id for i in indexes for f in groups[i])),
            reasons=("visible_partition_reconciliation",), previous_semantic_sha256=semantic_state(prior))
        return result

    for indexes, parents in components:
        if len(parents) == 1 and len(indexes) == 1:
            key = parents[0]
            assignments[indexes[0]] = key
            if registry[key].status == "dormant" and next(e for e in old_events if e.event_key == key).status == "dormant":
                row = transition("reactivate", parents, indexes, [key])
                new_transitions.append(row)
                registry[key] = registry[key].model_copy(update={
                    "lineage_ids": registry[key].lineage_ids + (row.transition_id,)})
        elif len(parents) > 1 and len(indexes) == 1:
            key = min(parents, key=lambda k: (registry[k].created_at, k))
            assignments[indexes[0]] = key
            row = transition("merge", parents, indexes, [key])
            new_transitions.append(row)
            registry[key] = registry[key].model_copy(update={
                "lineage_ids": registry[key].lineage_ids + (row.transition_id,)})
            for loser in parents:
                if loser != key:
                    registry[loser] = registry[loser].model_copy(update={"status": "merged"})
                    aliases.append(AliasRecord(alias_key=loser, target_keys=(key,), kind="created",
                        effective_at=cursor.as_of, transition_id=row.transition_id))
        else:
            kind = "birth" if not parents else "split" if len(parents) == 1 else "complex"
            seed = transition(kind, parents, indexes, [])
            keys = []
            for i in indexes:
                anchor = min(groups[i], key=lambda f: (f.available_at, f.doc_version_id)).doc_version_id
                material = {"namespace": ns, "birth_anchor_doc_version_id": anchor,
                            "birth_kind": "new" if not parents else kind}
                if parents:
                    material["split_transition_id"] = seed.transition_id
                key = "g2:event:" + digest(material)
                if key in registry:
                    fail("G2_PR2_IDENTITY_GRAPH_INVALID", "identity", "birth_key", key)
                assignments[i] = key
                keys.append(key)
                registry[key] = RegisteredEvent(event_key=key, created_at=cursor.as_of,
                    anchor_doc_version_id=anchor, status="active", last_features=groups[i],
                    lineage_ids=(seed.transition_id,))
            row = seed.model_copy(update={"to_keys": tuple(sorted(keys))})
            new_transitions.append(row)
            for parent in parents:
                registry[parent] = registry[parent].model_copy(update={"status": "retired_split"})
            if parents and prior:
                # Retire aliases whose old resolution reaches a split parent; preserve original
                # alias entries, and record all successors rather than silently selecting a child.
                for alias_key in sorted({a.alias_key for a in prior.aliases}):
                    resolved = resolve_identity(prior, alias_key, as_of=prior.cursor.as_of)
                    if set(resolved["target_keys"]) & set(parents):
                        aliases.append(AliasRecord(alias_key=alias_key, target_keys=row.to_keys,
                            kind="retired", effective_at=cursor.as_of, transition_id=row.transition_id))
    transitions.extend(new_transitions)
    for i, key in assignments.items():
        old = registry[key]
        current_docs = {f.document_id for f in groups[i]}
        retained = tuple(f for f in old.last_features if f.document_id not in current_docs)
        registry[key] = old.model_copy(update={"status": "active", "last_features": tuple(sorted(
            retained + groups[i], key=lambda f: f.doc_version_id))})
    related = {i: set() for i in assignments}
    owner = {f.doc_version_id: i for i, group in enumerate(groups) for f in group}
    for pair in relations:
        a, b = owner[pair.left_doc_version_id], owner[pair.right_doc_version_id]
        if a != b and pair.predicted_relation == "related_distinct_event":
            related[a].add(assignments[b])
            related[b].add(assignments[a])
    snapshots = []
    for i, group in enumerate(groups):
        key, keys = assignments[i], tuple(sorted(related[i]))
        old = registry[key]
        subjects = {f.canonical_subject for f in group if f.canonical_subject}
        types = {f.event_type for f in group if f.event_type != "unknown"}
        descriptor = {}
        for field in ("target_version", "action", "action_object", "event_date"):
            values = {getattr(f, field) for f in group if getattr(f, field) is not None}
            descriptor[field] = next(iter(values)) if len(values) == 1 else None
        snapshots.append(EventSnapshot(event_key=key,
            event_revision=revision(key, group, relations, keys, old.lineage_ids, config),
            created_at=old.created_at, anchor_doc_version_id=old.anchor_doc_version_id,
            canonical_subject=next(iter(subjects)) if len(subjects) == 1 else None,
            event_type=next(iter(types)) if len(types) == 1 else "unknown",
            **descriptor,
            member_doc_version_ids=tuple(f.doc_version_id for f in group),
            related_event_keys=keys, lineage_ids=old.lineage_ids))
    state = IdentityState(namespace=ns, strategy=strategy, grouping_config_sha256=digest(config),
        input_manifest_sha256=replay_input.input_manifest_sha256, cursor=cursor,
        previous_state_sha256=digest(prior) if prior else None,
        registry=tuple(registry[k] for k in sorted(registry)), transitions=tuple(transitions),
        aliases=tuple(aliases))
    return IdentityUpdate(events=tuple(sorted(snapshots, key=lambda e: e.event_key)),
        transitions=tuple(new_transitions), state=state)


def resolve_identity(state, key, *, as_of):
    registry = {e.event_key: e for e in state.registry}

    def resolve(current, seen):
        if current in seen:
            fail("G2_PR2_IDENTITY_GRAPH_INVALID", "identity", "aliases", current)
        event = registry.get(current)
        if event is None or event.created_at > as_of:
            return {"status": "unknown", "target_keys": ()}
        entries = [a for a in state.aliases if a.alias_key == current and a.effective_at <= as_of]
        if entries:
            last = entries[-1]
            if last.kind == "retired":
                return {"status": "retired_split", "target_keys": last.target_keys}
            result = resolve(last.target_keys[0], seen | {current})
            return {**result, "status": "alias" if result["status"] == "active" else result["status"]}
        splits = [t for t in state.transitions if t.kind in {"split", "complex"}
                  and current in t.from_keys and t.effective_at <= as_of]
        if splits:
            return {"status": "retired_split", "target_keys": splits[-1].to_keys}
        return {"status": "active", "target_keys": (current,)}

    return resolve(key, set())


def resolve_published_reference(*, event_key, event_revision, snapshot):
    """Historical references are exact snapshots, not current alias redirects."""
    if snapshot.event_key != event_key or snapshot.event_revision != event_revision:
        fail("G2_PR2_REVISION_MISMATCH", "identity", "published_reference", event_key)
    return snapshot


def validate_graph(state):
    registry = {r.event_key: r for r in state.registry}
    tids = {t.transition_id for t in state.transitions}
    by_transition = {t.transition_id: t for t in state.transitions}
    if len(registry) != len(state.registry) or len(tids) != len(state.transitions):
        fail("G2_PR2_IDENTITY_GRAPH_INVALID", "identity", "registry")
    for transition in state.transitions:
        if not set(transition.from_keys + transition.to_keys) <= registry.keys():
            fail("G2_PR2_IDENTITY_GRAPH_INVALID", "identity", "transition.keys")
        if (len(set(transition.from_keys)) != len(transition.from_keys)
                or len(set(transition.to_keys)) != len(transition.to_keys)
                or any(registry[k].created_at > transition.effective_at
                       for k in transition.from_keys + transition.to_keys)):
            fail("G2_PR2_IDENTITY_GRAPH_INVALID", "identity", "transition.time_or_keys")
        if ((transition.kind == "birth" and (transition.from_keys or len(transition.to_keys) != 1))
                or (transition.kind == "merge" and (len(transition.from_keys) < 2
                    or len(transition.to_keys) != 1 or transition.to_keys[0] not in transition.from_keys))
                or (transition.kind in {"split", "complex"} and (not transition.from_keys
                    or len(transition.to_keys) < 2 or set(transition.from_keys) & set(transition.to_keys)))):
            fail("G2_PR2_IDENTITY_GRAPH_INVALID", "identity", "transition.cardinality")
    for record in state.registry:
        if not set(record.lineage_ids) <= tids:
            fail("G2_PR2_IDENTITY_GRAPH_INVALID", "identity", "lineage_ids", record.event_key)
    for alias in state.aliases:
        if (alias.alias_key not in registry or alias.alias_key in alias.target_keys
                or not set(alias.target_keys) <= registry.keys() or alias.transition_id not in tids
                or (alias.kind == "created" and len(alias.target_keys) != 1)):
            fail("G2_PR2_IDENTITY_GRAPH_INVALID", "identity", "aliases", alias.alias_key)
        transition = by_transition[alias.transition_id]
        if (transition.effective_at != alias.effective_at
                or any(registry[k].created_at > alias.effective_at for k in alias.target_keys)
                or (alias.kind == "created" and (transition.kind != "merge"
                    or alias.alias_key not in transition.from_keys
                    or alias.target_keys != transition.to_keys))
                or (alias.kind == "retired" and (transition.kind not in {"split", "complex"}
                    or alias.target_keys != transition.to_keys))):
            fail("G2_PR2_IDENTITY_GRAPH_INVALID", "identity", "aliases", alias.alias_key)
    for cutoff in sorted({a.effective_at for a in state.aliases} | {state.cursor.as_of}):
        for key in registry:
            resolve_identity(state, key, as_of=cutoff)
    for left, right in combinations(state.transitions, 2):
        if left.effective_at > right.effective_at:
            fail("G2_PR2_STATE_CHAIN_INVALID", "identity", "transitions.order")
