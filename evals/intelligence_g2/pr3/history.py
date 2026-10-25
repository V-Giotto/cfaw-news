"""Append-only claim archive, correction targets and event memberships."""

import re

from .contracts import ClaimMembership, ClaimTransition, CoverageGap, digest, fail
from .scope import compare_scope, lifecycle_fields, value


def namespace(value, config):
    replay = value.grouping_input.replay_input
    return digest(dict(dataset_id=replay.dataset_id, timeline_id=value.grouping_input.cursor.timeline_id,
        strategy=value.grouping_input.strategy, history_revision=config.history_revision,
        config_sha256=digest(config)))


def reconcile(value, extracted, config):
    prior = value.previous_state
    old_claims = {c.claim_key: c for c in prior.claims} if prior else {}
    old_refs = {r.ref_id: r for r in prior.citations} if prior else {}
    claims = []
    for claim in extracted.claims:
        # A surviving immutable paragraph keeps its birth record across merge/split and time.
        old = old_claims.get(claim.claim_key)
        if old:
            if claim.model_copy(update={"origin_event_key": old.origin_event_key,
                    "first_extracted_as_of": old.first_extracted_as_of}) != old:
                fail("G2_PR3_STATE_CHAIN_INVALID", "history", "immutable_claim", claim.claim_key)
            claim = old
        claims.append(claim)
    refs = list(extracted.citations)
    for ref in refs:
        if ref.ref_id in old_refs and ref != old_refs[ref.ref_id]:
            fail("G2_PR3_STATE_CHAIN_INVALID", "history", "immutable_citation", ref.ref_id)
    archived = {**old_claims, **{c.claim_key: c for c in claims}}
    all_refs = {**old_refs, **{r.ref_id: r for r in refs}}
    if len(archived) > config.max_archived_claims:
        fail("G2_PR3_BUDGET_EXCEEDED", "history", "archived_claims")
    return tuple(claims), tuple(refs), archived, all_refs


def memberships(value, archived, refs):
    replay = value.grouping_input.replay_input
    result = value.grouping_result
    owners = {m: e.event_key for e in result.events for m in e.member_doc_version_ids}
    versions = {}
    for doc in replay.visible_documents:
        for version in doc.visible_lineage:
            versions.setdefault(version.doc_version_id, set()).add(owners[doc.candidate.doc_version_id])
    old_rows = value.previous_state.memberships if value.previous_state else ()
    previous = {row.claim_key: row for row in old_rows}
    now, added = {}, []
    active = {e.event_key: e for e in result.events}
    for key, claim in sorted(archived.items()):
        ref = refs[claim.evidence_ref_ids[0]]
        prior = previous.get(key)
        # A document version chain is evidence location, not event identity. Traverse
        # only explicit PR2 identity transitions since this claim's last membership.
        routes = {prior.event_key: ()} if prior else {}
        for transition in result.next_state.transitions:
            if prior is None or transition.effective_at <= prior.effective_at:
                continue
            paths = [routes[k] for k in transition.from_keys if k in routes]
            if paths:
                path = min(paths) + (transition.transition_id,)
                for successor in transition.to_keys:
                    routes.setdefault(successor, path)
        lineage_ids = ()
        if claim.doc_version_id in owners:
            event = owners[claim.doc_version_id]
            basis = "visible_document"
            if prior and event not in routes:
                fail("G2_PR3_STATE_CHAIN_INVALID", "history", "memberships.event_key", key)
            if prior and event != prior.event_key:
                lineage_ids = routes[event]
        else:
            if prior is None:
                continue
            event = prior.event_key
            basis = "prior_membership"
            if event not in active:
                target_version = value_of(claim.scope.target_version)
                successors = {k for k in routes if k in active and not (
                    target_version and active[k].target_version and
                    target_version.removeprefix("v") != active[k].target_version.removeprefix("v"))}
                if len(successors) > 1:
                    # A split may be disambiguated by actual visible document lineage,
                    # but lineage cannot authorize a move to an unrelated birth event.
                    successors &= versions.get(ref.doc_version_id, set())
                if len(successors) != 1:
                    continue
                event = next(iter(successors))
                basis = "pr2_identity_lineage"
                lineage_ids = routes[event]
        now[key] = event
        if prior is None or prior.event_key != event:
            added.append(ClaimMembership(claim_key=key, event_key=event,
                effective_at=value.grouping_input.cursor.as_of, basis=basis, lineage_ids=lineage_ids))
    return now, tuple(added)


def find_transitions(value, current, archived, refs, owners):
    old = value.previous_state
    if old is None:
        old_claims = ()
    else:
        old_claims = old.claims
    transitions, gaps = [], []
    for claim in current:
        if claim.marker == "none":
            continue
        ref = refs[claim.evidence_ref_ids[0]]
        marker, target_metric, new_quantities = lifecycle_fields(ref)
        if marker != claim.marker:
            gaps.append(CoverageGap(code="unresolved_" + claim.marker, source_id=ref.source_id,
                                    doc_version_id=ref.doc_version_id))
            continue
        matches = []
        explicit_prior = bool(re.search(r"\b(?:previous|prior|earlier)\b|先前|此前|原先", claim.statement, re.I))
        explicit_change = bool(re.search(r"corrected to|更正为|修正为", claim.statement, re.I))
        for candidate in old_claims:
            origin = refs[candidate.evidence_ref_ids[0]]
            if (origin.document_id != ref.document_id or origin.source_id != ref.source_id
                    or candidate.attribution.attribution_kind != "publisher_statement"
                    or claim.attribution.attribution_kind != "publisher_statement"
                    or candidate.marker != "none" or candidate.doc_version_id == claim.doc_version_id
                    or owners.get(candidate.claim_key) != owners.get(claim.claim_key)):
                continue
            # A matching number alone cannot identify a claim. Unknown metric/scope,
            # unit or quantifier cannot serve as wildcards for lifecycle changes.
            quantities = candidate.proposition.quantities
            target = bool(len(quantities) == 1 and new_quantities and not candidate.proposition.ambiguous
                and value_of(candidate.proposition.metric) is not None
                and value_of(candidate.proposition.metric) == value_of(target_metric)
                and quantities[0].value.normalized_value == new_quantities[0].value.normalized_value
                and quantities[0].unit == new_quantities[0].unit
                and quantities[0].quantifier == new_quantities[0].quantifier)
            same_subject = (value_of(candidate.proposition.subject) is not None and
                value_of(candidate.proposition.subject) == value_of(claim.proposition.subject))
            same_version = (value_of(candidate.scope.target_version) is not None and
                value_of(candidate.scope.target_version) == value_of(claim.scope.target_version))
            qualified_marker = explicit_prior and (claim.marker == "withdrawal" or (
                explicit_change and len(new_quantities) >= 2))
            if qualified_marker and target and same_subject and same_version and compare_scope(candidate.scope, claim.scope) == "same_declared_scope":
                matches.append(candidate)
        if len(matches) != 1:
            gaps.append(CoverageGap(code="unresolved_" + claim.marker, source_id=ref.source_id,
                                    doc_version_id=ref.doc_version_id))
            continue
        material = dict(kind="corrects" if claim.marker == "correction" else "retracts",
            from_claim_keys=(matches[0].claim_key,), to_claim_keys=(claim.claim_key,),
            effective_at=value.grouping_input.cursor.as_of, trigger_ref_ids=claim.evidence_ref_ids)
        transition = ClaimTransition(transition_id="g2:claim-transition:" + digest({**material,
            "effective_at": value.grouping_input.cursor.as_of.isoformat()}), **material)
        if old and any((t.kind, t.from_claim_keys, t.to_claim_keys) == (
                transition.kind, transition.from_claim_keys, transition.to_claim_keys) for t in old.transitions):
            continue
        transitions.append(transition)
    return tuple(sorted(transitions, key=lambda t: t.transition_id)), tuple(gaps)


def value_of(field):
    return value(field)
