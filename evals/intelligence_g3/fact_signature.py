"""Versioned, conservative content identity; source references are provenance only.

This is a syntactic fact signature, not a semantic-equivalence classifier. Preserve
every non-whitespace character (including case-sensitive units), and native G2
grounded scope/proposition values. Never use claim/document/citation identifiers.
"""

import re
import unicodedata
from dataclasses import dataclass
from types import SimpleNamespace

from evals.intelligence_g2.contracts import digest
from evals.intelligence_g2.pr3.scope import parse_fields

REVISION = "g3-grounded-fact-signature-v2"
TOKEN = re.compile(r"<=>|<=|>=|!=|==|<>|\w+|[^\w\s]", re.UNICODE)
SCOPE_FIELDS = ("task", "dataset", "baseline", "protocol", "hardware", "target_version")


def policy():
    return dict(revision=REVISION, text="NFC-case-sensitive-all-symbols-ignore-whitespace-v1",
        reprint="ignore-one-explicit-leading-Reprint-label-v1",
        grounded="raw-and-normalized-values-normalizer-scope-proposition-quantities-v1",
        provenance="ignore-claim-document-citation-ids-and-span-offsets",
        persona="same-text-and-G2-parsed-scope-proposition-no-grounding-claim",
        interpretation="syntactic-change-proxy-not-semantic-truth-or-unit-conversion")


def policy_sha256():
    return digest(policy())


def tokens(text):
    # Only an explicit editorial prefix is removed. Negation, operators, decimal
    # punctuation, signs, units and arbitrary unknown symbols are all retained.
    text = re.sub(r"^\s*reprint:\s*", "", text, count=1, flags=re.I)
    return tuple(TOKEN.findall(unicodedata.normalize("NFC", text)))


def grounded(value):
    if value is None:
        return None
    return (tokens(value.raw_value), tokens(value.normalized_value)
            if value.normalized_value is not None else None, value.normalizer_revision)


@dataclass(frozen=True)
class Content:
    revision: str
    statement: tuple
    scope: tuple
    proposition: tuple


@dataclass(frozen=True)
class Fact:
    content: Content
    claim_type: str
    marker: str


def content(statement, scope, proposition):
    scoped = tuple((name, grounded(getattr(scope, name))) for name in SCOPE_FIELDS)
    scoped += (("conditions", tuple(sorted({grounded(v) for v in scope.conditions}, key=repr))),
               ("unknown_dimensions", tuple(sorted(scope.unknown_dimensions))))
    asserted = tuple((name, grounded(getattr(proposition, name)))
                     for name in ("subject", "action", "metric"))
    asserted += (("quantities", tuple((grounded(q.value), q.unit, q.quantifier)
                                      for q in proposition.quantities)),
                 ("polarity", proposition.polarity), ("quantifier", proposition.quantifier),
                 ("ambiguous", proposition.ambiguous))
    return Content(REVISION, tokens(statement), scoped, asserted)


def signature(claim):
    return Fact(content(claim.statement, claim.scope, claim.proposition),
                claim.claim_type, claim.marker)


def persona_content(statement):
    # A declaration has no citation or verification status. Reuse the finite G2
    # field grammar solely for matching its declared content to a native claim;
    # the placeholder reference and parser spans never enter the signature.
    scope, proposition, _ = parse_fields(SimpleNamespace(quote=statement, ref_id="persona:declaration"))
    return content(statement, scope, proposition)
