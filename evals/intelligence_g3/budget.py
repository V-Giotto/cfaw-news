"""Separate deterministic presentation planner; never changes scores or G2 facts."""

import unicodedata
from collections import Counter

from cfaw_news.retrieval import tokenize

from evals.intelligence_g2.contracts import data, digest

from .budget_contracts import (
    BriefingPlan,
    BudgetConfig,
    BudgetInput,
    CoverageDiagnostics,
    DomainCoverage,
    ReadingEstimate,
    ReadingRule,
)
from .contracts import fail
from .fact_signature import policy
from .history_contracts import HistoryConfig
from .history_contracts import parse_history as parse
from .rankers import _claims
from .ranking_contracts import RankingConfig
from .revisit import _history_features

PROFILES = {"focus60-radar40-v1": 60, "focus70-radar30-v1": 70, "focus80-radar20-v1": 80}
STATUSES = ("covered", "partial", "failed", "unknown", "service_offline")


def validate_input(value):
    """Bind the complete ranking to its context and independently check hard gates.

    Stage-one score computation is not repeated. Its exact rows are retained and
    hashed. Eligibility/protection cannot be supplied by an unbound ranking row.
    """
    source, ranked = value.history_input, value.ranking
    replay = source.replay
    config_hash = digest(dict(history=data(HistoryConfig()), base=data(RankingConfig()),
                              fact_signature=policy()))
    pool_hash = digest(sorted((c.event.event_key, c.event.event_revision, c.rule_item.item_id,
                               c.snapshot.snapshot_id, c.g2_view_sha256) for c in replay.candidates))
    if (ranked.input_sha256 != digest(source) or ranked.config != HistoryConfig()
            or ranked.base_config != RankingConfig() or ranked.config_sha256 != config_hash
            or ranked.algorithm_version != f"g3-{ranked.algorithm_id}-revisit-v1"
            or ranked.candidate_pool_sha256 != pool_hash
            or ranked.comparison_sha256 != digest(dict(input_sha256=digest(source),
                config_sha256=config_hash, candidate_pool_sha256=pool_hash))
            or ranked.as_of != replay.as_of
            or ranked.persona_version_id != replay.persona.persona.persona_version_id
            or ranked.attention_budget_seconds != replay.attention_budget_seconds):
        fail("G3_PLAN_INPUT_MISMATCH", "ranking_context")
    candidates = {c.event.event_key: c for c in replay.candidates}
    if (len(ranked.events) != len(candidates)
            or {r.event_key for r in ranked.events} != set(candidates)
            or [r.rank for r in ranked.events] != list(range(1, len(candidates) + 1))):
        fail("G3_PLAN_INPUT_MISMATCH", "complete_ranked_pool")
    for row in ranked.events:
        candidate = candidates[row.event_key]
        if (row.event_revision != candidate.event.event_revision
                or row.item_id != candidate.rule_item.item_id
                or row.snapshot_id != candidate.snapshot.snapshot_id
                or row.g2_view_sha256 != candidate.g2_view_sha256
                or row.g2_tier_candidate != candidate.rule_item.tier_candidate):
            fail("G3_PLAN_INPUT_MISMATCH", "ranking_identity")
        block = []
        item = candidate.rule_item
        if item.tier_candidate == "hold":
            block.append("g2_hold")
        if item.evidence_status == "insufficient" or candidate.bundle.status == "insufficient":
            block.append("g2_evidence_insufficient")
        if not _claims(candidate, replay.evidence, "/replay/evidence"):
            block.append("no_cited_attributed_claim")
        history, _, _ = _history_features(source, candidate, HistoryConfig())
        if (row.block_reasons != tuple(block) or row.eligible != (not block)
                or row.history != history
                or row.protected != (not block and history.promotion != "none")):
            fail("G3_PLAN_INPUT_MISMATCH", "evidence_or_update_protection")
    ordered = sorted(ranked.events, key=lambda r: (
        not r.eligible, not r.protected if ranked.algorithm_id in {"b4", "p1"} else False,
        -r.score, r.event_key, r.event_revision, r.item_id))
    if list(ranked.events) != ordered:
        fail("G3_PLAN_INPUT_MISMATCH", "stage_one_order")


def display_units(text):
    """Each Han codepoint is one unit; other Unicode letters/digits form runs.

    Punctuation, whitespace, symbols and combining marks add no unit. Combining
    marks do not split a word. No locale, clock, random seed or tokenizer model.
    """
    units, in_word = 0, False
    for char in text:
        code = ord(char)
        han = (0x3400 <= code <= 0x4DBF or 0x4E00 <= code <= 0x9FFF
               or 0xF900 <= code <= 0xFAFF or 0x20000 <= code <= 0x323AF)
        category = unicodedata.ucd_3_2_0.category(char)
        if han:
            units, in_word = units + 1, False
        elif category[0] in {"L", "N"}:
            units += not in_word
            in_word = True
        elif category[0] != "M":
            in_word = False
    return units


def _strings(value):
    """Visible scope values; grounding IDs/offsets are pointers, not reading text."""
    if hasattr(value, "raw_value"):
        return [value.raw_value]
    if isinstance(value, str):
        return [value]
    if isinstance(value, tuple):
        return [s for v in value for s in _strings(v)]
    return []


def estimates(candidate, index, rule=None):
    """Project existing rule blocks. Evidence/caveats survive every projection.

    Radar omits only the explicitly labelled inference. Minimum also omits the
    redundant what_happened block. No substring/claim/quote truncation is allowed.
    """
    rule = parse(ReadingRule, data(rule)) if rule is not None else ReadingRule()
    item = candidate.rule_item
    root = f"/history_input/replay/candidates/{index}/rule_item"
    blocks = []
    if item.headline:
        blocks.append((root + "/headline", [item.headline.text]))
    selected = set(item.selected_claim_keys)
    for si, summary in enumerate(item.claim_summaries):
        if summary.claim_key in selected:
            texts = [summary.statement.text, summary.attribution, summary.verification_state,
                     summary.lifecycle, *summary.limitations]
            texts += [s for name in type(summary.scope).model_fields
                      for s in _strings(getattr(summary.scope, name))]
            blocks.append((f"{root}/claim_summaries/{si}", texts))
    blocks += [(f"{root}/risks/{i}", [r.text]) for i, r in enumerate(item.risks)]
    blocks += [(f"{root}/uncertainties/{i}", [t]) for i, t in enumerate(item.uncertainties)]
    if item.status_text:
        blocks.append((root + "/status_text", [item.status_text]))
    mandatory = list(blocks)
    if item.what_happened:
        blocks.append((root + "/what_happened", [item.what_happened.text]))
    radar = list(blocks)
    if item.why_it_matters:
        blocks.append((root + "/why_it_matters", [item.why_it_matters.kind,
            item.why_it_matters.text, *item.why_it_matters.limitations]))
    all_refs = tuple(p for p, _ in blocks)
    citations = len(set(item.evidence_ref_ids))
    result = []
    for name, subset in (("focus", blocks), ("radar", radar), ("minimum", mandatory)):
        refs = tuple(p for p, _ in subset)
        units = sum(display_units(t) for _, texts in subset for t in texts)
        seconds = (rule.item_overhead_seconds
                   + (units + rule.units_per_second - 1) // rule.units_per_second
                   + citations * rule.citation_seconds)
        result.append(ReadingEstimate(projection=name, display_units=units,
            citation_count=citations, seconds=seconds, content_refs=refs,
            omitted_refs=tuple(p for p in all_refs if p not in refs)))
    return tuple(result)


def _reason(code, refs=(), required=None, available=None):
    return dict(code=code, input_refs=list(refs), required_seconds=required,
                available_seconds=available)


def _ratio(numerator, denominator):
    return numerator / denominator if denominator else None


def _coverage_status(statuses):
    """Non-covered observations conservatively veto overlapping covered claims."""
    noncovered = set(statuses) - {"covered"}
    if not statuses:
        return "unknown"
    if len(noncovered) == 1:
        return next(iter(noncovered))
    return "partial" if noncovered else "covered"


def _coverage_spans(segments, predicate):
    result = []
    for segment in segments:
        if not predicate(segment):
            continue
        start, end = segment["start_at"], segment["end_at"]
        if result and result[-1]["end_at"] == start:
            result[-1]["end_at"] = end
        else:
            result.append(dict(start_at=start, end_at=end))
    return tuple(result)


def _source_coverage(source_id, indexed_windows, start, end):
    point = start == end
    relevant = [(i, w) for i, w in indexed_windows if w.source_id == source_id and (
        w.start_at <= start <= w.end_at if point else max(start, w.start_at) < min(end, w.end_at))]
    boundaries = sorted({start, end, *(max(start, w.start_at) for _, w in relevant),
                         *(min(end, w.end_at) for _, w in relevant)})
    cells = [(start, end)] if point else list(zip(boundaries, boundaries[1:]))
    segments = []
    for left, right in cells:
        active = [(i, w) for i, w in relevant if w.start_at <= left and right <= w.end_at]
        statuses = sorted({w.status for _, w in active})
        reasons = []
        if not active:
            reasons.append("no_observation_for_requested_interval")
        elif statuses == ["covered"]:
            reasons.append("covered_window_union")
        else:
            reasons.append("explicit_noncovered_observation")
            if len(statuses) > 1:
                reasons.append("overlapping_noncovered_observation_veto")
        segments.append(dict(start_at=left, end_at=right, status=_coverage_status(statuses),
            observed_statuses=tuple(statuses),
            window_refs=tuple(f"/history_input/replay/source_coverage/{i}" for i, _ in active),
            reason_codes=tuple(reasons)))
    effective = {s["status"] for s in segments}
    status = next(iter(effective)) if len(effective) == 1 else "partial"
    return dict(source_id=source_id, status=status,
        observed_statuses=tuple(sorted({w.status for _, w in relevant})),
        window_refs=tuple(f"/history_input/replay/source_coverage/{i}" for i, _ in relevant),
        segments=tuple(segments),
        confirmed_intervals=_coverage_spans(segments, lambda s: s["status"] == "covered"),
        unconfirmed_intervals=_coverage_spans(segments, lambda s: s["status"] != "covered"),
        unobserved_intervals=_coverage_spans(segments, lambda s: not s["window_refs"]))


def _coverage(replay):
    """Retain raw observations and separately diagnose this query's time union."""
    windows = replay.source_coverage
    observed = {w.source_id for w in windows}
    expected = {p.source_id for c in replay.candidates for p in c.rule_item.source_pointers}
    sources = tuple(_source_coverage(s, tuple(enumerate(windows)), replay.time_window_start,
                                    replay.time_window_end) for s in sorted(observed | expected))
    counts = Counter(w.status for w in windows)
    statuses = sorted({s["status"] for s in sources}) or ["unknown"]
    return data(CoverageDiagnostics(requested_start_at=replay.time_window_start,
        requested_end_at=replay.time_window_end, windows=windows,
        status_counts={s: counts[s] for s in STATUSES}, source_count=len(sources),
        window_count=len(windows), missing_source_ids=tuple(sorted(expected - observed)),
        unobserved_source_ids=tuple(s["source_id"] for s in sources if not s["window_refs"]),
        sources=sources, effective_statuses=tuple(statuses), has_gap=any(s != "covered" for s in statuses)))


def _domain_coverage(replay, eligible, shown, by_key):
    """One denominator unit per exact lexical query, with every raw label retained."""
    groups = {}
    for i, label in enumerate(replay.persona.persona.domain_interests):
        query = tuple(sorted(set(tokenize(label))))
        groups.setdefault(query, []).append((i, label))
    texts = {}
    for key in eligible:
        item = by_key[key][1].rule_item
        text = "\n".join([item.headline.text if item.headline else "",
            *(s.statement.text for s in item.claim_summaries if s.claim_key in item.selected_claim_keys)])
        texts[key] = set(tokenize(text))
    domains = []
    for tokens, labels in sorted(groups.items()):
        matching = {key for key in eligible if tokens and set(tokens) <= texts[key]}
        domains.append(data(DomainCoverage(domain=labels[0][1],
            domain_key="g3:domain-query:" + digest(list(tokens)), query_tokens=tokens,
            labels=tuple(label for _, label in labels),
            input_refs=tuple(f"/history_input/replay/persona/persona/domain_interests/{i}" for i, _ in labels),
            reason_codes=("canonical_lexical_query_not_semantic_domain",) if tokens else (
                "canonical_lexical_query_not_semantic_domain", "empty_interest_query_unmatchable"),
            eligible_events=len(matching), presented_events=len(matching & shown),
            ratio=_ratio(len(matching & shown), len(matching)))))
    return domains


def derive(value):
    """Produce plan fields without invoking any ranker or modifying its rows."""
    replay, ranking, config = value.history_input.replay, value.ranking, value.config
    budget = replay.attention_budget_seconds
    focus_target = budget * PROFILES[config.profile] // 100
    radar_target = budget - focus_target
    by_key = {c.event.event_key: (i, c) for i, c in enumerate(replay.candidates)}
    decisions, display_order = {}, []
    focus_used = radar_used = 0
    for row in ranking.events:
        ci, candidate = by_key[row.event_key]
        decisions[row.event_key] = dict(rank=row.rank, event_key=row.event_key,
            snapshot_id=row.snapshot_id, status="not_displayed", tier=None, protected=row.protected,
            estimated_read_seconds=0, estimates=[data(e) for e in estimates(candidate, ci, config.reading_rule)],
            chosen_projection=None, content_refs=[], omitted_refs=[], reasons=[])
        if not row.eligible:
            decisions[row.event_key].update(status="constraint_excluded", reasons=[
                _reason(code, (f"/ranking/events/{row.rank - 1}/block_reasons",))
                for code in row.block_reasons])

    def attempt(row, tier, available, protected=False):
        nonlocal focus_used, radar_used
        entry = decisions[row.event_key]
        full = next(e for e in entry["estimates"] if e["projection"] == tier)
        minimum = entry["estimates"][-1]
        chosen = full if full["seconds"] <= available else (
            minimum if minimum["seconds"] <= available else None)
        refs = ("/config", f"/ranking/events/{row.rank - 1}")
        if protected:
            entry["reasons"].append(_reason("protected_update_priority", refs))
        if chosen is None:
            entry["reasons"].append(_reason(f"{tier}_share_insufficient", refs,
                minimum["seconds"], available))
            if minimum["seconds"] > budget:
                entry["reasons"].append(_reason("minimum_exceeds_total_budget", refs,
                    minimum["seconds"], budget))
            if protected:
                entry["reasons"].append(_reason("protected_budget_unmet", refs,
                    minimum["seconds"], available))
            return False
        truncated = chosen["projection"] == "minimum" and chosen["content_refs"] != full["content_refs"]
        entry.update(status="truncated" if truncated else tier, tier=tier,
            chosen_projection=chosen["projection"], estimated_read_seconds=chosen["seconds"],
            content_refs=chosen["content_refs"], omitted_refs=chosen["omitted_refs"])
        entry["reasons"].append(_reason(f"{tier}_budget_fit", refs, chosen["seconds"], available))
        if truncated:
            entry["reasons"].append(_reason("detail_blocks_omitted", chosen["omitted_refs"],
                full["seconds"], available))
        if protected and focus_used + chosen["seconds"] > focus_target:
            entry["reasons"].append(_reason("protected_borrows_radar_share", refs))
        if tier == "focus":
            focus_used += chosen["seconds"]
        else:
            radar_used += chosen["seconds"]
        display_order.append(row.event_key)
        return True

    # Selection priority is explicit and independent from stage-one scores/order.
    # Protection never bypasses eligibility or the total time limit.
    for row in ranking.events:
        if row.eligible and row.protected:
            attempt(row, "focus", budget - focus_used, protected=True)
    deferred = []
    for row in ranking.events:
        if row.eligible and not row.protected:
            if not attempt(row, "focus", max(0, focus_target - focus_used)):
                deferred.append(row)
    for row in deferred:
        attempt(row, "radar", max(0, min(radar_target - radar_used,
                                        budget - focus_used - radar_used)))

    events = [decisions[row.event_key] for row in ranking.events]
    eligible = {r.event_key for r in ranking.events if r.eligible}
    shown = set(display_order)
    domains = _domain_coverage(replay, eligible, shown, by_key)
    presented_domains = sum(d["presented_events"] > 0 for d in domains)
    used = focus_used + radar_used
    diagnostics = dict(budget_seconds=budget, focus_target_seconds=focus_target,
        radar_target_seconds=radar_target, focus_used_seconds=focus_used, radar_used_seconds=radar_used,
        protected_borrowed_seconds=max(0, focus_used - focus_target), used_seconds=used,
        unused_seconds=budget - used, utilization=used / budget, candidate_count=len(events),
        eligible_event_count=len(eligible), presented_event_count=len(shown),
        event_breadth=_ratio(len(shown), len(eligible)),
        breadth_unit="unique_g2_event_keys_not_independent_research_samples",
        domain_coverage=domains, declared_domain_count=len(domains),
        presented_domain_count=presented_domains,
        declared_domain_coverage=_ratio(presented_domains, len(domains)),
        truncated_event_keys=[e["event_key"] for e in events if e["status"] == "truncated"],
        not_displayed_event_keys=[e["event_key"] for e in events if e["status"] == "not_displayed"],
        excluded_event_keys=[e["event_key"] for e in events if e["status"] == "constraint_excluded"],
        unmet_protected_event_keys=[e["event_key"] for e in events if e["protected"] and e["tier"] is None],
        reason_counts=dict(sorted(Counter(r["code"] for e in events for r in e["reasons"]).items())))
    return dict(input_sha256=digest(value), ranking_sha256=digest(ranking), config_sha256=digest(config),
        events=events, display_order=display_order,
        archive_snapshot_ids=[r.snapshot_id for r in ranking.events], coverage=_coverage(replay),
        diagnostics=diagnostics)


def plan_briefing(history_input, ranking, config=None):
    """Stage two: consume an already completed PR3 ranking and keep it intact."""
    value = parse(BudgetInput, dict(history_input=data(history_input), ranking=data(ranking),
        config=data(config) if config is not None else data(BudgetConfig())))
    return parse(BriefingPlan, dict(input=data(value), **derive(value)))
