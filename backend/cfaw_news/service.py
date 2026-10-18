import asyncio
import logging
import time
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select, text

from .database import (
    Article,
    Decision,
    Goal,
    Run,
    Schedule,
    add_event,
    fingerprint,
    goal_dict,
    utcnow,
)
from .providers import BaselineProvider, CompatibleProvider, ProviderError, validate_judgment
from .retrieval import search

TERMINAL = {"completed", "failed", "cancelled", "stale"}
logger = logging.getLogger(__name__)


def require(session, model, value):
    record = session.get(model, value)
    if record is None:
        raise HTTPException(404, "记录不存在")
    return record


def retired_demo_evidence(session, run: Run) -> bool:
    """Historical seed snapshots remain auditable but cannot become fresh context."""
    ids = {
        row["id"] for row in run.snapshot.get("evidence", [])
        if row.get("origin") == "archive" and row["id"].startswith("archive:")
    }
    if not ids:
        return False
    remaining = set(session.scalars(select(Article.id).where(Article.id.in_(ids))))
    return bool(ids - remaining)


def build_run(session, goal: Goal, expected_version: int, mode: str) -> Run:
    if goal.version != expected_version or goal.status != "active":
        raise HTTPException(409, "目标已修改、暂停或取消关注，请刷新后重试")
    running = session.scalar(
        select(Run).where(Run.goal_id == goal.id, Run.status.in_(["queued", "running"]))
    )
    if running:
        return running
    rows = [article.data for article in session.scalars(select(Article))]
    candidates = search(goal.data, rows)
    basis = fingerprint(sorted((row["id"], row["content_hash"]) for row in candidates))
    previous = next(
        (run for run in session.scalars(
            select(Run)
            .where(Run.goal_id == goal.id, Run.goal_version == goal.version, Run.status == "completed")
            .order_by(Run.created_at.desc())
        ) if not retired_demo_evidence(session, run)),
        None,
    )
    decision = session.scalar(
        select(Decision)
        .where(Decision.goal_id == goal.id, Decision.goal_version == goal.version)
        .order_by(Decision.created_at.desc())
        .limit(1)
    )
    if decision and retired_demo_evidence(session, session.get(Run, decision.run_id)):
        decision = None
    snapshot = {
        "goal": goal_dict(goal),
        "evidence": candidates,
        "corpus_count": len(rows),
        "basis_hash": basis,
        "retrieval_revision": "bm25-han-bigram-v1",
        "prompt_revision": "judgment-v1",
        "checked_at": utcnow(),
        "previous": {
            "run_id": previous.id,
            "basis_hash": previous.basis_hash,
            "result": previous.result,
        }
        if previous
        else None,
        "previous_decision": {
            "choice": decision.choice,
            "reason": decision.reason,
            "basis_hash": decision.basis_hash,
        }
        if decision
        else None,
    }
    run = Run(
        goal_id=goal.id, goal_version=goal.version, mode=mode, snapshot=snapshot, basis_hash=basis
    )
    session.add(run)
    session.flush()
    add_event(session, run.id, "queued", "检查已创建，正在等待执行")
    return run


def invalidation_reason(session, run: Run) -> str | None:
    goal = session.get(Goal, run.goal_id)
    if not goal or goal.version != run.goal_version or goal.status != "active":
        return "目标版本或状态已变化，请重新检查"
    for snapshot in run.snapshot["evidence"]:
        article = session.get(Article, snapshot["id"])
        if article is None or article.content_hash != snapshot["content_hash"]:
            return "本轮依据已更新，请重新检查"
    return None


def schedule_dict(value: Schedule) -> dict:
    return {
        key: getattr(value, key)
        for key in ("id", "run_id", "title", "content", "start", "end", "status", "created_at")
    }


def approve(database, run_id, approval) -> tuple[dict, bool]:
    with database.session.begin() as session:
        # SQLite starter: serialize the check-and-insert of calendar intervals.
        if database.engine.dialect.name == "sqlite":
            session.execute(text("BEGIN IMMEDIATE"))
        run = require(session, Run, run_id)
        if run.status != "completed" or not run.result or not run.result.get("proposal"):
            raise HTTPException(409, "本轮没有可以批准的提议")
        proposal = run.result["proposal"]
        proposal_key = fingerprint([run.goal_id, run.goal_version, run.basis_hash, proposal])
        start = approval.start.astimezone(timezone.utc)
        end = approval.end.astimezone(timezone.utc)
        existing = session.scalar(select(Schedule).where(Schedule.proposal_key == proposal_key))
        if existing:
            if existing.start != start.isoformat() or existing.end != end.isoformat():
                raise HTTPException(409, "这个提议已经导入；修改时间应编辑已有日程")
            return schedule_dict(existing), False
        reason = invalidation_reason(session, run)
        if reason:
            raise HTTPException(409, reason)
        decision = session.scalar(
            select(Decision)
            .where(Decision.goal_id == run.goal_id, Decision.goal_version == run.goal_version)
            .order_by(Decision.created_at.desc())
            .limit(1)
        )
        if (
            decision
            and decision.choice in {"handled", "dismissed"}
            and (decision.basis_hash == run.basis_hash or not run.result.get("material_change"))
        ):
            raise HTTPException(409, "该目标已记录处理/不采纳决定，请重新检查后再提出安排")
        if start <= datetime.now(timezone.utc):
            raise HTTPException(422, "请选择未来的时间")
        if (end - start).total_seconds() != proposal["duration_minutes"] * 60:
            raise HTTPException(422, "安排时长必须与已预览的提议一致")
        conflict = session.scalar(
            select(Schedule.id)
            .where(
                Schedule.status == "planned",
                Schedule.start < end.isoformat(),
                Schedule.end > start.isoformat(),
            )
            .limit(1)
        )
        if conflict:
            raise HTTPException(409, "与已有日程冲突，请选择其他时段")
        value = Schedule(
            proposal_key=proposal_key,
            run_id=run.id,
            title=proposal["title"],
            content=proposal["content"],
            start=start.isoformat(),
            end=end.isoformat(),
        )
        session.add(value)
        session.flush()
        add_event(session, run.id, "approved", "用户确认后已保存应用内日程")
        return schedule_dict(value), True


class RunEngine:
    def __init__(self, database, settings, provider=None):
        self.database = database
        self.provider = provider or (
            BaselineProvider() if settings.llm_mode == "baseline" else CompatibleProvider(settings)
        )
        self.semaphore = asyncio.Semaphore(settings.max_concurrent_checks)
        self.tasks = {}

    def launch(self, run_id):
        if run_id not in self.tasks:
            task = asyncio.create_task(self.execute(run_id))
            self.tasks[run_id] = task
            task.add_done_callback(lambda _: self.tasks.pop(run_id, None))

    def mark(self, run_id, status, message, metrics=None):
        with self.database.session.begin() as session:
            run = session.get(Run, run_id)
            if run and metrics is not None:
                run.metrics = metrics
            if run and run.status not in TERMINAL:
                run.status = status
                if status in TERMINAL:
                    run.finished_at = utcnow()
                    if status == "failed":
                        run.error = message
                add_event(session, run_id, status, message)

    async def execute(self, run_id):
        started = time.perf_counter()
        candidate_count = 0

        def telemetry(metrics):
            return {
                **metrics,
                "elapsed_ms": round((time.perf_counter() - started) * 1000),
                "candidate_count": candidate_count,
            }

        try:
            async with self.semaphore:
                with self.database.session.begin() as session:
                    run = require(session, Run, run_id)
                    if run.status in TERMINAL or run.cancel_requested:
                        return
                    reason = invalidation_reason(session, run)
                    if reason:
                        run.status = "stale"
                        run.finished_at = utcnow()
                        add_event(session, run_id, "stale", reason)
                        return
                    run.status = "running"
                    snapshot = run.snapshot
                    candidate_count = len(snapshot["evidence"])
                    add_event(
                        session,
                        run_id,
                        "retrieval",
                        f"召回 {len(snapshot['evidence'])} 篇候选，已保存证据快照",
                    )
                    add_event(
                        session,
                        run_id,
                        "analysis",
                        "没有候选，本轮跳过模型调用" if not candidate_count else (
                            "执行词法基线" if run.mode == "baseline"
                            else "正在请求模型进行语义判断"
                        ),
                    )
                if snapshot["evidence"]:
                    result, metrics = await self.provider.judge(snapshot)
                else:
                    result, metrics = await BaselineProvider().judge(snapshot)
                    metrics["model_called"] = False
                validate_judgment(result, snapshot)
                with self.database.session.begin() as session:
                    run = require(session, Run, run_id)
                    # Retain actual request costs even when publication has become invalid.
                    run.metrics = telemetry(metrics)
                    if run.cancel_requested or run.status in TERMINAL:
                        return
                    reason = invalidation_reason(session, run)
                    if reason:
                        run.status = "stale"
                        run.finished_at = utcnow()
                        add_event(session, run_id, "stale", reason)
                        return
                    # A decision may have been made while inference was running.
                    decision = session.scalar(
                        select(Decision)
                        .where(
                            Decision.goal_id == run.goal_id,
                            Decision.goal_version == run.goal_version,
                            Decision.basis_hash == run.basis_hash,
                        )
                        .order_by(Decision.created_at.desc())
                        .limit(1)
                    )
                    if decision:
                        result.proposal = None
                    run.result = result.model_dump()
                    run.status = "completed"
                    run.finished_at = utcnow()
                    add_event(session, run_id, "completed", "验证完成，结果已保存")
        except asyncio.CancelledError as exc:
            metrics = telemetry(getattr(exc, "metrics", {}))
            self.mark(
                run_id, "failed", "服务停止，本轮未完成；已完成的历史结果仍可查看", metrics
            )
            raise
        except ProviderError as exc:
            logger.error("Run %s failed (provider:%s)", run_id, exc.code)
            self.mark(run_id, "failed", str(exc), telemetry(exc.metrics))
        except Exception as exc:
            logger.error("Run %s failed (%s)", run_id, type(exc).__name__)
            # Never persist response bodies, prompts or credentials from provider exceptions.
            message = (
                "本轮结果未通过校验；请调整条件后重试" if isinstance(exc, ValueError)
                else "检查失败，请查看服务端日志并重试"
            )
            self.mark(run_id, "failed", message, telemetry({"error_code": "internal"}))

    async def close(self):
        tasks = list(self.tasks.values())
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
