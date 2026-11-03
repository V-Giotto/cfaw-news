"""Loopback, shape, immutable references and deferred-body integrity boundaries."""

import asyncio
import json
import sqlite3

import pytest
from cfaw_news.intelligence.boundary import IntelligenceBoundary
from cfaw_news.intelligence.contracts import canonical
from cfaw_news.main import create_app
from fastapi.testclient import TestClient as RawClient

from .persistence_support import LocalClient as TestClient
from .persistence_support import current_status, preconditions, setup_app
from .test_publication_races import published

HEADERS = {"Origin": "http://127.0.0.1:8000"}


def test_remote_client_cannot_forge_local_host_and_origin(tmp_path):
    app, _, _, _ = setup_app(tmp_path)
    with RawClient(app, base_url="http://127.0.0.1:8000", headers=HEADERS,
                   client=("203.0.113.8", 50000)) as client:
        response = client.get("/api/intelligence/status")
        assert response.status_code == 403 and response.json()["code"] == "G4_LOCAL_CLIENT_REQUIRED"
        assert client.get("/api/health").status_code == 200  # Legacy API scope unchanged.


@pytest.mark.parametrize("kind,status", [("missing-origin", 403), ("mime", 415), ("old-policy", 422),
                                      ("bad-query", 422), ("future-time", 422), ("naive-time", 422)])
def test_additional_write_and_query_boundaries(tmp_path, kind, status):
    app, _, _, _ = setup_app(tmp_path)
    with TestClient(app, base_url="http://127.0.0.1:8000", headers=HEADERS) as client:
        head = current_status(client)["head"]
        if kind == "missing-origin":
            client.headers.pop("Origin")
            response = client.post("/api/intelligence/persona", json={})
        elif kind == "mime":
            response = client.post("/api/intelligence/persona", content="{}", headers={"Content-Type": "text/plain"})
        elif kind == "old-policy":
            response = client.post("/api/intelligence/briefings", json=dict(**preconditions(client),
                idempotency_key="old", expected_latest_version=0, persona_version_id="unknown",
                runtime_policy_sha256="0" * 64, profile="focus70-radar30-v1"))
            assert response.json()["code"] == "G4_RUNTIME_CONFIG_PIN_MISMATCH"
        elif kind == "bad-query":
            response = client.get("/api/intelligence/status?tenant=somebody")
        else:
            response = client.get("/api/intelligence/interactions", params={"as_of":
                "2099-01-01T00:00:00Z" if kind == "future-time" else "2026-01-01T00:00:00"})
        assert response.status_code == status, response.text
        assert current_status(client)["head"] == head


def test_bad_anchor_is_unavailable_without_losing_last_snapshot(tmp_path):
    app, clock, _, anchor = setup_app(tmp_path)
    with TestClient(app, base_url="http://127.0.0.1:8000", headers=HEADERS) as client:
        before = published(client, app, clock)
        original = anchor.read_bytes()
        value = json.loads(original)
        value["heads"]["real:local"]["sha256"] = "0" * 64
        anchor.write_bytes(canonical(value))
        assert client.get("/api/intelligence/status").json()["state"] == "unavailable"
        response = client.get("/api/intelligence/briefings/latest")
        assert response.status_code == 503 and response.json()["code"] == "G4_TRUSTED_HEAD_MISMATCH"
        assert client.get("/api/health").status_code == 200
        anchor.write_bytes(original)
        assert client.get("/api/intelligence/briefings/latest").json() == before


def test_corrupted_deferred_evidence_body_never_reaches_detail(tmp_path):
    app, clock, path, _ = setup_app(tmp_path)
    with TestClient(app, base_url="http://127.0.0.1:8000", headers=HEADERS) as client:
        before = published(client, app, clock)
    # Simulate offline file-level corruption, restoring the exact immutable trigger definition.
    with sqlite3.connect(path) as connection:
        trigger = connection.execute("SELECT sql FROM sqlite_master WHERE name='intelligence_snapshots_no_update'").fetchone()[0]
        connection.execute("DROP TRIGGER intelligence_snapshots_no_update")
        value = json.loads(connection.execute("SELECT runtime FROM intelligence_snapshots").fetchone()[0])
        value["input"]["versions"][0]["content"]["paragraphs"][0] = "Corrupted evidence body"
        connection.execute("UPDATE intelligence_snapshots SET runtime=?", (json.dumps(value),))
        connection.execute(trigger)
    renewed = create_app(app.state.intelligence.settings)
    renewed.state.intelligence.clock = clock
    renewed.state.intelligence.store.clock = clock
    with TestClient(renewed, base_url="http://127.0.0.1:8000", headers=HEADERS) as client:
        response = client.get("/api/intelligence/events/detail", params=dict(briefing_id=before["id"],
            event_snapshot_id=before["archive"][0]["event_snapshot_id"]))
        assert response.status_code == 503 and response.json()["code"] == "G4_SNAPSHOT_PAYLOAD_MISMATCH"


def test_request_concurrency_and_chunked_body_are_bounded():
    async def check():
        entered, release = asyncio.Event(), asyncio.Event()
        async def app(scope, receive, send):
            await send(dict(type="http.response.start", status=200, headers=[]))
            await send(dict(type="http.response.body", body=b"{}"))
        boundary = IntelligenceBoundary(app, origins=HEADERS.values(), max_body=32, max_requests=1)
        scope = dict(type="http", path="/api/intelligence/persona", method="POST", client=("127.0.0.1", 1),
            query_string=b"", headers=[(b"host", b"127.0.0.1:8000"), (b"origin", HEADERS["Origin"].encode()),
                                     (b"content-type", b"application/json")])
        async def slow_receive():
            entered.set()
            await release.wait()
            return dict(type="http.request", body=b"{}", more_body=False)
        first, second = [], []
        async def first_send(message):
            first.append(message)
        async def second_send(message):
            second.append(message)
        task = asyncio.create_task(boundary(scope, slow_receive, first_send))
        await entered.wait()
        await boundary(scope, slow_receive, second_send)
        assert second[0]["status"] == 429
        release.set()
        await task
        assert first[0]["status"] == 200 and boundary.active == 0
        async def oversized():
            return dict(type="http.request", body=b"x" * 33, more_body=True)
        second.clear()
        await boundary(scope, oversized, second_send)
        assert second[0]["status"] == 413 and boundary.active == 0
    asyncio.run(check())


def test_configured_local_origin_preflight_is_scoped_to_intelligence(tmp_path):
    app, _, _, _ = setup_app(tmp_path)
    from cfaw_news.intelligence.boundary import IntelligenceBoundary
    for middleware in app.user_middleware:
        if middleware.cls is IntelligenceBoundary:
            middleware.kwargs["origins"] = ("http://localhost:3000",)
    with TestClient(app, base_url="http://127.0.0.1:8000") as client:
        headers = {"Origin": "http://localhost:3000", "Access-Control-Request-Method": "POST",
                   "Access-Control-Request-Headers": "Content-Type"}
        response = client.options("/api/intelligence/persona", headers=headers)
        assert response.status_code == 204 and response.headers["access-control-allow-origin"] == "http://localhost:3000"
        response = client.post("/api/intelligence/persona", json={}, headers={"Origin": "http://localhost:3000"})
        assert response.status_code == 422 and response.headers["access-control-allow-origin"] == "http://localhost:3000"
        legacy = client.options("/api/goals", headers=headers)
        assert legacy.status_code == 400 and "access-control-allow-origin" not in legacy.headers
