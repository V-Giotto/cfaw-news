"""Conservative grouping from visible text and explicit upstream metadata only."""

from itertools import combinations

from cfaw_news.retrieval import tokenize

from .contracts import PredictedEventGroup
from .hashing import canonical_json, sha256_bytes


def event_group(ids, reasons, revision, *, oracle=False):
    ids = tuple(sorted(ids))
    digest = sha256_bytes(canonical_json({"members": ids, "revision": revision}).encode())
    return PredictedEventGroup(predicted_event_id=("oracle:" if oracle else "predicted:") + digest,
        doc_version_ids=ids, merge_reasons=tuple(sorted(set(reasons))),
        evidence_independence=("not_independent" if set(reasons) & {
            "exact_url_hash", "visible_upstream"} else "unknown"))


def jaccard(left, right):
    return len(left & right) / len(left | right) if left or right else 0.0


def similar(left, right, config):
    def body(row):
        return set(tokenize("\n".join([row.text_excerpt or "", *(p.text for p in row.paragraphs)])))
    a, b = body(left), body(right)
    return (min(len(a), len(b)) >= config.min_body_tokens
            and jaccard(a, b) >= config.body_jaccard
            and jaccard(set(tokenize(left.title)), set(tokenize(right.title)))
            >= config.title_jaccard)


def group_candidates(candidates, config):
    rows = sorted(candidates, key=lambda d: d.doc_version_id)
    parents = list(range(len(rows)))

    def find(i):
        while parents[i] != i:
            i = parents[i]
        return i

    edges = []
    for i, j in combinations(range(len(rows)), 2):
        a, b = rows[i], rows[j]
        reason = None
        if (a.canonical_url and a.content_sha256 and a.canonical_url == b.canonical_url
                and a.content_sha256 == b.content_sha256):
            reason = "exact_url_hash"
        elif (a.upstream_document_id == b.document_id or b.upstream_document_id == a.document_id):
            reason = "visible_upstream"
        if reason:
            parents[find(j)] = find(i)
            edges.append((a.doc_version_id, b.doc_version_id, reason))
    components = {}
    for i, row in enumerate(rows):
        components.setdefault(find(i), []).append(row)
    groups = list(components.values())
    text_edges = []
    # Complete linkage: a near duplicate cannot bridge two incompatible endpoints.
    changed = True
    while changed:
        changed = False
        for i, j in combinations(range(len(groups)), 2):
            if all(similar(a, b, config) for a in groups[i] for b in groups[j]):
                text_edges.append((groups[i][0].doc_version_id, groups[j][0].doc_version_id,
                                   "conservative_text"))
                groups[i] = sorted(groups[i] + groups[j], key=lambda d: d.doc_version_id)
                groups.pop(j)
                changed = True
                break
    result = []
    for group in groups:
        ids = {d.doc_version_id for d in group}
        reasons = [reason for a, b, reason in edges + text_edges if a in ids and b in ids]
        result.append(event_group(ids, reasons, config.grouping_revision))
    return tuple(sorted(result, key=lambda g: g.doc_version_ids))
