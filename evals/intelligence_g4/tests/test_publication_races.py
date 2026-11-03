"""Persistent publication wins only a valid CAS; late/uncooperative computation cannot publish."""

import threading

import pytest
from cfaw_news.intelligence.document_store import add_coverage
from cfaw_news.intelligence.runtime import run as calculate
from cfaw_news.intelligence.runtime_control import Control
from cfaw_news.main import create_app

from .persistence_support import LocalClient as TestClient
from .persistence_support import (
    capture,
    current_status,
    preconditions,
    save_persona,
    setup_app,
    start,
    wait_run,
)

HEADERS = {"Origin": "http://127.0.0.1:8000"}


def published(client, app, clock):
    assert save_persona(client).status_code == 201
    capture(app, clock, origin="synthetic" if app.state.intelligence.origin == "synthetic" else "real")
    response = start(client)
    assert response.status_code == 202, response.text
    state = wait_run(client, response.json()["resource_id"])
    assert state["status"] == "completed", state
    return client.get("/api/intelligence/briefings/latest").json()


class Paused:
    def __init__(self):
        self.started, self.release, self.finished = threading.Event(), threading.Event(), threading.Event()
        self.calls = 0

    def __call__(self, raw, **kwargs):
        self.calls += 1
        self.started.set()
        try:
            assert self.release.wait(10)
            return calculate(raw, **kwargs)
        finally:
            self.finished.set()


def test_duplicate_post_joins_one_persisted_run(tmp_path):
    paused = Paused()
    app, clock, _, _ = setup_app(tmp_path, mode="synthetic_development", runtime=paused)
    with TestClient(app, base_url="http://127.0.0.1:8000", headers=HEADERS) as client:
        save_persona(client)
        capture(app, clock, origin="synthetic")
        response = start(client)
        try:
            assert paused.started.wait(5)
            repeated = start(client)
            assert repeated.status_code == 202 and repeated.json()["deduplicated"], repeated.text
            assert repeated.json()["resource_id"] == response.json()["resource_id"]
        finally:
            paused.release.set()
        state = wait_run(client, response.json()["resource_id"])
        assert state["status"] == "completed", state
        assert paused.calls == 1
        view = client.get("/api/intelligence/briefings/latest").json()
        again = client.post("/api/intelligence/briefings", content=response.request.content,
                            headers={"Content-Type": "application/json"})
        assert again.status_code == 202 and again.json()["deduplicated"]
        assert client.get("/api/intelligence/briefings/latest").json()["id"] == view["id"]


def test_persisted_cancel_prevents_late_publication_and_preserves_old_snapshot(tmp_path):
    app, clock, _, _ = setup_app(tmp_path, mode="synthetic_development")
    with TestClient(app, base_url="http://127.0.0.1:8000", headers=HEADERS) as client:
        before = published(client, app, clock)
        clock.advance()
        paused = Paused()
        app.state.intelligence.runtime = paused
        response = start(client, key="second")
        identifier = response.json()["resource_id"]
        try:
            assert paused.started.wait(5)
            current = client.get("/api/intelligence/runs/" + identifier).json()
            body = dict(**preconditions(client), idempotency_key="cancel", expected_run_version=current["version"])
            cancelled = client.post("/api/intelligence/runs/" + identifier + "/cancel", json=body)
            assert cancelled.status_code == 200, cancelled.text
            repeated = client.post("/api/intelligence/runs/" + identifier + "/cancel", json=body)
            assert repeated.status_code == 200 and repeated.json()["deduplicated"]
        finally:
            paused.release.set()
        assert paused.finished.wait(5)
        state = wait_run(client, identifier)
        assert state["status"] == "cancelled" and state["snapshot_id"] is None
        assert client.get("/api/intelligence/briefings/latest").json() == before


@pytest.mark.parametrize("change", ["persona", "document", "source_failed"])
def test_stale_and_source_failure_preserve_old_snapshot(tmp_path, change):
    app, clock, _, _ = setup_app(tmp_path, mode="synthetic_development")
    with TestClient(app, base_url="http://127.0.0.1:8000", headers=HEADERS) as client:
        before = published(client, app, clock)
        paused = Paused()
        app.state.intelligence.runtime = paused
        clock.advance()
        if change == "source_failed":
            with app.state.database.session.begin() as session:
                add_coverage(session, "official", clock(), clock(), clock(), "failed", "source_failed")
        response = start(client, key="second")
        try:
            assert paused.started.wait(5)
            if change == "persona":
                clock.advance()
                assert save_persona(client, key="updated", expected=1).status_code == 201
            elif change == "document":
                capture(app, clock, origin="synthetic", body="Atlas Tool releases local agent tooling with latency <= 10 ms.")
        finally:
            paused.release.set()
        state = wait_run(client, response.json()["resource_id"])
        assert state["status"] == ("evidence_not_ready" if change == "source_failed" else "stale"), state
        assert client.get("/api/intelligence/briefings/latest").json() == before


def test_timeout_even_if_computation_ignores_request_control_cannot_late_publish(tmp_path):
    app, clock, _, _ = setup_app(tmp_path, mode="synthetic_development")
    release, started, finished = threading.Event(), threading.Event(), threading.Event()
    def ignores_cancel(raw, *, expected_sha256, control):
        started.set()
        try:
            value = calculate(raw, expected_sha256=expected_sha256, control=Control())
            release.wait(5)
            return value
        finally:
            finished.set()
    with TestClient(app, base_url="http://127.0.0.1:8000", headers=HEADERS) as client:
        before = published(client, app, clock)
        app.state.intelligence.runtime = ignores_cancel
        app.state.intelligence.settings.intelligence_timeout_seconds = 0.05
        response = start(client, key="timeout")
        try:
            assert started.wait(5)
            state = wait_run(client, response.json()["resource_id"])
            assert state["status"] == "timed_out", state
        finally:
            release.set()
        assert finished.wait(10)
        assert client.get("/api/intelligence/briefings/latest").json() == before


def test_disk_failure_before_publication_commit_leaves_no_partial_delivery(tmp_path):
    app, clock, _, _ = setup_app(tmp_path, mode="synthetic_development")
    with TestClient(app, base_url="http://127.0.0.1:8000", headers=HEADERS) as client:
        before = published(client, app, clock)
        interactions = client.get("/api/intelligence/interactions").json()
        armed = dict(value=False)
        def fail_once(stage):
            if stage == "before_db_commit" and armed["value"]:
                armed["value"] = False
                raise OSError("injected disk failure")
        def compute(raw, **kwargs):
            result = calculate(raw, **kwargs)
            app.state.intelligence.store.fault = fail_once
            armed["value"] = True
            return result
        app.state.intelligence.runtime = compute
        response = start(client, key="disk-failure")
        state = wait_run(client, response.json()["resource_id"])
        assert state["status"] == "failed" and state["snapshot_id"] is None, state
        assert client.get("/api/intelligence/briefings/latest").json() == before
        assert client.get("/api/intelligence/interactions").json() == interactions


def test_restart_recovers_queued_run_and_keeps_completed_snapshot(tmp_path):
    app, clock, _, _ = setup_app(tmp_path)
    with TestClient(app, base_url="http://127.0.0.1:8000", headers=HEADERS) as client:
        before = published(client, app, clock)
        app.state.intelligence.launch = lambda _: None  # Simulate interruption after reservation, before worker launch.
        response = start(client, key="reserved")
        identifier = response.json()["resource_id"]
        assert client.get("/api/intelligence/runs/" + identifier).json()["status"] == "queued"
    renewed = create_app(app.state.intelligence.settings)
    renewed.state.intelligence.clock = clock
    renewed.state.intelligence.store.clock = clock
    with TestClient(renewed, base_url="http://127.0.0.1:8000", headers=HEADERS) as client:
        assert current_status(client)["state"] == "ready"
        assert client.get("/api/intelligence/runs/" + identifier).json()["status"] == "interrupted"
        assert client.get("/api/intelligence/briefings/latest").json() == before


def test_old_snapshot_refs_are_exact_and_double_click_does_not_double_count(tmp_path):
    app, clock, _, _ = setup_app(tmp_path, mode="synthetic_development")
    with TestClient(app, base_url="http://127.0.0.1:8000", headers=HEADERS) as client:
        old = published(client, app, clock)
        capture(app, clock, origin="synthetic", body="Atlas Tool releases local agent tooling with latency > 10 ms.")
        response = start(client, key="second")
        assert wait_run(client, response.json()["resource_id"])["status"] == "completed"
        new = client.get("/api/intelligence/briefings/latest").json()
        assert new["version"] == old["version"] + 1
        target = old["deliveries"][0]["id"]
        def click(key, **extra):
            body = dict(**preconditions(client), idempotency_key=key, briefing_id=old["id"],
                expected_snapshot_version=old["version"], target_id=target, kind="opened", confirmation="detail_opened")
            return client.post("/api/intelligence/interactions", json={**body, **extra})
        mismatch = click("wrong-snapshot", briefing_id=new["id"], expected_snapshot_version=new["version"])
        assert mismatch.status_code == 409
        assert click("wrong-version", expected_snapshot_version=new["version"]).status_code == 409
        first, again = click("open-one"), click("open-two")
        assert first.status_code == again.status_code == 201
        assert again.json()["deduplicated"] and first.json()["resource_id"] == again.json()["resource_id"]
        rows = client.get("/api/intelligence/interactions").json()
        assert len([r for r in rows if r["kind"] == "opened" and r["target_id"] == target]) == 1
        assert client.get("/api/intelligence/briefings/" + old["id"]).json() == old
