"""Post-prediction metrics; no prediction module imports reference labels."""

import math
from collections import defaultdict

from evals.intelligence_g2.contracts import data

from .contracts import fail
from .pr5_contracts import Metric


def ratio(numerator, denominator, samples, families, reason="zero_evaluable_denominator"):
    return data(Metric(numerator=numerator, denominator=denominator,
        value=numerator / denominator if denominator else None, sample_count=samples,
        event_family_count=len(families), undefined_reason=None if denominator else reason))


def measure(result, labels, days):
    rows = {r["event_key"]: r for r in result["ranking"]["events"]}
    reference = {r["event_key"]: r for r in labels}
    if (len(reference) != len(labels) or rows.keys() != reference.keys()
            or any((rows[k]["event_revision"], rows[k]["snapshot_id"]) !=
                   (r["event_revision"], r["snapshot_id"]) for k, r in reference.items())
            or not all(r["evaluable"] is True and type(r["important"]) is bool
                       and type(r["duplicate"]) is bool and r["gain"] in (0, 1, 2, 3)
                       and r["family_id"] for r in labels)):
        fail("G3_REFERENCE_MISMATCH", "complete_frozen_event_identity")
    shown = set(result["plan"]["display_order"])
    families = {r["family_id"] for r in labels}
    important = {k for k, r in reference.items() if r["important"]}
    samples = len(labels)
    m, support = {}, {}

    def put(name, n, d, reason="zero_evaluable_denominator", *, applicable=True, window=None):
        active_families = families if applicable else set()
        m[name] = ratio(n, d, samples if applicable else 0, active_families, reason)
        support[name] = dict(applicable=applicable, family_ids=sorted(active_families),
                             revisit_window_days=window,
                             sample_unit="evaluable_candidate_event_state_in_metric_scope")

    put("ImportantEventRecall@budget", len(shown & important), len(important))
    put("ImportantMissRate", len(important - shown), len(important))
    put("DuplicateExposureRate", sum(reference[k]["duplicate"] for k in shown), len(shown),
        "no_presented_events")
    order = [r["event_key"] for r in result["ranking"]["events"] if r["eligible"]][:10]
    dcg = sum((2 ** reference[k]["gain"] - 1) / math.log2(i + 2) for i, k in enumerate(order))
    ideal = sum((2 ** g - 1) / math.log2(i + 2) for i, g in enumerate(
        sorted((r["gain"] for r in labels), reverse=True)[:10]))
    put("nDCG@10", dcg, ideal, "no_positive_reference_gain")
    for name, kind in (("MaterialChangeRecall", "material"), ("CorrectionRecall", "correction"),
                       ("WithdrawalRecall", "withdrawal")):
        expected = {k for k, r in reference.items() if r["change_kind"] == kind}
        put(name, len(expected & shown), len(expected))
    for horizon in (1, 3, 7):
        put(f"RevisitCoverage@{horizon}d", len(important & shown) if days == horizon else 0,
            len(important) if days == horizon else 0,
            "no_evaluable_important_events_in_this_revisit_window" if days == horizon
            else "outside_revisit_window", applicable=days == horizon, window=horizon)
    d = result["plan"]["diagnostics"]
    put("EventBreadth", d["presented_event_count"], d["eligible_event_count"])
    put("DeclaredDomainCoverage", d["presented_domain_count"], d["declared_domain_count"],
        "no_declared_lexical_domains")
    put("BudgetUtilization", d["used_seconds"], d["budget_seconds"])
    put("ConstraintViolationRate", sum(not rows[k]["eligible"] for k in shown), len(shown),
        "no_presented_events")
    put("UnmetProtectedRate", len(d["unmet_protected_event_keys"]),
        sum(r["protected"] for r in rows.values()))
    put("ExplorationExposureProxy", sum(rows[k]["features"]["exploration"]["value"] > 0
                                         for k in shown), len(shown), "no_presented_events")
    failures = []
    for event in result["plan"]["events"]:
        key = event["event_key"]
        if key in important - shown or (key in shown and reference[key]["duplicate"]):
            failures.append(dict(event_key=key, family_id=reference[key]["family_id"],
                kind="important_miss" if key not in shown else "duplicate_presented",
                evaluable=True, retained_in_denominator=True, protected=event["protected"],
                reasons=event["reasons"], job_id=result["job_id"], case_id=result["job"]["case_id"],
                reference=reference[key]))
    return dict(job_id=result["job_id"], **result["job"], revisit_days=days,
                family_ids=sorted(families), metrics=m, metric_support=support,
                dataset_support=dict(sample_count=samples, event_family_count=len(families),
                                     family_ids=sorted(families))), failures


def aggregate(measurements):
    groups = defaultdict(list)
    for row in measurements:
        for axis, cell in (("all", "all"), ("budget", str(row["budget"])),
                           ("revisit", str(row["revisit_days"]))):
            if axis != "revisit" or row["revisit_days"] is not None:
                groups[(row["variant"], axis, cell)].append(row)
    out = []
    for (variant, axis, cell), rows in sorted(groups.items()):
        families = {f for row in rows for f in row["family_ids"]}
        metrics, support = {}, {}
        for name in rows[0]["metrics"]:
            values = [r["metrics"][name] for r in rows]
            active_families = {f for row in rows for f in row["metric_support"][name]["family_ids"]}
            active_samples = sum(v["sample_count"] for v in values)
            metrics[name] = ratio(sum(v["numerator"] for v in values),
                sum(v["denominator"] for v in values), active_samples, active_families,
                "no_evaluable_denominator_in_this_cell" if active_samples
                else "no_applicable_samples_in_this_cell")
            support[name] = dict(family_ids=sorted(active_families),
                applicable_measurements=sum(row["metric_support"][name]["applicable"] for row in rows))
        out.append(dict(variant=variant, axis=axis, cell=cell, metrics=metrics,
                        case_budget_observations=len(rows), family_ids=sorted(families),
                        metric_support=support, dataset_support=dict(
                            sample_count=sum(row["dataset_support"]["sample_count"] for row in rows),
                            event_family_count=len(families), family_ids=sorted(families))))
    return out
