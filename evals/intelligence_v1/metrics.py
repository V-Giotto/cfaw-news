"""Pure post-prediction metrics; no dataset IO or prediction imports."""

import math
from datetime import timedelta

from .contracts import MetricValue
from .temporal import format_instant


def ratio(numerator, denominator, reason):
    result = {"numerator": numerator, "denominator": denominator,
              "value": numerator/denominator if denominator else None,
              "undefined_reason": None if denominator else reason}
    MetricValue.model_validate(result)
    return result


def unavailable(reason):
    return ratio(0, 0, reason)


def ranking_metrics(items, mapping, labels, *, k):
    visible = {e: label for e, label in labels.items() if e in set(mapping.values())}
    focus = {e for e, label in visible.items() if label["tier"] == "focus"}
    seen, dcg = set(), 0.0
    for position, item in enumerate(items[:k], 1):
        event = mapping.get(item["representative_doc_version_id"])
        if event in seen:
            continue
        seen.add(event)
        dcg += (2**visible.get(event, {}).get("graded_relevance", 0)-1)/math.log2(position+1)
    grades = sorted((label["graded_relevance"] for label in visible.values()), reverse=True)
    ideal = sum((2**g-1)/math.log2(i+2) for i, g in enumerate(grades[:k]))
    return {f"ImportantEventRecall@{k}": ratio(len(seen & focus), len(focus),
                                                "no_visible_gold_focus_events"),
            f"EventnDCG@{k}": ratio(dcg, ideal, "no_positive_gold_gain")}


def binary_metrics(predicted, positive, eligible):
    if predicted is None:
        return {key: unavailable("prediction_not_emitted") for key in ("precision", "recall", "f1")}
    predicted, positive = set(predicted) & set(eligible), set(positive) & set(eligible)
    tp, fp, fn = len(predicted & positive), len(predicted-positive), len(positive-predicted)
    return {"precision": ratio(tp, tp+fp, "no_predicted_positives"),
            "recall": ratio(tp, tp+fn, "no_reference_positives"),
            "f1": ratio(2*tp, 2*tp+fp+fn, "no_positive_pairs")}


def aggregate_metrics(values):
    defined = [v for v in values if v["value"] is not None]
    n, d = sum(v["numerator"] for v in defined), sum(v["denominator"] for v in defined)
    return {"macro": sum(v["value"] for v in defined)/len(defined) if defined else None,
            "micro": n/d if d else None, "numerator": n, "denominator": d,
            "defined_count": len(defined), "undefined_count": len(values)-len(defined)}


def coverage_gaps(context):
    gaps, intervals = [], {}
    for window in context.source_coverage:
        start = max(window.start_at, context.time_window_start)
        end = min(window.end_at, context.time_window_end)
        if window.status == "covered" or end <= start:
            continue
        gaps.append({"source_id": window.source_id, "status": window.status,
            "start_at": format_instant(start), "end_at": format_instant(end),
            "reason": window.reason})
        intervals.setdefault(window.source_id, []).append((start, end))
    seconds = 0.0
    for rows in intervals.values():
        end = None
        for start, stop in sorted(rows):
            if end is None or start >= end:
                seconds += (stop-start).total_seconds()
            elif stop > end:
                seconds += (stop-end).total_seconds()
            end = max(end, stop) if end is not None else stop
    return {"coverage_gap_count": len(gaps), "gaps": gaps,
            "unknown_source_seconds": seconds, "interpretation": "gaps_are_unknown_not_no_updates"}


def step_metrics(row, context, mapping, labels, *, k, evidence_times, historical_mapping):
    items, presented = row["ranked_items"], row["presentation"]["presented_items"]
    metrics = ranking_metrics(items, mapping, labels, k=k)
    visible_events = set(mapping.values())
    focus = {e for e, label in labels.items() if label["tier"] == "focus" and e in visible_events}
    mapped = [mapping.get(i["representative_doc_version_id"]) for i in presented]
    hit = set(mapped) & focus
    budget = row["presentation"]["budget_seconds"]
    metrics[f"ImportantEventRecall@budget:{budget}s"] = ratio(len(hit), len(focus),
                                                              "no_visible_gold_focus_events")
    metrics[f"ImportantMissRate@budget:{budget}s"] = ratio(len(focus-hit), len(focus),
                                                           "no_visible_gold_focus_events")
    if any(e is None for e in mapped):
        metrics["DuplicateExposureRate"] = unavailable("unmapped_presented_events")
    else:
        metrics["DuplicateExposureRate"] = ratio(len(mapped)-len(set(mapped)), len(mapped),
                                                  "no_presented_cards")
    historical_events = set(historical_mapping.values())
    repeated = [e for e in mapped if e in historical_events and e in labels
                and labels[e]["material_change"] != "insufficient"]
    unchanged = [e for e in repeated if labels[e]["material_change"] == "no_change"]
    metrics["RepeatedNoChangeRate"] = ratio(len(unchanged), len(repeated),
                                             "no_comparable_repeated_presentations")
    for days in (1, 3, 7):
        lower = max(context.time_window_start, context.as_of-timedelta(days=days))
        eligible = {e for e in focus if any(lower <= evidence_times[key] <= context.time_window_end
            for key in labels[e]["supporting_doc_version_ids"] if key in evidence_times)}
        metrics[f"RevisitCoverage@{days}d@budget:{budget}s"] = ratio(
            len(set(mapped) & eligible), len(eligible), "no_visible_gold_focus_events_in_window")
    # A new-text proxy is not a meaningful-update or correction classifier.
    proxy, comparable = set(), set()
    for item in items:
        event = mapping.get(item["representative_doc_version_id"])
        delta = item["score_components"].get("text_delta")
        if (event in labels and labels[event]["material_change"] != "insufficient"
                and delta in {"new_text", "no_change"}):
            comparable.add(event)
            if delta == "new_text":
                proxy.add(event)
    positive = {e for e, label in labels.items()
                if label["material_change"] in {"meaningful_update", "correction", "withdrawal"}}
    proxy_metrics = binary_metrics(proxy if comparable else None, positive, comparable)
    insufficient = {e for e, label in labels.items() if label["material_change"] == "insufficient"}
    if not comparable and any(mapping.get(i["representative_doc_version_id"]) in insufficient
                              and i["score_components"].get("text_delta") in {"new_text", "no_change"}
                              for i in items):
        proxy_metrics = {name: unavailable("reference_change_insufficient")
                         for name in ("precision", "recall", "f1")}
    for name, result in proxy_metrics.items():
        metrics[f"NewTextProxyAgainstReference.{name}"] = result
    for kind in ("MaterialChange", "Correction", "Withdrawal"):
        for name, result in binary_metrics(None, positive, set(labels)).items():
            metrics[f"{kind}.{name}"] = result
    metrics["ClaimCitationValidity"] = unavailable("no_output_claim_citations")
    metrics["EvidenceSupportPrecision"] = unavailable("not_measured")
    metrics["IndependenceErrorRate"] = unavailable("no_predicted_independent_groups")
    return metrics, {"hit_focus_event_ids": sorted(hit), "missed_focus_event_ids": sorted(focus-hit),
        "presented_reference_event_ids": mapped, "repeated_reference_event_ids": repeated,
        "reference_change_positive_count": len(positive),
        "reference_change_insufficient_event_ids": sorted(insufficient),
        "proxy_comparable_event_ids": sorted(comparable),
        "supporting_evidence_presented": {e: sorted(set(label["supporting_doc_version_ids"]) & {
            key for i in presented for key in i["doc_version_ids"]}) for e, label in labels.items()},
        "miss_reasons": {e: miss_reason(e, row, mapping) for e in sorted(focus-hit)}}


def miss_reason(event, row, mapping):
    members = {v for i in row["ranked_items"] for v in i["doc_version_ids"] if mapping.get(v) == event}
    representatives = {i["representative_doc_version_id"] for i in row["ranked_items"]}
    if not members:
        return "not_visible_or_not_recalled"
    if not members & representatives:
        return "merged_under_other_representative"
    return "ranking_and_budget_cutoff"
