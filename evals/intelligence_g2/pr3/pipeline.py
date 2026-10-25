"""Pure evidence assembly; no briefing generation, IO or model calls."""

from .contracts import (
    ClaimAssessment,
    CoverageGap,
    EvidenceBundle,
    EvidenceResult,
    EvidenceState,
    PR3Diagnostic,
    data,
    digest,
)
from .extract import extract_claims
from .history import find_transitions, memberships, namespace, reconcile
from .lineage import build_source_lineage
from .relations import assess_claim_relations


def coverage_gaps(replay):
    windows = replay.context.source_coverage
    gaps = []
    if not windows:
        gaps.append(CoverageGap(code="coverage_unknown"))
    known = {w.source_id for w in windows}
    for source_id in sorted({d.candidate.source_id for d in replay.visible_documents} - known):
        gaps.append(CoverageGap(code="source_coverage_unknown", source_id=source_id))
    for w in windows:
        if w.status != "covered":
            gaps.append(CoverageGap(code="source_" + w.status, source_id=w.source_id,
                                    coverage_window_id=w.coverage_window_id))
    return tuple(gaps)


def bundle_digest(bundle):
    return digest({k: v for k, v in data(bundle).items() if k not in {"bundle_id", "bundle_sha256"}})


def assemble(value, config):
    replay = value.grouping_input.replay_input
    cursor = value.grouping_input.cursor
    extracted = extract_claims(replay_input=replay, events=value.grouping_result.events, config=config)
    current, citations, archived, all_refs = reconcile(value, extracted, config)
    owners, added_memberships = memberships(value, archived, all_refs)
    lineage = build_source_lineage(replay_input=replay, grouping_result=value.grouping_result, config=config)
    related = assess_claim_relations(claims=current, lineage=lineage, history={"owners": owners}, config=config)
    transitions, history_gaps = find_transitions(value, current, archived, all_refs, owners)
    prior = value.previous_state
    all_transitions = (prior.transitions if prior else ()) + transitions
    status = {key: "superseded" if t.kind == "corrects" else "retracted"
              for t in all_transitions for key in t.from_claim_keys}
    disputed = {key for c in related.conflicts for key in c.claim_keys}
    current_keys = {c.claim_key for c in current}
    assessments = []
    for key, event_key in sorted(owners.items()):
        claim = archived[key]
        lifecycle = status.get(key, "current" if key in current_keys else "historical")
        verification = ("retracted" if lifecycle == "retracted" else "disputed" if key in disputed else
            "unverified" if claim.attribution.attribution_kind == "secondary_material" else "source_attributed")
        assessments.append(ClaimAssessment(claim_key=key, event_key=event_key, as_of=cursor.as_of,
            verification_state=verification, lifecycle=lifecycle,
            evidence_link_ids=tuple(link.link_key for link in related.links if link.target_claim_key == key),
            limitations=claim.limitations + (("historical_not_current_evidence",) if key not in current_keys else ())))
    gaps = coverage_gaps(replay) + extracted.coverage_gaps + lineage.coverage_gaps + history_gaps
    gaps = tuple(sorted({digest(g): g for g in gaps}.values(), key=lambda g: digest(g)))
    bundles = []
    for event in value.grouping_result.events:
        keys = tuple(sorted(k for k, owner in owners.items() if owner == event.event_key))
        current_members = tuple(k for k in keys if k in current_keys)
        docs = set(event.member_doc_version_ids)
        bundle = EvidenceBundle(bundle_id="pending", event_key=event.event_key,
            event_revision=event.event_revision, as_of=cursor.as_of,
            status="assembled" if current_members else "insufficient",
            current_doc_version_ids=event.member_doc_version_ids, current_claim_keys=current_members,
            historical_claim_keys=tuple(k for k in keys if k not in current_keys),
            assessments=tuple(a for a in assessments if a.event_key == event.event_key),
            lineage=tuple(s for s in lineage.sources if s.doc_version_id in docs),
            links=tuple(link for link in related.links if link.target_claim_key in keys),
            conflicts=tuple(c for c in related.conflicts if set(c.claim_keys) <= set(keys)),
            coverage_gaps=tuple(g for g in gaps if g.doc_version_id is None or g.doc_version_id in docs),
            uncertainties=("independence_unknown", "semantic_truth_not_evaluated", "observed_sources_only"),
            bundle_sha256="0" * 64)
        sha = bundle_digest(bundle)
        bundles.append(bundle.model_copy(update={"bundle_id": "g2:bundle:" + sha, "bundle_sha256": sha}))
    state = EvidenceState(namespace=namespace(value, config), config_sha256=digest(config), cursor=cursor,
        previous_state_sha256=digest(prior) if prior else None,
        claims=tuple(archived[k] for k in sorted(archived)),
        citations=tuple(all_refs[k] for k in sorted(all_refs)),
        transitions=all_transitions, memberships=(prior.memberships if prior else ()) + added_memberships,
        assessments=(prior.assessments if prior else ()) + tuple(assessments),
        grouping_state_sha256=digest(value.grouping_result.next_state))
    return EvidenceResult(cursor=cursor, claims=current, citations=citations, assessments=tuple(assessments),
        memberships=added_memberships, links=related.links, lineage=lineage.sources, conflicts=related.conflicts,
        transitions=transitions, bundles=tuple(bundles), next_state=state,
        validation=PR3Diagnostic(ok=True, counts={"claims": len(current), "citations": len(citations),
            "bundles": len(bundles), "conflicts": len(related.conflicts), "transitions": len(transitions),
            "comparisons": related.comparisons, "coverage_gaps": len(gaps), "confirmed_independent_support": 0},
            coverage_gaps=gaps))


def run_evidence_step(*, evidence_input, config):
    from .validate_output import checked_input, validate_output

    value, config = checked_input(evidence_input, config)
    result = assemble(value, config)
    validate_output(result, value, config)
    return result
