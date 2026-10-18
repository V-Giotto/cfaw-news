"""Goal lifecycle regressions; all provider results are fixed lexical fixtures."""

import asyncio
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Event

import pytest
from cfaw_news.config import Settings
from cfaw_news.database import Goal, Run
from cfaw_news.main import create_app
from cfaw_news.providers import BaselineProvider
from cfaw_news.seed import DEMO_GOALS
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
FIELDS = ("name", "purpose", "scope", "constraints", "keywords", "trial_requested")


@pytest.fixture
def settings(tmp_path):
    return Settings(
        _env_file=None,
        root=ROOT,
        database_url=f"sqlite:///{(tmp_path / 'following.db').as_posix()}",
        llm_mode="baseline",
        archive_seed=True,
        news_auto_refresh=False,
        news_media_fetch=False,
        news_reading_fetch=False,
    )


def new_goal(client):
    response = client.post("/api/goals", json=DEMO_GOALS[0])
    assert response.status_code == 201
    return response.json()


def completed(client, goal):
    response = client.post(
        f"/api/goals/{goal['id']}/checks", json={"expected_version": goal["version"]}
    )
    assert response.status_code == 202
    run_id = response.json()["id"]
    for _ in range(200):
        result = client.get(f"/api/runs/{run_id}").json()
        if result["status"] not in {"queued", "running"}:
            assert result["status"] == "completed"
            return result
        time.sleep(0.01)
    pytest.fail("fixture run did not complete")


def interval(run):
    start = (datetime.now(timezone.utc) + timedelta(days=2)).replace(second=0, microsecond=0)
    return {
        "start": start.isoformat(),
        "end": (
            start + timedelta(minutes=run["result"]["proposal"]["duration_minutes"])
        ).isoformat(),
    }


def test_default_start_and_restart_have_no_example_goals(settings):
    assert settings.demo_seed is False
    for _ in range(2):
        with TestClient(create_app(settings)) as client:
            assert client.get("/api/goals").json() == []
            assert client.get("/api/goals?include_unfollowed=true").json() == []
            assert client.get("/api/config").json()["counts"]["goals"] == 0


def test_retire_examples_keeps_edited_goals_news_snapshots_decisions_and_schedules(settings):
    legacy = settings.model_copy(update={"demo_seed": True})
    with TestClient(create_app(legacy)) as client:
        demos = client.get("/api/goals").json()
        run = completed(client, demos[0])
        assert (
            client.post(f"/api/runs/{run['id']}/decisions", json={"choice": "watch"}).status_code
            == 200
        )
        assert client.post(f"/api/runs/{run['id']}/approve", json=interval(run)).status_code == 200
        edited = client.patch(
            f"/api/goals/{demos[1]['id']}",
            json={
                **{key: demos[1][key] for key in FIELDS},
                "purpose": "我亲自编辑过的目标应当保留",
                "expected_version": 1,
            },
        ).json()
        own = new_goal(client)  # Same name as a fixture, but explicitly user-created.
        before_run = client.get(f"/api/runs/{run['id']}").json()
        before_schedules = client.get("/api/schedules").json()
        before_articles = client.get("/api/articles").json()
    for _ in range(2):
        with TestClient(create_app(settings)) as client:
            goals = client.get("/api/goals").json()
            assert {g["id"] for g in goals} == {edited["id"], own["id"]}
            assert all(not g["is_demo"] for g in goals)
            assert client.get("/api/config").json()["counts"]["goals"] == 2
            with client.app.state.database.session() as session:
                assert session.get(Goal, demos[2]["id"]) is None  # Unused example is removed.
                retired = session.get(Goal, demos[0]["id"])
                assert retired.status == "unfollowed" and retired.version == 2
            assert client.get(f"/api/runs/{run['id']}").json() == before_run
            assert client.get("/api/schedules").json() == before_schedules
            assert client.get("/api/articles").json() == before_articles
            assert client.get("/api/runs").json()[0]["goal_name"] == demos[0]["name"]
            assert (
                client.post(
                    f"/api/goals/{demos[0]['id']}/follow", json={"expected_version": 2}
                ).status_code
                == 409
            )


def test_unfollow_preserves_history_and_calendar_with_reversible_versioned_follow(settings):
    with TestClient(create_app(settings)) as client:
        goal = new_goal(client)
        run = completed(client, goal)
        client.post(f"/api/runs/{run['id']}/decisions", json={"choice": "watch"})
        times = interval(run)
        schedule = client.post(f"/api/runs/{run['id']}/approve", json=times).json()
        before = client.get(f"/api/runs/{run['id']}").json()
        response = client.post(f"/api/goals/{goal['id']}/unfollow", json={"expected_version": 1})
        assert response.status_code == 200
        stopped = response.json()
        assert stopped["status"] == "unfollowed" and stopped["version"] == 2
        assert client.get("/api/goals").json() == []
        assert client.get("/api/config").json()["counts"]["goals"] == 0
        assert client.get("/api/goals?include_unfollowed=true").json()[0]["id"] == goal["id"]
        assert client.get(f"/api/runs/{run['id']}").json() == before
        assert client.get("/api/schedules").json() == [schedule["schedule"]]
        # Exact retries of an approved write retain calendar idempotency.
        retry = client.post(f"/api/runs/{run['id']}/approve", json=times)
        assert retry.status_code == 200 and retry.json()["created"] is False
        assert (
            client.post(f"/api/runs/{run['id']}/decisions", json={"choice": "handled"}).status_code
            == 409
        )
        assert (
            client.post(f"/api/goals/{goal['id']}/checks", json={"expected_version": 2}).status_code
            == 409
        )
        assert (
            client.patch(
                f"/api/goals/{goal['id']}",
                json={
                    **{key: goal[key] for key in FIELDS},
                    "expected_version": 2,
                    "status": "active",
                },
            ).status_code
            == 409
        )
        restored = client.post(
            f"/api/goals/{goal['id']}/follow", json={"expected_version": 2}
        ).json()
        assert restored["status"] == "active" and restored["version"] == 3
        assert all(restored[key] == goal[key] for key in FIELDS)
        assert len(client.get("/api/runs").json()) == 1  # Restore never starts inference.
    with TestClient(create_app(settings)) as client:
        assert client.get("/api/goals").json()[0]["version"] == 3
        assert client.get("/api/schedules").json() == [schedule["schedule"]]


def test_unfollow_and_restore_require_fresh_approval_for_old_proposals(settings):
    with TestClient(create_app(settings)) as client:
        goal = new_goal(client)
        run = completed(client, goal)
        client.post(f"/api/goals/{goal['id']}/unfollow", json={"expected_version": 1})
        assert client.post(f"/api/runs/{run['id']}/approve", json=interval(run)).status_code == 409
        client.post(f"/api/goals/{goal['id']}/follow", json={"expected_version": 2})
        assert client.post(f"/api/runs/{run['id']}/approve", json=interval(run)).status_code == 409
        assert client.get("/api/schedules").json() == []


def test_following_transitions_are_idempotent_and_stale_writes_cannot_cancel_restored_goals(
    settings,
):
    with TestClient(create_app(settings)) as client:
        goal = new_goal(client)
        route = f"/api/goals/{goal['id']}"
        assert client.post(route + "/unfollow", json={"expected_version": 999}).status_code == 409
        assert client.post(route + "/unfollow", json={}).status_code == 422
        assert (
            client.post("/api/goals/missing/unfollow", json={"expected_version": 1}).status_code
            == 404
        )
        first = client.post(route + "/unfollow", json={"expected_version": 1}).json()
        assert client.post(route + "/unfollow", json={"expected_version": 1}).json() == first
        assert client.post(route + "/follow", json={"expected_version": 1}).status_code == 409
        restored = client.post(route + "/follow", json={"expected_version": 2}).json()
        assert restored["version"] == 3
        assert client.post(route + "/follow", json={"expected_version": 2}).json() == restored
        assert client.post(route + "/unfollow", json={"expected_version": 1}).status_code == 409
        assert client.get("/api/goals").json()[0]["version"] == 3


def test_unfollow_blocks_late_publication_even_after_restore_and_ignored_task_cancellation(
    settings,
):
    entered, release = Event(), Event()

    class IgnoresCancellation(BaselineProvider):
        async def judge(self, snapshot):
            entered.set()
            while not release.is_set():
                try:
                    await asyncio.sleep(0.01)
                except asyncio.CancelledError:
                    pass
            return await super().judge(snapshot)

    with TestClient(create_app(settings, IgnoresCancellation())) as client:
        goal = new_goal(client)
        run = client.post(f"/api/goals/{goal['id']}/checks", json={"expected_version": 1}).json()
        try:
            assert entered.wait(2)
            stopped = client.post(
                f"/api/goals/{goal['id']}/unfollow", json={"expected_version": 1}
            ).json()
            assert stopped["version"] == 2
            assert (
                client.post(
                    f"/api/goals/{goal['id']}/follow", json={"expected_version": 2}
                ).status_code
                == 200
            )
        finally:
            release.set()
        for _ in range(200):
            if run["id"] not in client.app.state.run_engine.tasks:
                break
            time.sleep(0.01)
        else:
            pytest.fail("late fixture inference did not return")
        stored = client.get(f"/api/runs/{run['id']}").json()
        assert stored["status"] == "cancelled" and stored["result"] is None
        assert stored["finished_at"]
        with client.app.state.database.session() as session:
            assert session.get(Run, run["id"]).cancel_requested
        assert client.get("/api/schedules").json() == []


def test_unfollow_cancels_queued_job_without_cancelling_another_goals_running_job(settings):
    entered, release = Event(), Event()

    class WaitForRelease(BaselineProvider):
        async def judge(self, snapshot):
            entered.set()
            while not release.is_set():
                await asyncio.sleep(0.01)
            return await super().judge(snapshot)

    configured = settings.model_copy(update={"max_concurrent_checks": 1})
    with TestClient(create_app(configured, WaitForRelease())) as client:
        first, second = new_goal(client), new_goal(client)
        first_run = client.post(
            f"/api/goals/{first['id']}/checks", json={"expected_version": 1}
        ).json()
        try:
            assert entered.wait(2)
            queued = client.post(
                f"/api/goals/{second['id']}/checks", json={"expected_version": 1}
            ).json()
            assert client.get(f"/api/runs/{queued['id']}").json()["status"] == "queued"
            assert (
                client.post(
                    f"/api/goals/{second['id']}/unfollow", json={"expected_version": 1}
                ).status_code
                == 200
            )
            assert client.get(f"/api/runs/{queued['id']}").json()["status"] == "cancelled"
            assert client.get(f"/api/runs/{first_run['id']}").json()["status"] == "running"
        finally:
            release.set()
