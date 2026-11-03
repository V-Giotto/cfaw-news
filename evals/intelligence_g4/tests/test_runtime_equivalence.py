"""Only test code loads the real frozen synthetic replay proof; runtime never does."""

import pytest
from cfaw_news.intelligence.g3_adapter import rows

from evals.intelligence_g2.contracts import data
from evals.intelligence_g3.budget import derive, plan_briefing
from evals.intelligence_g3.budget_contracts import BudgetConfig
from evals.intelligence_g3.history_contracts import HistoryInput
from evals.intelligence_g3.revisit import rank_revisit
from tests.evals.g3.history_support import revisit_case, with_history


@pytest.mark.parametrize("mode", ["repeat", "correction"])
@pytest.mark.parametrize("algorithm", ["b4", "p1"])
def test_frozen_native_ranking_rows_exact_equivalence(mode, algorithm):
    history = with_history(revisit_case(days=7, mode=mode), kinds=("opened",))
    assert isinstance(history, HistoryInput)
    native = rank_revisit(history, algorithm)
    assert [data(r) for r in rows(history, algorithm)] == [data(r) for r in native.events]


@pytest.mark.parametrize("profile", ["focus60-radar40-v1", "focus70-radar30-v1", "focus80-radar20-v1"])
def test_native_budget_kernel_preserves_every_plan_field(profile):
    history = with_history(revisit_case(days=7, mode="correction"), kinds=("opened",))
    plan = plan_briefing(history, rank_revisit(history, "b4"), BudgetConfig(profile=profile))
    assert plan.model_dump(mode="json", exclude={"input", "scope", "schema_revision"}) == derive(plan.input)
