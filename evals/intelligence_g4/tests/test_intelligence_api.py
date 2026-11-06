"""Local API workflow; real-shaped inputs are authored mocks, never real RSS/license proof."""


import pytest

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

ORIGIN = {"Origin": "http://127.0.0.1:8000"}


def test_real_raw_snapshot_preserves_material_semantics_and_get_has_no_exposure(tmp_path):
    app, clock, _, _ = setup_app(tmp_path)
    with TestClient(app, base_url="http://127.0.0.1:8000", headers=ORIGIN) as client:
        response = save_persona(client)
        assert response.status_code == 201, response.text
        capture(app, clock)
        response = start(client)
        assert response.status_code == 202, response.text
        run = wait_run(client, response.json()["resource_id"])
        assert run["status"] == "completed", run
        response = client.get("/api/intelligence/briefings/latest")
        assert response.status_code == 200, response.text
        view = response.json()
        assert view["mode"] == "real" and view["evidence_status"] == "raw_news_only"
        assert view["deliveries"] == [] and view["display_order"] == [] and view["archive"]
        assert view["coverage"]["has_gap"] and view["history_scoring"] == "validated_sqlite_prefix_native_rules_v1"
        assert view["native_basis_sha256"] and view["history_prefix_sha256"]
        assert view["archive"][0]["content_kinds"] == ["feed_summary"]
        assert client.get("/api/intelligence/briefings/latest", headers={"If-None-Match": response.headers["etag"]}).status_code == 304
        item = view["archive"][0]
        details = client.get("/api/intelligence/events/detail", params=dict(briefing_id=view["id"],
            event_snapshot_id=item["event_snapshot_id"]))
        assert details.status_code == 200, details.text
        assert details.json()["opens_recorded_by_get"] is False
        assert details.json()["claims"][0]["attribution"]["attribution_kind"] == "secondary_material"
        assert client.get("/api/intelligence/interactions").json() == []
        assert client.get("/api/intelligence/archive").json() == view["archive"]
        assert client.get("/api/intelligence/coverage").json() == view["coverage"]


def test_developer_delivery_confirmations_are_append_only_idempotent_and_retractable(tmp_path):
    app, clock, _, _ = setup_app(tmp_path, mode="synthetic_development")
    with TestClient(app, base_url="http://127.0.0.1:8000", headers=ORIGIN) as client:
        assert save_persona(client).status_code == 201
        capture(app, clock, origin="synthetic")
        response = start(client)
        run = wait_run(client, response.json()["resource_id"])
        assert run["status"] == "completed", run
        view = client.get("/api/intelligence/briefings/latest").json()
        assert view["mode"] == "synthetic_development" and view["deliveries"]
        interactions = client.get("/api/intelligence/interactions").json()
        assert {e["kind"] for e in interactions} == {"included"}
        target = view["deliveries"][0]["id"]
        def interact(kind, key, **extra):
            return client.post("/api/intelligence/interactions", json=dict(**preconditions(client),
                idempotency_key=key, briefing_id=view["id"], expected_snapshot_version=view["version"],
                target_id=target, kind=kind,
                confirmation={"rendered": "viewport_visible", "opened": "detail_opened"}.get(kind, "explicit_user"), **extra))
        for kind in ("rendered", "opened", "ack", "dismiss"):
            response = interact(kind, kind)
            assert response.status_code == 201, response.text
            repeated = interact(kind, kind)
            assert repeated.status_code == 201 and repeated.json()["deduplicated"]
        rows = client.get("/api/intelligence/interactions").json()
        assert all(r["learned"] is False for r in rows)
        assert len([r for r in rows if r["kind"] == "opened"]) == 1
        ack = next(r for r in rows if r["kind"] == "ack")
        before_retract = clock()
        clock.advance()
        response = interact("retract", "retract", retracts_id=ack["id"])
        assert response.status_code == 201, response.text
        assert not any(r["kind"] == "retract" for r in client.get("/api/intelligence/interactions", params={"as_of": before_retract}).json())
        assert len(client.get("/api/intelligence/interactions").json()) == len(rows) + 1


@pytest.mark.parametrize("case,status,code", [("origin", 403, "G4_ORIGIN_FORBIDDEN"),
    ("host", 400, "G4_HOST_FORBIDDEN"), ("extra", 422, "G4_SCHEMA_INVALID"),
    ("size", 413, "G4_REQUEST_TOO_LARGE"), ("duplicate", 422, "G4_JSON_INVALID")])
def test_boundaries_reject_before_mutation(tmp_path, case, status, code):
    app, _, _, _ = setup_app(tmp_path)
    with TestClient(app, base_url="http://127.0.0.1:8000", headers=ORIGIN) as client:
        original = current_status(client)["head"]
        payload = dict(**preconditions(client), idempotency_key="persona", expected_persona_version=0, domain_interests=[])
        if case == "origin":
            response = client.post("/api/intelligence/persona", json=payload, headers={"Origin": "https://evil.example"})
        elif case == "host":
            response = client.post("/api/intelligence/persona", json=payload, headers={"Host": "evil.example"})
        elif case == "extra":
            response = client.post("/api/intelligence/persona", json={**payload, "tenant": "fake"})
        elif case == "size":
            response = client.post("/api/intelligence/persona", content=b"x" * 65537, headers={"Content-Type": "application/json"})
        else:
            response = client.post("/api/intelligence/persona", content=b'{"idempotency_key":"a","idempotency_key":"b"}',
                                   headers={"Content-Type": "application/json"})
        assert response.status_code == status and response.json()["code"] == code, response.text
        assert current_status(client)["head"] == original


def test_no_evidence_does_not_publish_and_missing_migration_is_explicit(tmp_path):
    app, _, _, _ = setup_app(tmp_path / "migrated")
    with TestClient(app, base_url="http://127.0.0.1:8000", headers=ORIGIN) as client:
        save_persona(client)
        response = start(client)
        assert response.status_code == 202, response.text
        run = wait_run(client, response.json()["resource_id"])
        assert run["status"] == "evidence_not_ready", run
        assert client.get("/api/intelligence/briefings/latest").status_code == 404
    app, _, _, _ = setup_app(tmp_path / "missing", migrated=False)
    with TestClient(app, base_url="http://127.0.0.1:8000", headers=ORIGIN) as client:
        assert client.get("/api/intelligence/status").json()["state"] == "migration_required"
        assert client.get("/api/health").status_code == 200
