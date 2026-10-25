"""Measured denominators are separate from unavailable and independent research."""

from collections import Counter, defaultdict

from .contracts import MetricValue


def ratio(n, d, reason="zero_denominator"):
    return MetricValue(
        numerator=n,
        denominator=d,
        value=n / d if d else None,
        status="measured" if d else "unavailable",
        reason=None if d else reason,
    )


def not_evaluated(reason):
    return MetricValue(
        numerator=0, denominator=0, value=None, status="not_evaluated", reason=reason
    )


def pair_counts(events, reference):
    owner = {m: e.event_key for e in events for m in e.member_doc_version_ids}
    counts = Counter(tp=0, fp=0, fn=0, tn=0, reference_uncertain=0, reference_missing=0)
    for pair in reference:
        left, right, label = pair
        if label == "uncertain":
            counts["reference_uncertain"] += 1
            continue
        if left not in owner or right not in owner:
            counts["fn" if label else "reference_missing"] += 1
            continue
        same = owner[left] == owner[right]
        counts["tp" if same and label else "fp" if same else "fn" if label else "tn"] += 1
    return dict(counts)


def summarize(records):
    items = [i for r in records for i in r.rule.items]
    claims = [c for r in records for c in r.evidence.claims]
    refs = [c for r in records for c in r.evidence.citations]
    assessments = [a for r in records for a in r.expression.assessments]
    attempted = sum(a.status != "skipped" for a in assessments)
    calls = [t for r in records for t in r.call_observations]
    old = [c["claim"] for r in records for c in r.old_claims]
    reservations = defaultdict(int)
    for record in records:
        state = record.expression.next_state
        reservations[state.namespace] = max(
            reservations[state.namespace], state.response_bytes_reserved
        )
    return dict(
        mock_calls=sum(t.mock_calls for t in calls),
        request_bytes=sum(t.request_bytes for t in calls),
        response_bytes=sum(t.response_bytes for t in calls),
        response_bytes_reserved=sum(reservations.values()),
        usage_origins=dict(Counter(t.usage_origin for t in calls)),
        mock_total_tokens_known=sum((t.usage or {}).get("total_tokens", 0) for t in calls),
        mock_token_unknown_calls=sum(
            bool(t.mock_calls and (not t.usage or "total_tokens" not in t.usage)) for t in calls
        ),
        input_tokens=None,
        pr1_excerpt_diagnostic=dict(
            claims=len(old),
            characters=sum(len(c["statement"]) for c in old),
            semantic_support="not_evaluated",
        ),
        pr3_paragraph_diagnostic=dict(
            claims=len(claims),
            characters=sum(len(c.statement) for c in claims),
            known_scope_dimensions=sum(
                sum(
                    getattr(c.scope, dimension) is not None
                    for dimension in (
                        "task",
                        "dataset",
                        "baseline",
                        "protocol",
                        "hardware",
                        "target_version",
                    )
                )
                for c in claims
            ),
        ),
        items=len(items),
        claims=len(claims),
        citations=len(refs),
        unique_claims=len({c.claim_key for c in claims}),
        unique_citations=len({c.ref_id for c in refs}),
        tiers=dict(Counter(i.tier_candidate for i in items)),
        source_independence=dict(
            Counter(v.independence for r in records for v in r.evidence.lineage)
        ),
        expression_acceptance=ratio(sum(a.status == "accepted" for a in assessments), attempted),
        errors=dict(Counter(a.code for a in assessments if a.code)),
        expression_statuses=dict(Counter(a.status for a in assessments)),
        accepted_styles=dict(
            Counter(
                p.style_id
                for r in records
                for p in r.expression.presentations
                if p.selection == "mock_closed"
            )
        ),
        historical_claim_observations=sum(
            len(b.historical_claim_keys) for r in records for b in r.evidence.bundles
        ),
        merge_split_observations=dict(
            Counter(t.kind for r in records for t in r.grouping.next_state.transitions)
        ),
        structural_locator=ratio(len(refs), len(refs)),
        coverage_gap_observations=sum(len(r.evidence.validation.coverage_gaps) for r in records),
        estimated_read_seconds=sum(r.estimated_read_seconds for r in records),
        reading_overrun_seconds=sum(
            max(0, r.estimated_read_seconds - r.reading_budget_seconds) for r in records
        ),
        independently_supported=sum(
            a.verification_state == "independently_supported"
            for r in records
            for a in r.evidence.assessments
        ),
        supports=sum(v.direction == "supports" for r in records for v in r.evidence.links),
        refutes=sum(v.direction == "refutes" for r in records for v in r.evidence.links),
        independent_semantic_support=not_evaluated("independent_research_not_evaluated"),
        underlying_truth=not_evaluated("source_attribution_is_not_truth"),
        model_calls=0,
        external_requests=0,
        billed_cost=0,
    )
