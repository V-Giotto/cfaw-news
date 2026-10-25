"""Narrow relations between reported propositions, never truth verification."""

from itertools import combinations

from .contracts import Conflict, EvidenceLink, RelationResult, digest, fail
from .scope import compare_scope, same_proposition


def make_link(target, evidence, direction, scope_relation, rule):
    material = dict(target_claim_key=target.claim_key, evidence_claim_key=evidence.claim_key,
        ref_id=evidence.evidence_ref_ids[0], direction=direction,
        basis="rule_inferred" if direction in {"supports", "refutes"} else
              "source_excerpt" if target.claim_key == evidence.claim_key else "unresolved",
        rule_id=rule, scope_relation=scope_relation,
        support_check_status="rule_checked" if direction in {"supports", "refutes"} else "not_evaluated")
    return EvidenceLink(link_key="g2:link:" + digest(material), **material)


def assess_claim_relations(*, claims, lineage, history, config):
    del lineage  # No positive independence assertion can be made from lineage absence.
    owners = history["owners"]
    links = [make_link(c, c, "mentions", "unknown", "source_made_statement") for c in claims]
    conflicts = []
    comparisons = 0
    for a, b in combinations(sorted(claims, key=lambda c: c.claim_key), 2):
        if owners[a.claim_key] != owners[b.claim_key]:
            continue
        comparisons += 1
        if comparisons > config.max_comparisons:
            fail("G2_PR3_BUDGET_EXCEEDED", "relations", "comparisons")
        scope = compare_scope(a.scope, b.scope)
        direction, rule = "unknown", "target_or_scope_unknown"
        if scope == "scope_difference":
            rule = "scope_difference"
        if (same_proposition(a, b) and a.marker == b.marker == "none"
                and "secondary_material" not in {a.attribution.attribution_kind, b.attribution.attribution_kind}):
            pa, pb = a.proposition, b.proposition
            if {pa.polarity, pb.polarity} == {"positive", "negative"} and (
                    pa.quantifier == pb.quantifier == "reported"):
                direction, rule = "refutes", "opposite_polarity_same_scope"
                material = dict(claim_keys=(a.claim_key, b.claim_key),
                                ref_ids=a.evidence_ref_ids + b.evidence_ref_ids)
                conflicts.append(Conflict(conflict_id="g2:conflict:" + digest(material), **material))
            elif pa.polarity == pb.polarity == "positive" and len(pa.quantities) == len(pb.quantities) == 1:
                qa, qb = pa.quantities[0], pb.quantities[0]
                if ((qa.value.normalized_value, qa.unit, qa.quantifier) ==
                        (qb.value.normalized_value, qb.unit, qb.quantifier)):
                    direction, rule = "supports", "same_reported_value_and_scope"
        links.extend((make_link(a, b, direction, scope, rule), make_link(b, a, direction, scope, rule)))
    return RelationResult(links=tuple(sorted(links, key=lambda v: v.link_key)),
        conflicts=tuple(sorted(conflicts, key=lambda v: v.conflict_id)), comparisons=comparisons)
