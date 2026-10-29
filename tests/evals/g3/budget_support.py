"""Native synthetic prediction cases for the separate PR4 planner tests."""

from functools import lru_cache
from unittest.mock import patch

from evals.intelligence_g2.contracts import data, digest
from evals.intelligence_g3.contracts import G3ReplayInput, parse
from evals.intelligence_g3.history_contracts import HistoryInput, HistoryJournal
from evals.intelligence_v1.contracts import CoverageWindow
from tests.evals.g2.pr2.support import sequence

from . import ranking_support
from .ranking_support import delivered

NAMES = ("Atlas", "Boreal", "Cedar", "Delta", "Ember", "Fjord", "Grove", "Hazel",
         "Indigo", "Juniper", "Kestrel", "Lunar", "Maple", "Nimbus")


def source(replay, budget=180):
    raw = data(replay)
    raw["attention_budget_seconds"] = budget
    raw["persona"]["persona"].update(domain_interests=["local", "evaluation", "unmatched"],
                                     current_goals=[], hard_constraints=[])
    return HistoryInput(replay=parse(G3ReplayInput, raw), journal=HistoryJournal())


@lru_cache
def pool_case(budget=180):
    specs = [dict(id=name, title=f"{name} SDK v1.0 release",
                  body=f"{name} SDK provides local agent evaluation.") for name in NAMES]
    replay = ranking_support.native_replay([(0, specs)])
    return source(replay, budget)


@lru_cache
def long_case(length=160, budget=180):
    # Fully grounded measured claim, below native G2's character limit. Its
    # uncropped mandatory projection can nevertheless exceed the G3 time budget.
    body = ("Atlas Tool v1.0 claims a speed gain of 40%. Task: summarization; Dataset: ToySet; "
            "Baseline: Base v1.0; Protocol: P1; Hardware: CPU; Conditions: " + "限定" * length + ";")
    return source(ranking_support.native_replay([(0, [dict(id="official", body=body)])]), budget)


@lru_cache
def long_update_case(length):
    scope = ("Atlas Tool v1.0 claims a speed gain of 40%. Task: summarization; Dataset: ToySet; "
             "Baseline: Base v1.0; Protocol: P1; Hardware: CPU; Conditions: ")
    old = dict(id="official", body=scope + "限定" * 20 + ";")
    new = dict(id="official", version=2, body=scope + "限定" * length + ";")
    return source(delivered(ranking_support.native_replay([(0, [old]), (7, [new])]), ()))


@lru_cache
def protected_case(count=2):
    old, new = [], []
    for index, name in enumerate(NAMES[:count]):
        scope = "Task: summarization; Dataset: ToySet; Baseline: Base v1.0; Protocol: P1; Hardware: CPU; Conditions: batch=1;"
        old.append(dict(id=name, title=f"{name} Tool v1.0 release",
            body=f"{name} Tool v1.0 claims a speed gain of 40%. " + scope))
        update = ("correction: the previous speed gain of 40% is corrected to 4%." if index % 2 == 0
                  else "withdraws the previous speed gain of 40% claim.")
        new.append(dict(id=name, version=2, title=f"{name} Tool v1.0 release",
                        body=f"{name} Tool v1.0 {update} " + scope))
    ordinary = dict(id="fresh", title="Zinc SDK v1.0 release",
                    body="Zinc SDK provides local agent evaluation.")
    # The ordinary event is strictly newer, giving B0 a natural high-score
    # ordinary row before the protected updates. No scores are edited by tests.
    replay = ranking_support.native_replay([(0, old), (6, new), (7, [*new, ordinary])])
    return source(replay)


@lru_cache
def coverage_case(status="unknown"):
    specs = [dict(id="Atlas", body="Atlas Tool provides local execution.")]
    values = sequence([(0, specs)])
    native = values[0]
    window = CoverageWindow(coverage_window_id="synthetic:coverage", source_id=native.sources[0].source_id,
        start_at=native.context.time_window_start, end_at=native.context.as_of,
        observed_at=native.context.as_of, status=status, reason=f"synthetic:{status}")
    native = native.model_copy(update={"context": native.context.model_copy(
        update={"source_coverage": (window,)}), "source_coverage_digest": digest([data(window)])})
    def bind_coverage(model, raw):
        # The PR2 test builder deliberately assumes no coverage observations.
        # Bind its envelope to the actual source windows used by the native G2 run.
        raw["source_coverage"] = [data(window)]
        raw["observations"][0].update(source_coverage=[data(window)],
                                    source_coverage_digest=digest([data(window)]))
        return parse(model, raw)
    # No G2 outputs or planner decisions are mocked or repaired.
    with (patch.object(ranking_support, "sequence", return_value=(native,)),
          patch.object(ranking_support, "parse", side_effect=bind_coverage)):
        replay = ranking_support.native_replay([(0, specs)])
    return source(replay)
