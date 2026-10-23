"""Offline agreement arithmetic; development comparisons never attest to people."""

import random
from collections import defaultdict
from itertools import combinations

from .metrics import ratio

SCORES = ("relevance", "potential_value", "novelty_to_persona", "evidence_quality",
          "graded_relevance")
CATEGORIES = {"tier": ["focus", "radar", "archive", "hold"],
              "material_change": ["new", "meaningful_update", "no_change", "correction",
                                  "withdrawal", "insufficient"]}


def family_confidence_interval(pairs, categories, *, weighted=False, resamples=1000, seed=719):
    """Percentile cluster bootstrap. Resample whole families, never individual steps."""
    from .annotations import agreement_statistic

    if resamples < 1:
        raise ValueError("resamples must be positive")
    ordered = sorted(pairs)
    agreement_statistic([a for _, a, _ in ordered], [b for _, _, b in ordered],
                        categories, weighted=weighted)
    groups = defaultdict(list)
    for family, a, b in ordered:
        groups[family].append((a, b))
    result = {"interval": None, "confidence_level": .95, "resampling_unit": "family",
              "family_count": len(groups), "resamples": resamples, "seed": seed,
              "valid_resamples": 0, "undefined_resamples": 0, "undefined_reason": None,
              "warning": "few_families_unstable_not_generalization_evidence" if len(groups) <= 5 else None}
    if len(groups) < 2:
        result["undefined_reason"] = "no_paired_samples" if not ordered else "fewer_than_two_families"
        return result
    keys, values, rng = sorted(groups), [], random.Random(seed)
    for _ in range(resamples):
        sample = [pair for family in rng.choices(keys, k=len(keys)) for pair in groups[family]]
        value = agreement_statistic([a for a, _ in sample], [b for _, b in sample],
                                    categories, weighted=weighted)["kappa"]
        if value is not None:
            values.append(value)
    values.sort()
    result.update(valid_resamples=len(values), undefined_resamples=resamples-len(values))
    if not values:
        result["undefined_reason"] = "all_bootstrap_kappas_undefined"
        return result

    def quantile(probability):
        index = (len(values)-1)*probability
        low = int(index)
        return values[low] + (values[min(low+1, len(values)-1)]-values[low])*(index-low)

    result["interval"] = [quantile(.025), quantile(.975)]
    return result


def align_components(left, right):
    """Connected document-overlap components retain every split/merge member."""
    sets = [{*row["document_version_ids"]} for row in (*left, *right)]
    unseen, result = set(range(len(sets))), []
    while unseen:
        stack, component = [min(unseen)], set()
        while stack:
            index = stack.pop()
            if index in component:
                continue
            component.add(index)
            unseen.discard(index)
            # Only cross-reviewer edges: distinct groups on one side stay distinct.
            stack.extend(j for j in sorted(unseen) if (index < len(left)) != (j < len(left))
                         and sets[index] & sets[j])
        a = sorted(i for i in component if i < len(left))
        b = sorted(i-len(left) for i in component if i >= len(left))
        adocs = sorted(set().union(*(sets[i] for i in a)))
        bdocs = sorted(set().union(*(sets[i+len(left)] for i in b)))
        status = ("missing_in_a" if not a else "missing_in_b" if not b else
                  "matched" if len(a) == len(b) == 1 and adocs == bdocs else
                  "split_merge_disagreement")
        result.append({"status": status, "a_indices": a, "b_indices": b,
                       "a_documents": adocs, "b_documents": bdocs})
    return result


def compare_development_records(submissions, *, families, excluded_steps=()):
    """A/B here are one human and one AI; output can never satisfy a human gate."""
    from .annotations import agreement_statistic

    grouped = defaultdict(lambda: {"A": [], "B": []})
    for role in ("A", "B"):
        for record in submissions[role]:
            if record["step_id"] not in excluded_steps:
                grouped[record["timeline_id"], record["step_id"]][role].append(record["initial_label"])
    samples = {name: [] for name in (*SCORES, *CATEGORIES)}
    alignment, pair_counts = [], {"a_positive": 0, "b_positive": 0, "shared_positive": 0,
                                "comparable_pairs": 0, "agreeing_pairs": 0,
                                "a_only_documents": 0, "b_only_documents": 0}
    for (timeline, step), rows in sorted(grouped.items()):
        components = align_components(rows["A"], rows["B"])
        alignment.append({"timeline_id": timeline, "step_id": step, "components": components,
                          "a_event_count": len(rows["A"]), "b_event_count": len(rows["B"])})
        for component in components:
            if component["status"] != "matched":
                continue
            a, b = rows["A"][component["a_indices"][0]], rows["B"][component["b_indices"][0]]
            for name in samples:
                samples[name].append((families[timeline], a[name], b[name]))
        documents = [{d for row in rows[role] for d in row["document_version_ids"]} for role in ("A", "B")]
        common = documents[0] & documents[1]
        positive = [{pair for row in rows[role] for pair in
                     combinations(sorted(set(row["document_version_ids"]) & common), 2)} for role in ("A", "B")]
        comparable = len(common)*(len(common)-1)//2
        pair_counts["a_only_documents"] += len(documents[0]-documents[1])
        pair_counts["b_only_documents"] += len(documents[1]-documents[0])
        pair_counts["a_positive"] += len(positive[0])
        pair_counts["b_positive"] += len(positive[1])
        pair_counts["shared_positive"] += len(positive[0] & positive[1])
        pair_counts["comparable_pairs"] += comparable
        pair_counts["agreeing_pairs"] += comparable-len(positive[0] ^ positive[1])
    statistics = {}
    for name, pairs in samples.items():
        categories = list(range(4)) if name in SCORES else CATEGORIES[name]
        statistics[name] = {
            **agreement_statistic([a for _, a, _ in pairs], [b for _, _, b in pairs],
                                  categories, weighted=name in SCORES),
            "family_confidence_interval": family_confidence_interval(pairs, categories,
                                                                     weighted=name in SCORES)}
    tp, ap, bp = (pair_counts[n] for n in ("shared_positive", "a_positive", "b_positive"))
    event_pairs = {"scope": "both_sides_annotated_documents_only",
                   "raw_agreement": ratio(pair_counts["agreeing_pairs"], pair_counts["comparable_pairs"],
                                          "no_common_document_pairs"),
                   "a_reference_precision": ratio(tp, bp, "no_positive_pairs"),
                   "a_reference_recall": ratio(tp, ap, "no_positive_pairs"),
                   "b_reference_precision": ratio(tp, ap, "no_positive_pairs"),
                   "b_reference_recall": ratio(tp, bp, "no_positive_pairs"),
                   "f1": ratio(2*tp, ap+bp, "no_positive_pairs")}
    return {"scope": "human_ai_development_comparison_not_independent_human_agreement",
            "human_annotation_gate": "BLOCKED", "g1a_passed": False,
            "excluded_steps": sorted(excluded_steps), "alignment": alignment,
            "statistics": statistics, "event_pair_counts": pair_counts, "event_pairs": event_pairs,
            "semantic_support": {"value": None,
                "undefined_reason": "human_ai_comparison_is_not_independent_human_semantic_review"}}
