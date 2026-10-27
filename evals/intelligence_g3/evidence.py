"""Shared native evidence closure and append-only state checks; no assembly or inference."""

from evals.intelligence_g2.contracts import digest
from evals.intelligence_g2.pr3.contracts import CoverageGap
from evals.intelligence_g2.pr3.validate_output import check_claim_fields, check_ref_bytes
from evals.intelligence_v1.exceptions import ContractError

from .contracts import fail


def unique(rows, key, name):
    result = {}
    for row in rows:
        identity = key(row)
        if identity in result:
            fail("G3_DUPLICATE_ID", name)
        result[identity] = row
    return result


def same(left, right, name):
    if left != right:
        fail("G3_REFERENCE_MISMATCH", name)


def require(keys, archive, name):
    if not set(keys) <= archive.keys():
        fail("G3_REFERENCE_NOT_FOUND", name)


def checked_native(check, *args):
    try:
        check(*args)
    except ContractError:
        fail("G3_REFERENCE_MISMATCH", "evidence.native_content")


def validate_evidence(result, identity, documents, coverage, prior=None):
    """Validate current/bundle/archive copies against each step's own refs and links."""
    state = result.next_state
    same(result.cursor, identity.cursor, "evidence.cursor")
    same(state.cursor, result.cursor, "evidence_state.cursor")
    same(state.grouping_state_sha256, digest(identity), "evidence.identity")
    same(state.previous_state_sha256, digest(prior.next_state) if prior else None, "evidence.parent")
    if (not result.validation.ok or result.validation.errors
            or result.validation.locator_validation != "passed"
            or result.validation.rule_contract_validation != "passed"):
        fail("G3_PARENT_INVALID", "evidence.validation")
    claims = unique(state.claims, lambda c: c.claim_key, "archive.claim_key")
    refs = unique(state.citations, lambda r: r.ref_id, "archive.ref_id")
    current = unique(result.claims, lambda c: c.claim_key, "current.claim_key")
    current_refs = unique(result.citations, lambda r: r.ref_id, "current.ref_id")
    registry = {r.event_key: r for r in identity.registry}
    active = {k for k, r in registry.items() if r.status == "active"}
    transitions = {t.transition_id: t for t in identity.transitions}
    for ref in refs.values():
        doc = documents.get(ref.doc_version_id)
        if doc is None:
            fail("G3_REFERENCE_NOT_FOUND", "citation.document")
        checked_native(check_ref_bytes, ref)
        same((ref.document_id, ref.available_at, ref.content_sha256),
             (doc.document_id, doc.available_at, doc.content_sha256), "citation.identity")
    for claim in claims.values():
        require(claim.evidence_ref_ids, refs, "claim.evidence_ref_ids")
        checked_native(check_claim_fields, claim, refs)
        require((claim.origin_event_key,), registry, "claim.origin_event")
        ref = refs[claim.evidence_ref_ids[0]]
        same(claim.record_origin, ref.record_origin, "claim.origin")
    for rows, archive, key, name in ((current, claims, "claim_key", "current.claim"),
                                    (current_refs, refs, "ref_id", "current.citation")):
        for row in rows.values():
            same(archive.get(getattr(row, key)), row, name)
    same(set(current_refs), {r for c in current.values() for r in c.evidence_ref_ids}, "current.citation_set")
    for field, now in (("claims", current), ("citations", current_refs)):
        key = "claim_key" if field == "claims" else "ref_id"
        old = {getattr(r, key): r for r in getattr(prior.next_state, field)} if prior else {}
        for k in old.keys() & now.keys():
            same(old[k], now[k], "immutable_" + field)
        expected = {**old, **now}
        same(getattr(state, field), tuple(expected[k] for k in sorted(expected)), "archive." + field)
    for field in ("memberships", "assessments", "transitions"):
        previous = getattr(prior.next_state, field) if prior else ()
        same(getattr(state, field), previous + getattr(result, field), "archive." + field)
    owners = {}
    seen = set()
    for row in state.memberships:
        identity_key = (row.claim_key, row.event_key, row.effective_at)
        if identity_key in seen:
            fail("G3_DUPLICATE_ID", "membership")
        seen.add(identity_key)
        require((row.claim_key,), claims, "membership.claim")
        require((row.event_key,), registry, "membership.event")
        require(row.lineage_ids, transitions, "membership.lineage")
        if (registry[row.event_key].created_at > row.effective_at
                or claims[row.claim_key].first_extracted_as_of > row.effective_at
                or any(transitions[k].effective_at > row.effective_at for k in row.lineage_ids)):
            fail("G3_INVALID_INTERVAL", "membership")
        owners[row.claim_key] = row.event_key
    links = unique(result.links, lambda r: r.link_key, "link_key")
    for link in links.values():
        require((link.target_claim_key, link.evidence_claim_key), current, "link.claim")
        if (owners.get(link.target_claim_key) != owners.get(link.evidence_claim_key)
                or link.ref_id not in current[link.evidence_claim_key].evidence_ref_ids):
            fail("G3_REFERENCE_MISMATCH", "link.membership")
    conflicts = unique(result.conflicts, lambda c: c.conflict_id, "conflict_id")
    for conflict in conflicts.values():
        require(conflict.claim_keys, current, "conflict.claim")
        require(conflict.ref_ids, current_refs, "conflict.ref")
        if len({owners.get(k) for k in conflict.claim_keys}) != 1:
            fail("G3_REFERENCE_MISMATCH", "conflict.membership")
    lifecycle = {}
    unique(state.transitions, lambda t: t.transition_id, "claim_transition_id")
    for transition in state.transitions:
        require(transition.from_claim_keys + transition.to_claim_keys, claims, "claim_transition.claim")
        require(transition.trigger_ref_ids, refs, "claim_transition.ref")
        lifecycle.update({k: "superseded" if transition.kind == "corrects" else "retracted"
                          for k in transition.from_claim_keys})
    assessments = unique(result.assessments, lambda a: a.claim_key, "assessment.claim")
    expected_owners = {k: v for k, v in owners.items() if v in active}
    require(current, expected_owners, "current_claim.membership")
    same(set(assessments), set(expected_owners), "assessment.claim_set")
    for assessment in state.assessments:
        require((assessment.claim_key,), claims, "archive_assessment.claim")
        require((assessment.event_key,), registry, "archive_assessment.event")
        if assessment.verification_state == "independently_supported":
            fail("G3_REFERENCE_MISMATCH", "independent_support")
    disputed = {k for c in conflicts.values() for k in c.claim_keys}
    for key, assessment in assessments.items():
        claim = claims[key]
        same((assessment.event_key, assessment.as_of), (expected_owners[key], result.cursor.as_of),
             "assessment.binding")
        require(assessment.evidence_link_ids, links, "assessment.link")
        same(assessment.evidence_link_ids,
             tuple(link.link_key for link in result.links if link.target_claim_key == key), "assessment.links")
        life = lifecycle.get(key, "current" if key in current else "historical")
        verification = ("retracted" if life == "retracted" else "disputed" if key in disputed else
                        "unverified" if claim.attribution.attribution_kind == "secondary_material"
                        else "source_attributed")
        same((assessment.lifecycle, assessment.verification_state), (life, verification), "assessment.status")
        same(assessment.limitations, claim.limitations + (() if key in current else
             ("historical_not_current_evidence",)), "assessment.limitations")
    bundles = unique(result.bundles, lambda b: b.event_key, "bundle.event")
    same(set(bundles), active, "bundle.active_set")
    gaps = result.validation.coverage_gaps
    required_gaps = ([CoverageGap(code="coverage_unknown")] if not coverage else
                     [CoverageGap(code="source_" + w.status, source_id=w.source_id,
                                  coverage_window_id=w.coverage_window_id)
                      for w in coverage if w.status != "covered"])
    if any(gap not in gaps for gap in required_gaps):
        fail("G3_REFERENCE_MISMATCH", "coverage.required_diagnostic")
    windows = {w.coverage_window_id: w for w in coverage}
    for gap in gaps:
        if gap.coverage_window_id is not None:
            require((gap.coverage_window_id,), windows, "coverage_gap.window")
            same(gap.source_id, windows[gap.coverage_window_id].source_id, "coverage_gap.source")
        if gap.doc_version_id is not None:
            require((gap.doc_version_id,), documents, "coverage_gap.document")
    for key, expected in dict(claims=len(current), citations=len(current_refs), bundles=len(bundles),
            conflicts=len(conflicts), transitions=len(result.transitions), coverage_gaps=len(gaps),
            confirmed_independent_support=0).items():
        same(result.validation.counts.get(key), expected, "evidence.counts." + key)
    lineage = unique(result.lineage, lambda r: r.doc_version_id, "lineage.document")
    require(lineage, documents, "lineage.document")
    for bundle in bundles.values():
        keys = tuple(sorted(k for k, v in expected_owners.items() if v == bundle.event_key))
        same(bundle.current_claim_keys, tuple(k for k in keys if k in current), "bundle.current_claims")
        same(bundle.historical_claim_keys, tuple(k for k in keys if k not in current), "bundle.historical_claims")
        for field, expected in (
            ("assessments", tuple(a for a in result.assessments if a.event_key == bundle.event_key)),
            ("links", tuple(link for link in result.links if link.target_claim_key in keys)),
            ("conflicts", tuple(c for c in result.conflicts if set(c.claim_keys) <= set(keys))),
            ("lineage", tuple(row for row in result.lineage if row.doc_version_id in bundle.current_doc_version_ids)),
            ("coverage_gaps", tuple(g for g in result.validation.coverage_gaps
                                    if g.doc_version_id is None or g.doc_version_id in bundle.current_doc_version_ids)),
        ):
            same(getattr(bundle, field), expected, "bundle." + field)
    return claims, refs
