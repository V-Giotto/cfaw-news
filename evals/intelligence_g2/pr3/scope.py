"""A finite, auditable grammar. Unknown values are never wildcards."""

import re
import unicodedata
from decimal import Decimal

from .contracts import ClaimScope, GroundedValue, Proposition, Quantity

FIELDS = ("task", "dataset", "baseline", "protocol", "hardware", "target_version")
SUBJECT = re.compile(r"(?:^|(?<=[.!?。]))\s*(?:reprint:\s*)?([^\n.;:!?。]+?)\s+"
    r"(v\d+(?:\.\d+)*)(?:\s+|(?=[\u4e00-\u9fff]))"
    r"(claims?|reports?|releases?|is released|correction|withdraws?|introduces?|宣称|报告|发布|更正|撤回)", re.I)
QUANTITY = re.compile(r"(?<![A-Za-z0-9_.])(\d+(?:\.\d+)?)\s*(percentage points?|percent(?:age)?|%|百分点|倍|times?)", re.I)


def normalize(raw):
    return " ".join(unicodedata.normalize("NFKC", raw).casefold().split())


def decimal_text(raw):
    return format(Decimal(raw).normalize(), "f")


def grounded(ref, start, end, normalized=None):
    raw = ref.quote[start:end]
    return GroundedValue(raw_value=raw, normalized_value=normalize(raw) if normalized is None else normalized,
                         ref_id=ref.ref_id, start=start, end=end)


def statement_parts(text):
    """Keep proposition spans before the first declared scope field."""
    boundary = re.search(r"\b(?:Task|Dataset|Baseline|Protocol|Hardware|Conditions)\s*:", text, re.I)
    return (text[:boundary.start()], text[boundary.start():]) if boundary else (text, "")


def quantity_value(ref, span, raw_unit, quantifier):
    raw_unit = normalize(raw_unit)
    unit = ("percent_point" if raw_unit in {"percentage point", "percentage points", "百分点"}
            else "percent" if raw_unit in {"%", "percent", "percentage"} else "ratio")
    return Quantity(value=grounded(ref, *span, normalized=decimal_text(ref.quote[slice(*span)])),
                    unit=unit, quantifier=quantifier)


def lifecycle_fields(ref):
    """An affirmative act and its explicitly named target, with original clause spans."""
    leading, suffix = statement_parts(ref.quote)
    targets = list(SUBJECT.finditer(leading))
    if len(targets) != 1 or re.search(r"\b(?:and|versus|vs)\b|与|对比", targets[0].group(1), re.I):
        return "none", None, ()
    target = targets[0]
    declared = r"(?:\s*(?:Task|Dataset|Baseline|Protocol|Hardware|Conditions)\s*:\s*[^;\n]+;\s*)+"
    if suffix and not re.fullmatch(declared, suffix, re.I):
        return "none", None, ()
    prefix = r"\s*" + re.escape(target.group(1)) + r"\s+" + re.escape(target.group(2))

    def quantity(name):
        return (r"(?:(?P<" + name + r"_quantifier>up to|at least|approximately)\s+)?(?P<"
                + name + r"_value>\d+(?:\.\d+)?)\s*(?P<" + name
                + r"_unit>percentage points?|percent(?:age)?|%|times?)")

    # Unknown/mismatched metrics may identify an affirmative attempted withdrawal,
    # but history must still resolve a complete grounded target before any change.
    metric = r"(?P<prior_metric>speed\s+(?:gain|improvement)|speedup|accuracy(?:\s+claim)?|claim)"
    prior = r"(?:our|its|the)\s+(?:previous|prior|earlier)\s+" + metric + r"\s+of\s+" + quantity("prior")
    withdrawal = prefix + r"\s+(?:withdraws?|retracts?)\s+" + prior + r"(?:\s+claim)?[.]?\s*"
    correction = (prefix + r"\s+correction:\s+" + prior + r"\s+is\s+corrected\s+to\s+"
                  + quantity("corrected") + r"[.]?\s*")
    for marker, pattern, names in (("withdrawal", withdrawal, ("prior",)),
                                   ("correction", correction, ("prior", "corrected"))):
        match = re.fullmatch(pattern, leading, re.I)
        if match is None:
            continue
        raw_metric = normalize(match.group("prior_metric"))
        metric = (None if raw_metric == "claim" else grounded(ref, *match.span("prior_metric"),
            normalized="accuracy" if raw_metric.startswith("accuracy") else "speed_gain"))
        quantities = []
        for name in names:
            raw = normalize(match.group(name + "_quantifier") or "")
            quantifier = {"up to": "at_most", "at least": "at_least", "approximately": "approx"}.get(raw, "reported")
            quantities.append(quantity_value(ref, match.span(name + "_value"),
                match.group(name + "_unit"), quantifier))
        return marker, metric, tuple(quantities)
    return "none", None, ()


def parse_fields(ref):
    text = ref.quote
    leading, suffix = statement_parts(text)
    values = {}
    for field in FIELDS[:-1]:
        matches = list(re.finditer(r"(?:^|[;\n.]\s*)\s*" + field + r"\s*:\s*([^;\n]+)", text, re.I))
        if len(matches) == 1:
            match = matches[0]
            start, end = match.span(1)
            while end > start and text[end - 1].isspace():
                end -= 1
            if start < end:
                values[field] = grounded(ref, start, end)
    targets = list(SUBJECT.finditer(leading))
    subjects = {normalize(m.group(1)) for m in targets}
    versions = {normalize(m.group(2)) for m in targets}
    ambiguous = (len(subjects) > 1 or len(versions) > 1 or any(
        re.search(r"\b(?:and|versus|vs)\b|与|对比", subject) for subject in subjects))
    target = targets[0] if len(targets) == 1 and not ambiguous else None
    subject = grounded(ref, *target.span(1)) if target else None
    action = grounded(ref, *target.span(3), normalized="reported_statement") if target else None
    if target:
        values["target_version"] = grounded(ref, *target.span(2))
    conditions = list(re.finditer(r"(?:^|[;\n])\s*conditions\s*:\s*([^;\n]+)", text, re.I))
    conditions = tuple(grounded(ref, *m.span(1)) for m in conditions)
    # Inline natural-language limits are retained verbatim even without a full structured scope.
    limits = list(re.finditer(r"(?:only|limited to|仅限|仅在)[^.;。\n]+", text, re.I))
    conditions += tuple(grounded(ref, *m.span()) for m in limits)
    scope = ClaimScope(**values, conditions=conditions,
        unknown_dimensions=tuple(f for f in FIELDS if f not in values) + (() if conditions else ("conditions",)))
    quantifier = ("at_most" if re.search(r"up to|at most|最高|最多", leading, re.I) else
                  "at_least" if re.search(r"at least|至少", leading, re.I) else
                  "approx" if re.search(r"approximately|about\s+\d|大约|约\d", leading, re.I) else "reported")
    quantities = []
    for match in QUANTITY.finditer(leading):
        quantities.append(quantity_value(ref, match.span(1), match.group(2), quantifier))
    metric_match = re.search(r"speed\s+(?:gain|improvement)|速度提升|speedup", leading, re.I)
    metric = grounded(ref, *metric_match.span(), normalized="speed_gain") if metric_match else None
    marker, target_metric, target_quantities = lifecycle_fields(ref)
    if marker != "none":
        metric, quantities = target_metric, target_quantities
        quantifier = quantities[0].quantifier
    negative = bool(re.search(r"no speed gain|no speed improvement|no speedup|速度未提升|没有速度提升", leading, re.I))
    positive = bool(metric and metric.normalized_value == "speed_gain" and len(quantities) == 1 and quantities[0].unit == "percent"
                    and Decimal(quantities[0].value.normalized_value) > 0 and not negative)
    # Multiple quantities cannot be reduced to a single measured outcome. Correction matching
    # uses their original spans, but they cannot supply a current support/refutation edge.
    uncertain_negation = bool(metric and not negative and re.search(r"\b(?:not|never|no|without)\b|不|未|没有", leading, re.I))
    ambiguous = ambiguous or len(quantities) > 1 or uncertain_negation or (negative and bool(quantities))
    if metric and target:
        # Strong inference is restricted to a completely recognized report + declared
        # scope grammar. Unparsed conditionals/discourse are not silently treated as a
        # complete scope, even when they contain familiar numbers and metadata markers.
        prefix = r"\s*(?:reprint:\s*)?" + re.escape(target.group(1)) + r"\s+" + re.escape(target.group(2))
        report = prefix + r"\s+(?:claims?|reports?)\s+(?:a\s+)?(?:speed\s+gain|speed\s+improvement|speedup)\s+(?:of\s+)?(?:up to\s+|at least\s+|approximately\s+)?\d+(?:\.\d+)?%[.]?\s*"
        denial = prefix + r"\s+(?:claims?|reports?)\s+no\s+(?:speed\s+gain|speed\s+improvement|speedup)[.]?\s*"
        declared = r"(?:\s*(?:Task|Dataset|Baseline|Protocol|Hardware|Conditions)\s*:\s*[^;\n]+;\s*)+"
        if not ((re.fullmatch(report, leading, re.I) or re.fullmatch(denial, leading, re.I))
                and re.fullmatch(declared, suffix, re.I)):
            ambiguous = True
    proposition = Proposition(subject=subject, action=action, metric=metric, quantities=tuple(quantities),
        polarity="negative" if negative else "positive" if positive else "unknown",
        quantifier=quantifier, ambiguous=ambiguous)
    return scope, proposition, marker


def value(field):
    return field.normalized_value if field else None


def compare_scope(a, b):
    for field in FIELDS:
        left, right = value(getattr(a, field)), value(getattr(b, field))
        if left is not None and right is not None and left != right:
            return "scope_difference"
    ca, cb = tuple(value(v) for v in a.conditions), tuple(value(v) for v in b.conditions)
    if ca and cb and ca != cb:
        return "scope_difference"
    if a.unknown_dimensions or b.unknown_dimensions or not ca or not cb:
        return "unknown"
    return "same_declared_scope"


def same_proposition(a, b):
    return (not a.proposition.ambiguous and not b.proposition.ambiguous
        and value(a.proposition.subject) is not None
        and value(a.proposition.subject) == value(b.proposition.subject)
        and value(a.proposition.metric) is not None
        and value(a.proposition.metric) == value(b.proposition.metric)
        and compare_scope(a.scope, b.scope) == "same_declared_scope")
