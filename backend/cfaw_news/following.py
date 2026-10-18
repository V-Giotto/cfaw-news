"""Goal following transitions, independent of HTTP and UI."""

from sqlalchemy import select, update

from .database import Decision, Goal, Run, add_event, utcnow


class FollowingConflict(ValueError):
    pass


def change_following(session, goal, expected_version, *, following):
    """Versioned, idempotent transition; retain historical evidence and schedules."""
    currently_following = goal.status != "unfollowed"
    if following and not currently_following and goal.is_demo:
        raise FollowingConflict("示例目标已清理，请新建自己的关注目标")
    if following == currently_following:
        return goal, []  # Retrying a completed transition does not bump versions.
    changed = session.execute(
        update(Goal)
        .where(Goal.id == goal.id, Goal.version == expected_version)
        .values(status="active" if following else "unfollowed", version=expected_version + 1)
    )
    if changed.rowcount != 1:
        raise FollowingConflict("目标已被修改，请刷新后重试")
    session.refresh(goal)
    cancelled = []
    if not following:
        for run in session.scalars(
            select(Run).where(Run.goal_id == goal.id, Run.status.in_(["queued", "running"]))
        ):
            run.cancel_requested = True
            run.status = "cancelled"
            run.finished_at = utcnow()
            add_event(session, run.id, "cancelled", "目标已取消关注；迟到结果不会发布")
            cancelled.append(run.id)
    return goal, cancelled


def retire_demo_goals(session):
    """Keep foreign-key history while removing untouched fixtures from daily use."""
    for goal in session.scalars(select(Goal).where(Goal.is_demo.is_(True))):
        has_history = session.scalar(select(Run.id).where(Run.goal_id == goal.id).limit(1))
        has_decision = session.scalar(
            select(Decision.id).where(Decision.goal_id == goal.id).limit(1)
        )
        if not has_history and not has_decision:
            session.delete(goal)
        elif goal.status != "unfollowed":
            change_following(session, goal, goal.version, following=False)
