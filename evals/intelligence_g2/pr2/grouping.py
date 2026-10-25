"""Complete linkage for R1/R2; the G1 R0 function is called unchanged."""

from itertools import combinations

from evals.intelligence_v1.contracts import BaselineConfig
from evals.intelligence_v1.grouping import group_candidates

from .contracts import BlockedMerge, EventCluster, GroupingPartition, fail
from .relations import MERGE_RELATIONS


def r0_partition(candidates):
    return GroupingPartition(clusters=tuple(EventCluster(member_doc_version_ids=g.doc_version_ids,
        r0_group_id=g.predicted_event_id) for g in group_candidates(candidates, BaselineConfig())),
        blocked_merges=())


def cluster_events(*, candidate_ids, relations, strategy, config):
    del config
    if strategy == "r0":
        raise ValueError("R0 requires the exact G1 candidates via r0_partition")
    ids = sorted(candidate_ids)
    pairs = {(r.left_doc_version_id, r.right_doc_version_id): r for r in relations}
    if len(set(ids)) != len(ids) or len(pairs) != len(relations) or set(pairs) != set(combinations(ids, 2)):
        fail("G2_PR2_PAIR_SET_INVALID", "grouping", "relations")
    groups = [(i,) for i in ids]
    rank = {"exact_duplicate": 3, "syndicated": 2, "same_event_different_evidence": 1}
    while True:
        proposals = []
        for i, j in combinations(range(len(groups)), 2):
            cross = [pairs[tuple(sorted((a, b)))] for a in groups[i] for b in groups[j]]
            if all(r.predicted_relation in MERGE_RELATIONS and not r.cannot_link for r in cross):
                strength = min(rank[r.predicted_relation] for r in cross)
                weakest = min(min(r.title_similarity, r.body_similarity) for r in cross)
                proposals.append((-strength, -weakest, groups[i], groups[j], i, j))
        if not proposals:
            break
        *_, i, j = min(proposals)
        groups[i] = tuple(sorted(groups[i] + groups[j]))
        groups.pop(j)
        groups.sort()
    blocked = []
    for a, b in combinations(groups, 2):
        cross = [pairs[tuple(sorted((x, y)))] for x in a for y in b]
        if any(r.predicted_relation in MERGE_RELATIONS for r in cross):
            blocked.append(BlockedMerge(left_members=a, right_members=b,
                blocking_pairs=tuple((r.left_doc_version_id, r.right_doc_version_id)
                    for r in cross if r.cannot_link or r.predicted_relation not in MERGE_RELATIONS)))
    return GroupingPartition(clusters=tuple(EventCluster(member_doc_version_ids=g) for g in groups),
                             blocked_merges=tuple(blocked))
