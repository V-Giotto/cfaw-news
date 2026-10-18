import asyncio
import json
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select, update

from . import __version__
from .config import Settings
from .database import (
    Article,
    ArticleMedia,
    Database,
    Decision,
    Goal,
    Run,
    RunEvent,
    Schedule,
    add_event,
    goal_dict,
    run_dict,
    utcnow,
)
from .following import FollowingConflict, change_following
from .ingestion import NewsIngestor
from .media import MediaCache
from .reading import ReadingCache
from .schemas import ApprovalInput, CheckInput, DecisionInput, GoalInput, GoalUpdate, RefreshInput
from .seed import seed
from .service import (
    TERMINAL,
    RunEngine,
    approve,
    build_run,
    require,
    retired_demo_evidence,
    schedule_dict,
)


def create_app(settings: Settings | None = None, provider=None):
    settings = settings or Settings()
    database = Database(settings.database_url)
    engine = RunEngine(database, settings, provider)
    news = NewsIngestor(database, settings.root)
    media = MediaCache(database, settings.root / ".local/media", enabled=settings.news_media_fetch)
    reading = ReadingCache(database, media, enabled=settings.news_reading_fetch)

    @asynccontextmanager
    async def lifespan(app):
        database.create()
        seed(database, settings.root, demo=settings.demo_seed, include_archive=settings.archive_seed)
        with database.session.begin() as session:
            for run in session.scalars(select(Run).where(Run.status.in_(["queued", "running"]))):
                run.status = "failed"
                run.error = "上次服务进程中断，本轮未完成；请重新检查"
                run.finished_at = utcnow()
                add_event(session, run.id, "failed", run.error)
        if settings.news_auto_refresh:
            news.start()
        media.start()
        reading.start()
        try:
            yield
        finally:
            await reading.close()
            await media.close()
            await news.close()
            await engine.close()
            database.engine.dispose()

    app = FastAPI(
        title="CFAW News",
        version=__version__,
        lifespan=lifespan,
        description="本地单用户的目标、证据与决定工作台。默认 BM25 开发基线。",
    )
    app.state.database = database
    app.state.run_engine = engine
    app.state.news_ingestor = news
    app.state.media_cache = media
    app.state.reading_cache = reading
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["GET", "POST", "PATCH"],
        allow_headers=["Content-Type", "Last-Event-ID"],
    )

    @app.get("/api/health")
    async def health():
        with database.session() as session:
            session.scalar(select(func.count()).select_from(Goal))
        return {"status": "ok", "version": __version__}

    @app.get("/api/config")
    async def config():
        with database.session() as session:
            counts = {
                "articles": session.scalar(select(func.count()).select_from(Article)),
                "goals": session.scalar(select(func.count()).select_from(Goal).where(Goal.status != "unfollowed")),
                "runs": session.scalar(select(func.count()).select_from(Run)),
            }
        return {
            "version": __version__,
            "mode": settings.llm_mode,
            "model": settings.llm_model if settings.llm_mode == "compatible" else None,
            "counts": counts,
            "scope": "local-single-user",
            "news_auto_refresh": settings.news_auto_refresh,
        }

    @app.get("/api/goals")
    async def goals(include_unfollowed: bool = False):
        with database.session() as session:
            result = []
            for goal in session.scalars(select(Goal).order_by(Goal.created_at)):
                if goal.status == "unfollowed" and not include_unfollowed:
                    continue
                latest = next(
                    (run for run in session.scalars(
                        select(Run).where(Run.goal_id == goal.id).order_by(Run.created_at.desc())
                    ) if not retired_demo_evidence(session, run)),
                    None,
                )
                result.append(
                    {
                        **goal_dict(goal),
                        "latest_run": run_dict(latest, include_snapshot=False) if latest else None,
                    }
                )
            return result

    @app.post("/api/goals", status_code=201)
    async def create_goal(body: GoalInput):
        with database.session.begin() as session:
            goal = Goal(data=body.model_dump())
            session.add(goal)
            session.flush()
            return goal_dict(goal)

    @app.patch("/api/goals/{goal_id}")
    async def edit_goal(goal_id: str, body: GoalUpdate):
        with database.session.begin() as session:
            goal = require(session, Goal, goal_id)
            if goal.status == "unfollowed":
                raise HTTPException(409, "目标已取消关注，请先恢复关注后再编辑")
            changed = session.execute(
                update(Goal)
                .where(Goal.id == goal_id, Goal.version == body.expected_version)
                .values(
                    data=body.model_dump(exclude={"expected_version", "status"}),
                    status=body.status,
                    version=body.expected_version + 1,
                    is_demo=False,
                )
            )
            if changed.rowcount != 1:
                raise HTTPException(409, "目标已被修改，请刷新后重试")
            return goal_dict(session.get(Goal, goal_id))

    async def set_following(goal_id, body, following):
        with database.session.begin() as session:
            goal = require(session, Goal, goal_id)
            try:
                goal, cancelled = change_following(
                    session, goal, body.expected_version, following=following
                )
            except FollowingConflict as exc:
                raise HTTPException(409, str(exc)) from None
            value = goal_dict(goal)
        # Persistence wins even if an inference task ignores cancellation.
        for run_id in cancelled:
            task = engine.tasks.get(run_id)
            if task:
                task.cancel()
        return value

    @app.post("/api/goals/{goal_id}/unfollow")
    async def unfollow_goal(goal_id: str, body: CheckInput):
        return await set_following(goal_id, body, False)

    @app.post("/api/goals/{goal_id}/follow")
    async def follow_goal(goal_id: str, body: CheckInput):
        return await set_following(goal_id, body, True)

    @app.post("/api/goals/{goal_id}/checks", status_code=202)
    async def start_check(goal_id: str, body: CheckInput):
        with database.session.begin() as session:
            run = build_run(
                session, require(session, Goal, goal_id), body.expected_version, settings.llm_mode
            )
            value = run_dict(run)
        engine.launch(run.id)
        return value

    @app.get("/api/runs")
    async def runs():
        with database.session() as session:
            return [
                {**run_dict(run, include_snapshot=False),
                 "goal_name": run.snapshot.get("goal", {}).get("name", "历史目标"),
                 "retired_demo_evidence": retired_demo_evidence(session, run)}
                for run in session.scalars(select(Run).order_by(Run.created_at.desc()).limit(100))
            ]

    @app.get("/api/runs/{run_id}")
    async def get_run(run_id: str):
        with database.session() as session:
            run = require(session, Run, run_id)
            decision = session.scalar(select(Decision).where(Decision.run_id == run_id))
            return {
                **run_dict(run),
                "retired_demo_evidence": retired_demo_evidence(session, run),
                "decision": {"choice": decision.choice, "reason": decision.reason}
                if decision
                else None,
            }

    @app.post("/api/runs/{run_id}/cancel")
    async def cancel(run_id: str):
        with database.session.begin() as session:
            run = require(session, Run, run_id)
            if run.status in TERMINAL:
                raise HTTPException(409, "本轮已经结束")
            run.cancel_requested = True
            run.status = "cancelled"
            run.finished_at = utcnow()
            add_event(session, run_id, "cancelled", "用户已取消；迟到结果不会发布")
        task = engine.tasks.get(run_id)
        if task:
            task.cancel()
        return {"status": "cancelled"}

    @app.get("/api/runs/{run_id}/events")
    async def events(run_id: str, request: Request):
        with database.session() as session:
            require(session, Run, run_id)
        try:
            cursor = int(request.headers.get("last-event-id", "0"))
        except ValueError:
            raise HTTPException(422, "事件游标必须是整数") from None

        async def stream():
            nonlocal cursor
            ticks = 0
            while not await request.is_disconnected():
                with database.session() as session:
                    rows = list(
                        session.scalars(
                            select(RunEvent)
                            .where(RunEvent.run_id == run_id, RunEvent.id > cursor)
                            .order_by(RunEvent.id)
                        )
                    )
                    current = session.get(Run, run_id)
                    finished = current.status in TERMINAL
                for row in rows:
                    cursor = row.id
                    payload = json.dumps(
                        {
                            "id": row.id,
                            "kind": row.kind,
                            "message": row.message,
                            "created_at": row.created_at,
                        },
                        ensure_ascii=False,
                    )
                    yield f"id: {row.id}\ndata: {payload}\n\n"
                if finished:
                    return
                ticks += 1
                if ticks % 40 == 0:
                    yield ": heartbeat\n\n"
                await asyncio.sleep(0.25)

        return StreamingResponse(
            stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @app.post("/api/runs/{run_id}/decisions")
    async def decide(run_id: str, body: DecisionInput):
        with database.session.begin() as session:
            run = require(session, Run, run_id)
            goal = require(session, Goal, run.goal_id)
            if run.status != "completed" or goal.status != "active" or goal.version != run.goal_version:
                raise HTTPException(409, "本轮尚未完成或目标已改变")
            if retired_demo_evidence(session, run):
                raise HTTPException(409, "本轮演示新闻已移除，请重新检查当前新闻")
            value = session.scalar(select(Decision).where(Decision.run_id == run.id))
            if value:
                value.choice, value.reason, value.created_at = body.choice, body.reason, utcnow()
            else:
                session.add(
                    Decision(
                        run_id=run.id,
                        goal_id=run.goal_id,
                        goal_version=run.goal_version,
                        basis_hash=run.basis_hash,
                        choice=body.choice,
                        reason=body.reason,
                    )
                )
            return body.model_dump()

    @app.post("/api/runs/{run_id}/approve")
    async def approve_proposal(run_id: str, body: ApprovalInput):
        value, created = approve(database, run_id, body)
        return {"schedule": value, "created": created}

    @app.get("/api/articles")
    async def articles(
        q: str = "",
        origin: str = "all",
        source_id: str = "",
        category: str = "",
        exclude_discovery: bool = False,
        limit: int = Query(default=200, ge=1, le=500),
        offset: int = Query(default=0, ge=0),
    ):
        with database.session() as session:
            rows = [row.data for row in session.scalars(select(Article))]
        result = sorted(
            [
                row
                for row in rows
                if (origin == "all" or row["origin"] == origin)
                and (not source_id or row.get("source_id") == source_id)
                and (not category or row.get("category") == category)
                and (not exclude_discovery or news.sources.get(row.get("source_id"), {}).get("display_role") != "discovery")
                and q.lower() in (row["title"] + row["summary"] + row["source"]).lower()
            ],
            key=lambda row: (
                row.get("published_at") or row.get("submitted_at") or row.get("updated_at") or "",
                row["id"],
            ),
            reverse=True,
        )[offset : offset + limit]
        return media.decorate(result)


    @app.get("/api/articles/{article_id}/reading")
    async def read_article(article_id: str):
        with database.session() as session:
            article = dict(require(session, Article, article_id).data)
        return reading.get(article)

    @app.get("/api/articles/{article_id}/reading/images/{image_index}")
    async def reading_image(article_id: str, image_index: int):
        try:
            file, kind = await reading.image(article_id, image_index)
        except (ValueError, OSError):
            raise HTTPException(404, "该正文图片暂不可用") from None
        return FileResponse(file, media_type=kind, headers={"Cache-Control": "public, max-age=86400", "X-Content-Type-Options": "nosniff"})
    @app.get("/api/articles/{article_id}/image")
    async def article_image(article_id: str):
        with database.session() as session:
            entry = session.get(ArticleMedia, article_id)
            data = dict(entry.data) if entry else {}
        path = media.cover_file(data)
        if not path:
            raise HTTPException(404, "该条目暂无可用配图")
        return FileResponse(
            path,
            media_type=data["content_type"],
            headers={"Cache-Control": "public, max-age=86400", "X-Content-Type-Options": "nosniff"},
        )

    @app.get("/api/sources")
    async def sources():
        return news.list_sources()

    @app.post("/api/sources/refresh")
    async def refresh_sources(body: RefreshInput):
        valid = set(news.sources)
        if any(source_id not in valid for source_id in body.source_ids):
            raise HTTPException(422, "只允许刷新目录内的来源")
        return {"results": await news.refresh(body.source_ids)}

    @app.get("/api/schedules")
    async def schedules():
        with database.session() as session:
            return [
                schedule_dict(value)
                for value in session.scalars(select(Schedule).order_by(Schedule.start))
            ]

    @app.post("/api/schedules/{schedule_id}/complete")
    async def complete_schedule(schedule_id: str):
        with database.session.begin() as session:
            value = require(session, Schedule, schedule_id)
            value.status = "completed"
            return schedule_dict(value)

    # One production-like local URL: built React assets are served by the Python app.
    dist = settings.root / "frontend/dist"
    if (dist / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")
    if (dist / "source-brands").is_dir():
        app.mount("/source-brands", StaticFiles(directory=dist / "source-brands"), name="source-brands")

    @app.get("/icon.svg", include_in_schema=False)
    async def icon():
        return FileResponse(settings.root / "frontend/public/icon.svg")

    @app.get("/", include_in_schema=False)
    async def index():
        if not (dist / "index.html").is_file():
            raise HTTPException(
                503, "前端尚未构建；请运行启动脚本或在 frontend 中执行 npm run build"
            )
        return FileResponse(dist / "index.html")

    return app
