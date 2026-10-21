"""One deterministic ranked-prefix reading budget for every baseline."""

from .contracts import BudgetPresentation, PresentedItem
from .exceptions import ContractError


def apply_budget(ranked_items, policy):
    ids = [i.predicted_event_id for i in ranked_items if i.predicted_event_id is not None]
    if len(set(ids)) != len(ids):
        raise ContractError("DUPLICATE_EVENT_SLOT")
    used, presented, reason = 0, [], "exhausted_ranking"
    for position, item in enumerate(ranked_items):
        if position >= policy.max_focus+policy.max_radar:
            reason = "card_limit"
            break
        focus = position < policy.max_focus
        seconds = policy.focus_seconds if focus else policy.radar_seconds
        if used+seconds > policy.max_read_seconds:
            reason = "reading_budget"
            break
        presented.append(PresentedItem(rank=item.rank, doc_version_ids=item.doc_version_ids,
            representative_doc_version_id=item.representative_doc_version_id,
            predicted_event_id=item.predicted_event_id, tier="focus" if focus else "radar",
            estimated_read_seconds=seconds))
        used += seconds
    return BudgetPresentation(budget_seconds=policy.max_read_seconds, used_read_seconds=used,
        presented_items=tuple(presented), truncated_item_count=len(ranked_items)-len(presented),
        stop_reason=reason)
