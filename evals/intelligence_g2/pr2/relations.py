"""Pair decisions over visible features; abstention is an ordinary prediction."""

from itertools import combinations

from .contracts import PairDecision, fail
from .features import target_conflicts

MERGE_RELATIONS = frozenset({"exact_duplicate", "syndicated", "same_event_different_evidence"})


def jaccard(a, b):
    a, b = set(a), set(b)
    return len(a & b) / len(a | b) if a or b else 0.0


def same_target(a, b):
    if a.ambiguous or b.ambiguous or target_conflicts(a, b):
        return False
    if a.target_link and a.target_link == b.target_link:
        return True
    return bool(a.canonical_subject and a.canonical_subject == b.canonical_subject
                and a.target_version and a.target_version == b.target_version
                and a.action and a.action == b.action
                and a.action_object and a.action_object == b.action_object)


def decide(a, b, *, as_of, strategy, config):
    a, b = sorted((a, b), key=lambda f: f.doc_version_id)
    title, body = jaccard(a.title_tokens, b.title_tokens), jaccard(a.body_tokens, b.body_tokens)
    conflicts = target_conflicts(a, b)
    relation, rule = "uncertain", "insufficient_target"
    if conflicts:
        relation = ("unrelated" if "different_subject" in conflicts
                    else "related_distinct_event")
        rule = "cannot_link"
    elif a.ambiguous or b.ambiguous:
        rule = "ambiguous_subject"
    elif (a.canonical_url and a.canonical_url == b.canonical_url and a.content_sha256
          and a.content_sha256 == b.content_sha256):
        relation, rule = "exact_duplicate", "exact_url_hash"
    else:
        upstream = (a.upstream_document_id == b.document_id or
                    b.upstream_document_id == a.document_id or
                    (a.upstream_document_id and a.upstream_document_id == b.upstream_document_id))
        compatible_subject = bool(a.canonical_subject and a.canonical_subject == b.canonical_subject)
        measurement = "measurement" in {a.material_role, b.material_role}
        if upstream and compatible_subject and not measurement and (a.copy_cue or b.copy_cue):
            relation, rule = "syndicated", "visible_upstream_copy"
        elif same_target(a, b):
            relation, rule = "same_event_different_evidence", "explicit_target"
        elif strategy == "r2" and compatible_subject and a.action and a.action == b.action and (
                a.action_object and a.action_object == b.action_object):
            target_anchor = ((a.target_version and a.target_version == b.target_version)
                             or (a.event_date and a.event_date == b.event_date))
            timing = abs((a.published_at or a.available_at) -
                         (b.published_at or b.available_at)).total_seconds() <= config.window_days * 86400
            text_ok = (min(len(a.body_tokens), len(b.body_tokens)) >= config.min_body_tokens
                       and title >= config.title_jaccard and body >= config.body_jaccard)
            if target_anchor and timing and text_ok:
                is_copy = ((a.copy_cue or b.copy_cue) and not measurement
                           and title >= config.copy_title_jaccard
                           and body >= config.copy_body_jaccard)
                relation, rule = ("syndicated", "near_copy") if is_copy else (
                    "same_event_different_evidence", "constrained_text")
    return PairDecision(left_doc_version_id=a.doc_version_id, right_doc_version_id=b.doc_version_id,
        predicted_relation=relation, as_of=as_of, rule_id=rule,
        evidence_reasons=conflicts or (rule,), feature_refs=a.refs + b.refs,
        cannot_link=conflicts, title_similarity=float(title), body_similarity=float(body))


def predict_relations(*, features, as_of, strategy, config):
    for feature in features:
        if feature.available_at > as_of or any(r.available_at > as_of for r in feature.refs):
            fail("G2_PR2_HISTORY_FUTURE", "relations", "features.available_at", feature.doc_version_id)
    if strategy == "r0":
        return ()
    return tuple(decide(a, b, as_of=as_of, strategy=strategy, config=config)
                 for a, b in combinations(sorted(features, key=lambda f: f.doc_version_id), 2))
