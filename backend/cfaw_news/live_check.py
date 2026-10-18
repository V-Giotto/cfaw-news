"""Opt-in real-provider acceptance check using public archive evidence and isolated storage."""

import argparse
import asyncio
import json
import time
from urllib.parse import urlsplit

import httpx
from sqlalchemy import select

from .config import ROOT, Settings
from .database import Database, Goal, identifier, utcnow
from .main import create_app
from .providers import validate_judgment
from .schemas import Judgment
from .seed import DEMO_GOALS, seed
from .service import build_run


class CheckFailure(Exception):
    pass


def require_check(condition, name, report):
    report["checks"][name] = bool(condition)
    if not condition:
        raise CheckFailure(name)


async def wait_run(client, run_id, timeout):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        response = await client.get(f"/api/runs/{run_id}")
        response.raise_for_status()
        run = response.json()
        if run["status"] not in {"queued", "running"}:
            return run
        await asyncio.sleep(0.1)
    await client.post(f"/api/runs/{run_id}/cancel")
    raise CheckFailure("acceptance_timeout")


def preview_check(settings, output_dir):
    """Create an inspectable public payload without starting an event loop or model request."""
    database = Database("sqlite:///:memory:")
    database.create()
    try:
        seed(database, settings.root, demo=True, include_archive=True)
        with database.session.begin() as session:
            goal = session.scalar(select(Goal).order_by(Goal.created_at))
            snapshot = build_run(session, goal, goal.version, "compatible").snapshot
        preview = {
            "model_called": False,
            "endpoint_host": urlsplit(settings.llm_base_url).hostname,
            "requested_model": settings.llm_model,
            "max_tokens_per_request": settings.llm_max_tokens,
            "maximum_requests": 2,
            "prompt_file": "backend/cfaw_news/prompts/judgment.v1.txt",
            "output_schema": Judgment.model_json_schema(),
            "snapshot": snapshot,
            "scope": "public demo goal and frozen archive only; no personal records",
        }
        path = output_dir / "request-preview.json"
        path.write_text(json.dumps(preview, ensure_ascii=False, indent=2), encoding="utf-8")
        return path
    finally:
        database.engine.dispose()


async def run_check(settings, output_dir):
    """Exercise production routes and real network inference; never use the user's database."""
    database_path = output_dir / "check.db"
    isolated = settings.model_copy(update={
        "database_url": f"sqlite:///{database_path.as_posix()}",
        "news_auto_refresh": False,
        "news_media_fetch": False,
        "demo_seed": False,
        "archive_seed": True,
    })
    report = {
        "report_revision": "live-model-loop-v1",
        "started_at": utcnow(),
        "live_model_check_passed": False,
        "transport": "production ASGI routes in-process; real provider HTTPS",
        "evidence_scope": "public frozen archive captured 2026-10-13; not refetched",
        "semantic_quality_verified": False,
        "decision_origin": "scripted acceptance decision; not a personal user decision",
        "requested_model": settings.llm_model,
        "endpoint_host": urlsplit(settings.llm_base_url).hostname,
        "database": str(database_path),
        "checks": {},
    }
    try:
        app = create_app(isolated)
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app), base_url="http://acceptance.local"
            ) as client:
                report["config"] = (await client.get("/api/config")).json()
                require_check(report["config"]["mode"] == "compatible", "compatible_mode", report)
                response = await client.post("/api/goals", json=DEMO_GOALS[0])
                response.raise_for_status()
                goal = response.json()
                response = await client.post(
                    f"/api/goals/{goal['id']}/checks", json={"expected_version": goal["version"]}
                )
                response.raise_for_status()
                run = await wait_run(client, response.json()["id"], 2 * settings.llm_timeout_seconds + 20)
                report["run"] = run
                require_check(run["status"] == "completed", "real_run_completed", report)
                require_check(run["metrics"].get("model_called") is True, "model_called", report)
                require_check(
                    run["metrics"].get("validation_passed") is True, "output_validated", report
                )
                result = validate_judgment(Judgment.model_validate(run["result"]), run["snapshot"])
                report["resolved_citations"] = []
                for ref in result.citations:
                    article = next(
                        row for row in run["snapshot"]["evidence"] if row["id"] == ref.article_id
                    )
                    paragraph = (
                        {"id": "summary", "text": article["summary"], "kind": "summary"}
                        if ref.paragraph_id == "summary" else next(
                            row for row in article["paragraphs"] if row["id"] == ref.paragraph_id
                        )
                    )
                    report["resolved_citations"].append({
                        "article_id": article["id"], "source_url": article["source_url"],
                        "content_hash": article["content_hash"], **paragraph,
                    })
                require_check(bool(report["resolved_citations"]), "citations_resolved", report)
                require_check(
                    (await client.get("/api/schedules")).json() == [], "no_automatic_schedule", report
                )
                response = await client.post(
                    f"/api/runs/{run['id']}/decisions",
                    json={"choice": "watch", "reason": "隔离验收脚本：保存观察决定，等待核实适用条件。"},
                )
                response.raise_for_status()
                saved = (await client.get(f"/api/runs/{run['id']}")).json()
                report["decision"] = saved["decision"]
                require_check(saved["decision"]["choice"] == "watch", "decision_saved", report)

                empty_goal = (await client.post("/api/goals", json={
                    "name": "zzquux123", "purpose": "xyzzy987 zwibb123",
                })).json()
                empty_run = (await client.post(
                    f"/api/goals/{empty_goal['id']}/checks", json={"expected_version": 1}
                )).json()
                empty_run = await wait_run(client, empty_run["id"], 10)
                report["no_candidate_run"] = empty_run
                require_check(
                    empty_run["status"] == "completed"
                    and empty_run["metrics"].get("model_called") is False
                    and empty_run["metrics"].get("request_count", 0) == 0
                    and empty_run["result"]["proposal"] is None,
                    "no_candidate_skips_model", report,
                )
        restarted = create_app(isolated)
        async with restarted.router.lifespan_context(restarted):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(restarted), base_url="http://acceptance.local"
            ) as client:
                restored = (await client.get(f"/api/runs/{run['id']}")).json()
                require_check(
                    restored["status"] == "completed"
                    and restored["result"] == run["result"]
                    and restored["snapshot"] == run["snapshot"]
                    and restored["metrics"] == run["metrics"]
                    and restored["decision"] == saved["decision"],
                    "result_evidence_metrics_decision_survive_restart", report,
                )
                require_check(
                    (await client.get("/api/schedules")).json() == [], "schedules_stay_empty", report
                )
        report["live_model_check_passed"] = True
    except CheckFailure as exc:
        report["failure"] = str(exc)
    except Exception as exc:
        # Do not print exception details, response bodies, environment or request headers.
        report["failure"] = type(exc).__name__
    finally:
        report["finished_at"] = utcnow()
        (output_dir / "report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group()
    action.add_argument(
        "--run", action="store_true",
        help="Send public demo evidence to the configured provider (at most two paid requests).",
    )
    action.add_argument(
        "--preview", action="store_true", help="Save a public payload preview without inference.",
    )
    args = parser.parse_args()
    try:
        settings = Settings()
    except Exception:
        print(json.dumps({"ready": False, "error": "invalid_local_configuration"}))
        return 1
    ready = settings.llm_mode == "compatible"
    if args.preview:
        output_dir = ROOT / ".local/live-checks" / identifier()
        output_dir.mkdir(parents=True)
        path = preview_check(settings, output_dir)
        print(json.dumps({"preview": str(path), "model_called": False}))
        return 0
    if not args.run or not ready:
        print(json.dumps({
            "ready": ready, "mode": settings.llm_mode, "model": settings.llm_model,
            "key_present": bool(settings.llm_api_key.get_secret_value()),
            "model_called": False,
            "next_step": "Use --run to perform the isolated real-provider check.",
        }))
        return 0 if ready else 1
    output_dir = ROOT / ".local/live-checks" / identifier()
    output_dir.mkdir(parents=True)
    report = asyncio.run(run_check(settings, output_dir))
    print(json.dumps({
        "passed": report["live_model_check_passed"],
        "report": str(output_dir / "report.json"),
        "failure": report.get("failure"),
    }))
    return 0 if report["live_model_check_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
