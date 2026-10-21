import pytest
from test_loader import step


def items(count=20):
    from evals.intelligence_v1.baselines import get_ranker
    from evals.intelligence_v1.contracts import BaselineConfig

    context, docs = step(name="D0")
    docs = tuple(docs[0].model_copy(update={"document_id": f"budget:{i:02}",
        "doc_version_id": f"budget:{i:02}:1"}) for i in range(count))
    context = context.model_copy(update={"candidate_doc_version_ids": tuple(
        d.doc_version_id for d in docs)})
    return get_ranker("b1", BaselineConfig()).rank(context, docs)


@pytest.mark.parametrize("seconds,count,used", [(180, 2, 180), (420, 15, 414), (900, 15, 414)])
def test_BUDGET01_fixed_prefix_and_caps(seconds, count, used):
    from evals.intelligence_v1.budget import apply_budget
    from evals.intelligence_v1.contracts import BudgetPolicy

    ranked = items()
    result = apply_budget(ranked, BudgetPolicy(max_read_seconds=seconds))
    assert len(result.presented_items) == count
    assert result.used_read_seconds == used <= seconds
    assert [i.rank for i in result.presented_items] == list(range(1, count+1))
    assert result.truncated_item_count == len(ranked)-count
    assert [i.tier for i in result.presented_items] == ["focus"]*min(count, 3) + ["radar"]*max(0,count-3)
    assert len(ranked) == 20


def test_budget_never_demotes_or_skips_and_empty_is_valid():
    from evals.intelligence_v1.budget import apply_budget
    from evals.intelligence_v1.contracts import BudgetPolicy

    assert apply_budget(items(), BudgetPolicy(max_read_seconds=179)).used_read_seconds == 90
    assert not apply_budget(items(), BudgetPolicy(max_read_seconds=89)).presented_items
    empty = apply_budget((), BudgetPolicy(max_read_seconds=420))
    assert empty.presented_items == () and empty.used_read_seconds == 0


def test_T15_budget_rejects_duplicate_predicted_main_slot():
    from evals.intelligence_v1.budget import apply_budget
    from evals.intelligence_v1.contracts import BudgetPolicy
    from evals.intelligence_v1.exceptions import ContractError

    ranked = items(2)
    repeated = tuple(i.model_copy(update={"predicted_event_id": "predicted:same"}) for i in ranked)
    with pytest.raises(ContractError, match="DUPLICATE_EVENT_SLOT"):
        apply_budget(repeated, BudgetPolicy(max_read_seconds=420))
    assert len(apply_budget(ranked, BudgetPolicy(max_read_seconds=420)).presented_items) == 2
