"""PR2 invariants use only synthetic prediction inputs, never gold tuning."""

import os
import subprocess
import sys
from datetime import timedelta
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from evals.intelligence_g2.contracts import data, digest, json_bytes
from evals.intelligence_g3.contracts import PACKAGE, ROOT, G3ReplayInput, parse
from evals.intelligence_g3.rankers import _features, compare, rank
from evals.intelligence_g3.ranking_contracts import (
    ALGORITHM_VERSIONS,
    MODELS,
    RankingConfig,
    RankingResult,
)
from evals.intelligence_v1.baselines import candidate_scores
from evals.intelligence_v1.exceptions import ContractError

from .ranking_support import SPECS, delivered, native_replay, pool
from .support import Scenario


@pytest.mark.parametrize("algorithm", ALGORITHM_VERSIONS)
def test_same_pool_no_mutation_and_deterministic_roundtrip(algorithm):
    value = pool()
    before = json_bytes(value)
    result = rank(value, algorithm)
    assert json_bytes(rank(value, algorithm)) == json_bytes(result)
    assert RankingResult.model_validate_json(json_bytes(result)) == result
    assert json_bytes(value) == before
    assert {e.event_key for e in result.events} == {c.event.event_key for c in value.candidates}
    assert len(result.events) == 3
    assert [e.rank for e in result.events] == [1, 2, 3]
    assert result.algorithm_version == f"g3-{algorithm}-event-v1"


def test_all_algorithms_bind_exact_same_context_config_and_pool():
    value = delivered(pool())
    assert value.history and value.deliveries
    results = compare(value)
    assert len(results) == 6
    for field in ("comparison_sha256", "input_sha256", "candidate_pool_sha256", "config_sha256",
                  "as_of", "persona_version_id", "attention_budget_seconds"):
        assert len({getattr(r, field) for r in results}) == 1
    changed = data(value)
    changed["attention_budget_seconds"] = 180
    changed = parse(G3ReplayInput, changed)
    assert changed.attention_budget_seconds != value.attention_budget_seconds
    assert changed.model_dump(exclude={"attention_budget_seconds"}) == value.model_dump(
        exclude={"attention_budget_seconds"})
    assert rank(changed, "p1").comparison_sha256 != results[0].comparison_sha256, (
        "budget-only change must change comparison fingerprint")


def test_budget_binding_assertion_rejects_fingerprint_omitting_budget(monkeypatch):
    def omit_budget(value):
        if isinstance(value, G3ReplayInput):
            value = value.model_dump(mode="json", exclude={"attention_budget_seconds"})
        return digest(value)

    # Change only the ranker's local hash function, leaving native integrity
    # validation intact. Both baseline and changed inputs run under the mutant.
    monkeypatch.setattr("evals.intelligence_g3.rankers.digest", omit_budget)
    with pytest.raises(AssertionError, match="budget-only change must change comparison fingerprint"):
        test_all_algorithms_bind_exact_same_context_config_and_pool()


def test_b1_b2_reuse_g1_scores_without_grouping(monkeypatch):
    value = pool()
    rows = tuple(SimpleNamespace(doc_version_id=c.event.event_key,
        title=c.rule_item.headline.text if c.rule_item.headline else "", paragraphs=(),
        text_excerpt="\n".join(s.statement.text for s in c.rule_item.claim_summaries
                               if s.claim_key in c.rule_item.selected_claim_keys)) for c in value.candidates)
    expected = candidate_scores(SimpleNamespace(persona=value.persona.persona), rows)
    def forbidden(*args, **kwargs):
        raise AssertionError("G3 cannot regroup G2 events")
    monkeypatch.setattr("evals.intelligence_v1.baselines.group_candidates", forbidden)
    b1, b2 = rank(value, "b1"), rank(value, "b2")
    assert b1.events == b2.events
    assert {e.event_key: e.score for e in b1.events} == expected


@pytest.mark.parametrize("algorithm", ALGORITHM_VERSIONS)
def test_ties_use_event_identity_and_not_candidate_iteration_order(algorithm):
    raw = data(pool())
    for field in ("domain_interests", "current_goals", "hard_constraints"):
        raw["persona"]["persona"][field] = []
    value = parse(G3ReplayInput, raw)
    first = rank(value, algorithm)
    # Formal PR1 binds current order to its observation; permute both copies.
    raw["candidates"].reverse()
    raw["observations"][-1]["candidates"].reverse()
    # Published references/snapshot archives have their own native observation order.
    raw["published_refs"][-3:] = reversed(raw["published_refs"][-3:])
    raw["item_snapshots"][-3:] = reversed(raw["item_snapshots"][-3:])
    second = rank(parse(G3ReplayInput, raw), algorithm)
    assert [(e.event_key, e.score) for e in first.events] == [(e.event_key, e.score) for e in second.events]
    eligible = [e for e in first.events if e.eligible]
    assert len(eligible) == 2 and eligible[0].score == eligible[1].score
    assert [e.event_key for e in eligible] == sorted(e.event_key for e in eligible)


@pytest.mark.parametrize("algorithm", ALGORITHM_VERSIONS)
def test_empty_pool_still_emits_context_and_coverage_diagnostics(algorithm):
    value = Scenario("E10-negative").load()
    result = rank(value, algorithm)
    assert result.events == ()
    assert "coverage_gaps_do_not_mean_no_world_change" in result.diagnostics
    assert result.input_sha256 == digest(value)


@pytest.mark.parametrize("algorithm", ALGORITHM_VERSIONS)
def test_hold_and_evidence_constraints_are_structural_not_score_offsets(algorithm, monkeypatch):
    value = pool()
    held_key = next(c.event.event_key for c in value.candidates if c.rule_item.tier_candidate == "hold")
    monkeypatch.setattr("evals.intelligence_g3.rankers.candidate_scores", lambda *args:
                        {c.event.event_key: 1e9 if c.event.event_key == held_key else 0
                         for c in value.candidates})
    result = rank(value, algorithm)
    hold = [e for e in result.events if e.g2_tier_candidate == "hold"]
    assert len(hold) == 1 and not hold[0].eligible
    assert set(hold[0].block_reasons) >= {"g2_hold", "g2_evidence_insufficient"}
    assert result.events[-1] == hold[0]
    assert hold[0].features.exploration.value == 0
    if algorithm != "b0":
        assert hold[0].score > max(e.score for e in result.events if e.eligible)


def test_b0_b3_use_availability_half_life_and_ignore_missing_event_date():
    result = rank(pool(), "b3")
    assert all(c.event.event_date is None for c in pool().candidates)
    assert all(e.features.age_days == 7 for e in result.events)
    assert all(e.features.recency.value == 0.5 for e in result.events)
    for e in result.events:
        assert e.score == round(0.75 * e.features.relevance.value + 0.25 * 0.5, 5)
    b0 = rank(pool(), "b0")
    assert all(e.score == e.features.latest_material_at.timestamp() for e in b0.events)


def test_missing_material_time_is_zero_and_missing_required_time_is_rejected():
    value = pool()
    candidate = value.candidates[0]
    # Exercise the documented empty-material fallback separately from PR1's
    # rejection of removal of a required native source-pointer timestamp.
    probe = candidate.model_copy(update={"rule_item": candidate.rule_item.model_copy(
        update={"source_pointers": ()})})
    features, _ = _features(value, probe, 0, 0, 0, RankingConfig(), ())
    assert features.latest_material_at is None and features.recency.value == 0
    raw = data(value)
    del raw["candidates"][0]["rule_item"]["source_pointers"][0]["available_at"]
    with pytest.raises((ValidationError, ContractError)):
        parse(G3ReplayInput, raw)


@pytest.mark.parametrize("kind,penalty,novelty", [
    ("included", 0.1, 1), ("rendered", 0.2, 1), ("opened", 0.1, 1),
    ("acknowledged", 0.35, 0), ("dismissed", 0.1, 1),
])
def test_history_signals_remain_distinct(kind, penalty, novelty):
    value = delivered(pool(), (kind,))
    target = value.deliveries[0].items[0].event_key
    e = next(e for e in rank(value, "p1").events if e.event_key == target)
    assert e.features.duplicate.value == pytest.approx(penalty)
    assert e.features.novelty.value == novelty
    assert e.features.exposure_signals == tuple(sorted({"included", kind}))
    assert e.features.material_change.value == 0
    b3 = next(e for e in rank(value, "b3").events if e.event_key == target)
    b4 = next(e for e in rank(value, "b4").events if e.event_key == target)
    assert b4.score == round(sum(c.contribution for c in b3.components) - penalty, 5)


def test_repeated_signal_does_not_multiply_penalty_and_known_is_explicit():
    value = delivered(pool(), ("rendered", "rendered", "opened"))
    target = value.deliveries[0].items[0].event_key
    e = next(e for e in rank(value, "p1").events if e.event_key == target)
    assert e.features.duplicate.value == 0.2 and e.features.novelty.value == 1
    raw = data(pool())
    raw["persona"]["persona"]["knowledge_known"] = [c.statement for c in pool().evidence.claims]
    result = rank(parse(G3ReplayInput, raw), "p1")
    assert all(e.features.novelty.value == 0 for e in result.events)


def test_evidence_correction_clears_penalty_and_renewed_novelty():
    value = delivered(Scenario().load(), ("rendered", "acknowledged"))
    e = rank(value, "p1").events[0]
    assert e.eligible and e.features.material_change.value == 1
    assert e.features.duplicate.value == 0 and e.features.novelty.value == 1
    assert any("/observations/0/" in r for r in e.features.material_change.input_refs)


def test_reprint_does_not_become_material_change_or_independent_support():
    specs = [{"id": "a"}]
    reprint = {"id": "copy", "title": "Atlas Tool v1.0 release", "upstream": "a",
               "body": SPECS[0].get("body", "The Atlas Tool release provides local execution for a fixed toy workflow.")}
    value = delivered(native_replay([(0, specs), (1, [*specs, reprint])]))
    e = rank(value, "p1").events[0]
    assert e.features.material_change.value == 0
    assert e.features.duplicate.value == 0.1
    assert all(a.independent_support_count == 0 for a in value.evidence.assessments)


def test_exploration_is_bounded_disabled_for_known_and_unknown_preferences():
    raw = data(pool())
    raw["persona"]["persona"].update(domain_interests=[], current_goals=[], hard_constraints=[])
    results = rank(parse(G3ReplayInput, raw), "p1")
    assert all(0 <= e.features.exploration.value <= 0.05 for e in results.events)
    assert any(e.features.exploration.value == 0.05 for e in results.events if e.eligible)
    for preference in ("off", "unregistered arbitrary exploration text"):
        raw["persona"]["persona"]["exploration_preference"] = preference
        assert all(e.features.exploration.value == 0 for e in rank(parse(G3ReplayInput, raw), "p1").events)


@pytest.mark.parametrize("field", ["half_life_days", "relevance_weight", "exploration_cap", "score_decimals"])
def test_unregistered_configuration_is_rejected(field):
    config = RankingConfig().model_copy(update={field: 2})
    with pytest.raises(ContractError, match="G3_RANK_CONFIG_INVALID"):
        rank(pool(), "p1", config)


@pytest.mark.parametrize("field", ["persona", "candidate", "history", "coverage"])
def test_model_copy_future_inputs_fail_before_prediction(field):
    value = delivered(pool())
    future = value.as_of + timedelta(days=1)
    if field == "persona":
        value = value.model_copy(update={"persona": value.persona.model_copy(update={
            "persona": value.persona.persona.model_copy(update={"available_at": future})})})
    elif field == "candidate":
        candidate = value.candidates[0]
        value = value.model_copy(update={"candidates": (candidate.model_copy(update={
            "event": candidate.event.model_copy(update={"created_at": future})}), *value.candidates[1:])})
    elif field == "history":
        value = value.model_copy(update={"history": (value.history[0].model_copy(update={"available_at": future}),)})
    else:
        value = value.model_copy(update={"source_coverage": ({"observed_at": future},)})
    with pytest.raises(ContractError, match="G3_FUTURE_INPUT"):
        rank(value, "p1")


@pytest.mark.parametrize("field", ["gold", "expected_ranking", "reference_labels", "future_outcome"])
def test_label_or_future_answer_fields_are_not_a_prediction_contract(field):
    raw = data(pool())
    raw[field] = {"secret": "prefer_the_hold_candidate"}
    with pytest.raises((ValidationError, ContractError)):
        parse(G3ReplayInput, raw)


def test_every_component_resolves_input_pointers_and_reconstructs_score():
    value = delivered(pool())
    raw = data(value)
    for result in compare(value):
        for e in result.events:
            assert e.components
            total = sum(c.contribution for c in e.components)
            assert e.score == (total if result.algorithm_id == "b0" else round(total, 5))
            for component in e.components:
                assert component.contribution == component.raw_value * component.weight
                assert component.input_refs
                for pointer in component.input_refs:
                    cursor = raw
                    for token in pointer.split("/")[1:]:
                        cursor = cursor[int(token)] if isinstance(cursor, list) else cursor[token]


def test_registered_policy_and_generated_schemas_match():
    assert (PACKAGE / "manifests/pr2_ranking_config.json").read_bytes() == json_bytes(RankingConfig())
    for model in MODELS:
        assert (PACKAGE / "schema/v2" / f"{model.__name__}.schema.json").read_bytes() == json_bytes(model.model_json_schema())


def test_unknown_algorithm_and_noncontract_input_fail():
    with pytest.raises(ContractError, match="G3_UNKNOWN_RANKER"):
        rank(pool(), "b2-oracle")
    with pytest.raises(ContractError, match="G3_SCHEMA_INVALID"):
        rank(data(pool()), "p1")


def test_hash_seed_determinism_and_prediction_import_isolation(tmp_path):
    input_file = tmp_path / "input.json"
    input_file.write_bytes(json_bytes(pool()))
    script = """
import builtins, pathlib, sys
original_open = builtins.open
original_read = pathlib.Path.read_bytes
def deny(path):
    name = str(path).replace('\\\\', '/').lower()
    if any(part in name for part in ('/labels/', '/reference/', 'expected', 'gold')):
        raise AssertionError('prediction tried to read labels')
def guarded_open(path, *args, **kwargs):
    deny(path)
    return original_open(path, *args, **kwargs)
def guarded_read(path):
    deny(path)
    return original_read(path)
builtins.open = guarded_open
pathlib.Path.read_bytes = guarded_read
from evals.intelligence_g3.contracts import G3ReplayInput
from evals.intelligence_g3.rankers import compare
from evals.intelligence_g2.contracts import json_bytes
value = G3ReplayInput.model_validate_json(pathlib.Path(sys.argv[1]).read_bytes())
print(json_bytes([r.model_dump(mode='json') for r in compare(value)]).decode(), end='')
assert not any('.metrics' in m or '.evaluate' in m or '.acceptance' in m for m in sys.modules)
"""
    outputs = []
    for seed in ("1", "91"):
        result = subprocess.run([sys.executable, "-B", "-c", script, str(input_file)], cwd=ROOT,
            env={**os.environ, "PYTHONHASHSEED": seed, "PYTHONPATH": str(ROOT / "backend")},
            capture_output=True, timeout=45)
        assert result.returncode == 0, result.stderr.decode()
        outputs.append(result.stdout)
    assert outputs[0] == outputs[1]
