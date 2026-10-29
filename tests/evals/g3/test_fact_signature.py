"""Review regressions, with authored nonblind native G2 -> G3 integration controls."""

from types import SimpleNamespace

import pytest

from evals.intelligence_g2.contracts import data, digest, json_bytes
from evals.intelligence_g3.budget import plan_briefing
from evals.intelligence_g3.fact_signature import (
    REVISION,
    persona_content,
    policy,
    policy_sha256,
    signature,
    tokens,
)
from evals.intelligence_g3.history_contracts import HistoryInput
from evals.intelligence_g3.rankers import rank
from evals.intelligence_g3.ranking_contracts import RankingConfig
from evals.intelligence_g3.revisit import rank_revisit

from .fact_signature_support import CASES, scenario, target
from .ranking_support import delivered


def native_claims(value):
    old = value.replay.observations[0].evidence.claims[0]
    new = next(c for c in value.replay.evidence.claims if c.doc_version_id == "official:2")
    return old, new


@pytest.mark.parametrize("name", CASES)
@pytest.mark.parametrize("algorithm", ["b4", "p1"])
def test_native_serialized_changes_and_reprints_keep_correct_budget_priority(name, algorithm):
    value = HistoryInput.model_validate_json(json_bytes(scenario(name)))
    before = json_bytes(value)
    expected_change = CASES[name][-1]
    result = rank_revisit(value, algorithm)
    row = next(r for r in result.events if r.event_key == target(value))
    plan = plan_briefing(value, result)
    assert len(result.events) == 6 and json_bytes(value) == before
    assert row.history.declared_known is not expected_change
    assert row.protected is expected_change
    assert row.features.material_change.value == float(expected_change)
    if expected_change:
        old, new = native_claims(value)
        assert old.claim_key != new.claim_key and old.scope != new.scope
        assert value.replay.observations[0].candidates[0].event.event_revision != row.event_revision
        assert row.features.duplicate.value == 0 and row.features.novelty.value == 1
        assert row.rank == 1 and row.event_key in plan.display_order
    elif name != "current-persona":
        assert row.features.duplicate.value == pytest.approx(.35)
        assert row.features.novelty.value == 0
    assert "fact_signature_revision:" + REVISION in result.diagnostics


@pytest.mark.parametrize("name", [n for n in CASES if CASES[n][-1]])
def test_pr2_uses_same_signature_for_persona_ack_increment_and_duplicate(name):
    value = scenario(name)
    # PR2 consumes its own explicit legacy history, PR3 consumes the journal.
    replay = (delivered(value.replay, ("acknowledged",))
              if CASES[name][2] in {"ack", "both"} else value.replay)
    row = next(r for r in rank(replay, "p1").events if r.event_key == target(value))
    assert row.features.novelty.value == row.features.material_change.value == 1
    assert row.features.duplicate.value == 0


@pytest.mark.parametrize("left,right", [("<", ">"), ("<=", "<"), (">=", ">"),
    ("=", "!="), ("50", "60"), ("0.5", "0.05"), ("-5", "+5"),
    ("ms", "s"), ("MB", "mB"), ("µs", "ms"), ("1,000", "1000"), ("m²", "m2")])
def test_meaningful_symbols_numbers_and_units_never_collide(left, right):
    assert tokens(left) != tokens(right)


def test_equal_content_across_ids_references_and_offsets_remains_equal():
    claim = native_claims(scenario("unchanged-version"))[1]
    raw = data(claim)
    raw.update(claim_key="other:claim", doc_version_id="other:document", evidence_ref_ids=["other:ref"])
    # Unit projection only: provenance is intentionally different, not a valid new
    # G2 claim. Native input/reprint validity is checked separately above.
    other = claim.model_copy(update={k: raw[k] for k in
        ("claim_key", "doc_version_id", "evidence_ref_ids")})
    assert signature(claim) == signature(other)
    assert signature(claim).content == persona_content(claim.statement)
    assert tokens("Reprint: " + claim.statement) == tokens(claim.statement)


@pytest.mark.parametrize("field", ["task", "dataset", "baseline", "protocol", "hardware", "target_version"])
def test_native_grounded_scope_metadata_participates_in_signature(field):
    claim = native_claims(scenario("symbol-ack"))[1]
    value = getattr(claim.scope, field)
    changed = claim.model_copy(update={"scope": claim.scope.model_copy(update={
        field: value.model_copy(update={"normalized_value": "different grounded value"})})})
    assert signature(changed) != signature(claim)


@pytest.mark.parametrize("field,value", [("unit", "ratio"), ("quantifier", "at_most")])
def test_native_quantity_units_and_quantifiers_participate_in_signature(field, value):
    claim = native_claims(scenario("symbol-ack"))[1]
    q = claim.proposition.quantities[0]
    changed = claim.model_copy(update={"proposition": claim.proposition.model_copy(update={
        "quantities": (q.model_copy(update={field: value}),)})})
    assert signature(changed) != signature(claim)


def test_fact_policy_version_binds_comparison_and_revisit_configuration():
    value = scenario("symbol-ack")
    base = rank(value.replay, "p1")
    assert base.config_sha256 == digest(RankingConfig())
    assert base.comparison_sha256 == digest(dict(input_sha256=base.input_sha256,
        config_sha256=base.config_sha256, candidate_pool_sha256=base.candidate_pool_sha256,
        fact_signature_policy_sha256=policy_sha256()))
    result = rank_revisit(value, "p1")
    assert result.config_sha256 == digest(dict(history=data(result.config),
        base=data(result.base_config), fact_signature=policy()))
    assert "fact_signature_policy_sha256:" + policy_sha256() in result.diagnostics


def test_unknown_normalization_is_not_a_wildcard_and_provenance_is_not_content():
    claim = native_claims(scenario("symbol-ack"))[1]
    raw = claim.scope.conditions[0]
    unknown = claim.model_copy(update={"scope": claim.scope.model_copy(update={
        "conditions": (raw.model_copy(update={"normalized_value": None}),)})})
    assert signature(claim) != signature(unknown)
    assert tokens("latency < 50 ms") == tokens("latency  <  50 ms")
    assert persona_content("latency < 50 ms") != persona_content("latency > 50 ms")
    assert signature(SimpleNamespace(statement=claim.statement, scope=claim.scope,
        proposition=claim.proposition, claim_type=claim.claim_type, marker=claim.marker)) == signature(claim)
