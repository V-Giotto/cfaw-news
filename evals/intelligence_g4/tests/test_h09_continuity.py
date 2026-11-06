"""Real isolated SQLite/native continuity. Materials here are authored engineering mocks."""

import threading
from copy import deepcopy
from datetime import timedelta

import pytest
from cfaw_news.intelligence.persistence_models import BriefingSnapshot, InteractionRow
from cfaw_news.intelligence.runtime import run
from cfaw_news.intelligence.runtime_contracts import RuntimeConfig, RuntimeEnvelope
from sqlalchemy import select

from evals.intelligence_g2.contracts import json_bytes
from evals.intelligence_v1.hashing import sha256_bytes

from .persistence_support import (
    LocalClient,
    capture,
    current_status,
    preconditions,
    setup_app,
    start,
    wait_run,
)


def save(client, clock, budget, version):
    clock.advance()
    response = client.post("/api/intelligence/persona", json=dict(**preconditions(client),
        idempotency_key=f"p-{version}", expected_persona_version=version - 1,
        attention_budget_seconds=budget, domain_interests=["agent tooling"]))
    assert response.status_code == 201, response.text


def generate(client, key):
    response = start(client, key=key)
    assert response.status_code == 202, response.text
    terminal = wait_run(client, response.json()["resource_id"], timeout=60)
    assert terminal["status"] == "completed", terminal
    return client.get("/api/intelligence/briefings/" + terminal["snapshot_id"]).json()


def interact(client, snapshot, target, kind, key, retracts=None):
    payload = dict(**preconditions(client), idempotency_key=key, briefing_id=snapshot["id"],
        expected_snapshot_version=snapshot["version"], target_id=target, kind=kind,
        confirmation={"opened": "detail_opened", "rendered": "viewport_visible"}.get(kind, "explicit_user"))
    if retracts:
        payload["retracts_id"] = retracts
    response = client.post("/api/intelligence/interactions", json=payload)
    assert response.status_code == 201, response.text
    return response.json()["resource_id"]


def runtime(app, identifier):
    with app.state.database.session() as session:
        return session.get(BriefingSnapshot, identifier).runtime


@pytest.mark.parametrize("late", [False, True])
def test_actual_budget_save_then_native_generation_preserves_identity_and_times(tmp_path, late):
    app, clock, _, _ = setup_app(tmp_path / "budget", mode="real", timeout=60)
    with LocalClient(app, base_url="http://127.0.0.1:8000", headers={"Origin": "http://127.0.0.1:8000"}) as client:
        if not late:
            save(client, clock, 420, 1)
        document = capture(app, clock)
        if late:
            save(client, clock, 420, 1)
        first = generate(client, "first")
        birth = first["archive"][0]["event_key"]
        for version, budget in enumerate((180, 900, 420), 2):
            save(client, clock, budget, version)
            current = generate(client, f"r-{version}")
            body = runtime(app, current["id"])
            assert current["history_scoring"] == "validated_sqlite_prefix_native_rules_v1"
            assert current["archive"][0]["event_key"] == birth
            assert body["input"]["versions"][0]["available_at"] == document.available_at
            assert body["input"]["config"]["attention_budget_seconds"] == budget
            assert body["stages"][-1]["replay_input"]["context"]["attention_budget_seconds"] == budget
            assert len(body["input"]["persona_history"]) == version
            assert all(s["replay_input"]["context"]["persona"]["available_at"] <= s["replay_input"]["context"]["as_of"]
                       for s in body["stages"])
            assert not current["deliveries"] and current["evidence_status"] == "raw_news_only"


@pytest.mark.parametrize("days", [1, 3, 7])
def test_actual_raw_open_budget_update_and_revisit_window(tmp_path, days):
    app, clock, _, _ = setup_app(tmp_path / "visit", mode="real", timeout=60)
    with LocalClient(app, base_url="http://127.0.0.1:8000", headers={"Origin": "http://127.0.0.1:8000"}) as client:
        save(client, clock, 420, 1)
        capture(app, clock)
        old = generate(client, "old")
        clock.advance()
        opened_at = clock()
        interact(client, old, old["archive"][0]["id"], "opened", "opened")
        clock.value += timedelta(days=days)
        save(client, clock, 180, 2)
        new = generate(client, "new")
        body = runtime(app, new["id"])
        assert new["visit_window"]["basis"] == "last_confirmed_interaction"
        assert new["coverage"]["requested_start_at"] == opened_at.replace("+00:00", "Z").replace(".000000Z", "Z")
        assert body["context"]["journal"]["entries"] == []
        assert len(body["context"]["journal"]["ignored_archive_interaction_ids"]) == 1
        assert new["coverage"]["has_gap"] and not new["deliveries"]


def test_unobserved_raw_snapshots_paginate_without_inventing_exposure(tmp_path):
    app, clock, _, _ = setup_app(tmp_path / "directory", mode="real", timeout=60)
    with LocalClient(app, base_url="http://127.0.0.1:8000", headers={"Origin": "http://127.0.0.1:8000"}) as client:
        save(client, clock, 420, 1)
        capture(app, clock)
        identifiers = []
        for i in range(3):
            clock.advance()
            identifiers.append(generate(client, f"r-{i}")["id"])
        before = current_status(client)["head"]
        first = client.get("/api/intelligence/briefings?limit=2").json()
        assert [r["id"] for r in first["items"]] == list(reversed(identifiers[1:]))
        clock.advance()
        generate(client, "extra")
        page = client.get("/api/intelligence/briefings", params=dict(limit=2,
            before_version=first["next_before_version"], through_version=first["through_version"])).json()
        assert [r["id"] for r in page["items"]] == identifiers[:1]
        assert page["next_before_version"] is None
        assert client.get("/api/intelligence/briefings/" + identifiers[0]).status_code == 200
        assert client.get("/api/intelligence/interactions").json() == []
        assert before["publication_version"] == 3
        with app.state.database.session() as session:
            assert not list(session.scalars(select(InteractionRow)))


def test_actual_delivered_history_ack_and_retract_feed_frozen_native_rules(tmp_path):
    app, clock, _, _ = setup_app(tmp_path / "scoring", mode="synthetic_development", timeout=60)
    with LocalClient(app, base_url="http://127.0.0.1:8000", headers={"Origin": "http://127.0.0.1:8000"}) as client:
        save(client, clock, 420, 1)
        capture(app, clock, origin="synthetic")
        old = generate(client, "old")
        assert old["deliveries"]
        target = old["deliveries"][0]["id"]
        clock.advance()
        interact(client, old, target, "opened", "open")
        save(client, clock, 180, 2)
        opened = generate(client, "opened-repeat")
        event = runtime(app, opened["id"])["ranking"]["events"][0]
        assert event["history"]["delivery_count"] == 1
        assert not event["history"]["declared_known"]

        assert event["features"]["duplicate"]["value"] > 0
        clock.advance()
        ack = interact(client, old, target, "ack", "ack")
        known = generate(client, "ack-repeat")
        event = runtime(app, known["id"])["ranking"]["events"][0]
        assert event["history"]["declared_known"]
        clock.advance()
        interact(client, old, target, "retract", "retract", ack)
        retracted = generate(client, "retracted-repeat")
        event = runtime(app, retracted["id"])["ranking"]["events"][0]
        assert not event["history"]["declared_known"]


def test_home_visit_is_separate_and_current_visit_does_not_crop_revisit_window(tmp_path):
    app, clock, _, _ = setup_app(tmp_path / "home-visit", mode="real", timeout=60)
    with LocalClient(app, base_url="http://127.0.0.1:8000", headers={"Origin": "http://127.0.0.1:8000"}) as client:
        save(client, clock, 420, 1)
        capture(app, clock)
        old = generate(client, "old")
        payload = dict(**preconditions(client), idempotency_key="visit-one", confirmation="home_visible",
                       session_key="session-one", briefing_id=old["id"])
        response = client.post("/api/intelligence/visits", json=payload)
        assert response.status_code == 201, response.text
        first = client.get("/api/intelligence/visits/latest").json()
        sequence = current_status(client)["head"]["sequence"]
        assert client.post("/api/intelligence/visits", json=payload).json()["deduplicated"]
        assert current_status(client)["head"]["sequence"] == sequence
        clock.value += timedelta(days=7)
        boundary = current_status(client)["head"]["sequence"]
        response = client.post("/api/intelligence/visits", json=dict(**preconditions(client),
            idempotency_key="visit-two", confirmation="home_visible", session_key="session-two", briefing_id=old["id"]))
        assert response.status_code == 201, response.text
        save(client, clock, 180, 2)
        status = current_status(client)
        response = client.post("/api/intelligence/briefings", json=dict(**preconditions(client),
            idempotency_key="after-revisit", persona_version_id=status["head"]["persona_version_id"],
            expected_latest_version=status["head"]["publication_version"], runtime_policy_sha256=status["runtime_policy_sha256"],
            profile="focus70-radar30-v1", visit_before_sequence=boundary))
        assert response.status_code == 202, response.text
        result = wait_run(client, response.json()["resource_id"], timeout=60)
        assert result["status"] == "completed", result
        new = client.get("/api/intelligence/briefings/" + result["snapshot_id"]).json()
        assert new["visit_window"]["basis"] == "last_confirmed_home_visit"
        assert new["visit_window"]["last_confirmed_visit_at"] == first["available_at"]
        assert new["visit_window"]["through_sequence"] == boundary
        assert client.get("/api/intelligence/interactions").json() == []
        assert not runtime(app, new["id"])["context"]["journal"]["entries"]


@pytest.mark.parametrize("damage", ["missing_persona", "row", "entry", "window", "future_sequence"])
def test_native_rejects_tampered_history_prefix_and_visit_boundary(tmp_path, damage):
    app, clock, _, _ = setup_app(tmp_path / damage, mode="real", timeout=60)
    with LocalClient(app, base_url="http://127.0.0.1:8000", headers={"Origin": "http://127.0.0.1:8000"}) as client:
        save(client, clock, 420, 1)
        capture(app, clock)
        old = generate(client, "old")
        value = deepcopy(runtime(app, old["id"])["input"])
        if damage == "missing_persona":
            value["persona_history"] = []
        elif damage == "row":
            value["history_prefix"]["records"][0]["row"]["id"] = "invented"
        elif damage == "entry":
            value["history_prefix"]["entries"][0]["id"] = "0" * 64
        elif damage == "future_sequence":
            value["visit_window"]["through_sequence"] = value["history_prefix"]["sequence"] + 1
        else:
            value["visit_window"]["start_at"] = value["as_of"]
        with pytest.raises(ValueError):
            model = RuntimeEnvelope.model_validate_json(json_bytes(value))
            raw = json_bytes(model)
            run(raw, expected_sha256=sha256_bytes(raw))


def test_correction_after_persona_update_is_not_suppressed_by_old_ack(tmp_path):
    app, clock, _, _ = setup_app(tmp_path / "correction", mode="synthetic_development", timeout=60)
    with LocalClient(app, base_url="http://127.0.0.1:8000", headers={"Origin": "http://127.0.0.1:8000"}) as client:
        save(client, clock, 420, 1)
        capture(app, clock, origin="synthetic", body="Atlas Tool releases local agent tooling with latency <= 10 ms.")
        old = generate(client, "old")
        birth = old["archive"][0]["event_key"]
        clock.advance()
        interact(client, old, old["deliveries"][0]["id"], "ack", "old-ack")
        save(client, clock, 180, 2)
        capture(app, clock, origin="synthetic", body="Atlas Tool releases local agent tooling with latency > 10 ms.")
        new = generate(client, "corrected")
        event = runtime(app, new["id"])["ranking"]["events"][0]
        assert event["event_key"] == birth
        assert event["history"]["promotion"] in {"material_change", "correction"}
        assert not event["history"]["declared_known"]
        assert event["features"]["duplicate"]["value"] == 0
        assert event["protected"]


def test_v1_delivered_snapshot_imports_without_rewriting_its_runtime(tmp_path, monkeypatch):
    from cfaw_news.intelligence import service as service_module
    actual = service_module.from_ledger

    def legacy_input(session, **kwargs):
        for name in ("persona_history", "history_prefix", "visit_window"):
            kwargs.pop(name, None)
        kwargs["config"] = RuntimeConfig(budget={"profile": "focus70-radar30-v1"})
        return actual(session, **kwargs)

    app, clock, _, _ = setup_app(tmp_path / "v1-history", mode="synthetic_development", timeout=60)
    with LocalClient(app, base_url="http://127.0.0.1:8000", headers={"Origin": "http://127.0.0.1:8000"}) as client:
        save(client, clock, 420, 1)
        capture(app, clock, origin="synthetic")
        with monkeypatch.context() as patch:
            patch.setattr(service_module, "from_ledger", legacy_input)
            old = generate(client, "legacy-generation")
        original = runtime(app, old["id"])
        assert original["schema_revision"] == "g4-pr3-result-v1"
        assert old["history_scoring"] == "not_applied_pr3_v2" and old["deliveries"]
        clock.advance()
        interact(client, old, old["deliveries"][0]["id"], "ack", "legacy-ack")
        save(client, clock, 180, 2)
        new = generate(client, "v2-generation")
        body = runtime(app, new["id"])
        assert body["ranking"]["events"][0]["history"]["declared_known"]
        assert body["ranking"]["events"][0]["event_key"] == old["archive"][0]["event_key"]
        assert runtime(app, old["id"]) == original


def test_directory_cursor_validation_and_stream_isolation(tmp_path):
    from cfaw_news.main import create_app
    app, clock, _, _ = setup_app(tmp_path / "scope", mode="real", timeout=60)
    with LocalClient(app, base_url="http://127.0.0.1:8000", headers={"Origin": "http://127.0.0.1:8000"}) as client:
        save(client, clock, 420, 1)
        capture(app, clock)
        old = generate(client, "old")
        for query in ("limit=0", "limit=201", "before_version=0", "through_version=-1", "limit=1&limit=2", "stream_id=synthetic:local"):
            assert client.get("/api/intelligence/briefings?" + query).status_code == 422
        assert client.get("/api/intelligence/briefings?through_version=99").status_code == 409
        settings = app.state.intelligence.settings.model_copy(update={"intelligence_mode": "synthetic_development",
            "intelligence_synthetic_provenance": "evals/intelligence_g4/tests/test_h09_continuity.py"})
        other = create_app(settings)
        with LocalClient(other, base_url="http://127.0.0.1:8000", headers={"Origin": "http://127.0.0.1:8000"}) as separate:
            page = separate.get("/api/intelligence/briefings").json()
            assert page["stream_id"] == "synthetic:local" and page["items"] == []
            assert separate.get("/api/intelligence/briefings/" + old["id"]).status_code == 404


@pytest.mark.parametrize("mutation", ["visit", "persona"])
def test_later_confirmation_keeps_asof_prefix_but_persona_change_is_stale(tmp_path, mutation):
    from cfaw_news.intelligence.runtime import run as calculate
    entered, release = threading.Event(), threading.Event()
    state = {"pause": False, "calls": 0}

    def native(*args, **kwargs):
        state["calls"] += 1
        if state["pause"]:
            entered.set()
            assert release.wait(15)
        return calculate(*args, **kwargs)

    app, clock, _, _ = setup_app(tmp_path / mutation, mode="real", timeout=60, runtime=native)
    with LocalClient(app, base_url="http://127.0.0.1:8000", headers={"Origin": "http://127.0.0.1:8000"}) as client:
        save(client, clock, 420, 1)
        capture(app, clock)
        old = generate(client, "old")
        state["pause"] = True
        response = start(client, key="concurrent")
        assert response.status_code == 202, response.text
        assert entered.wait(10)
        clock.advance()
        try:
            if mutation == "visit":
                reply = client.post("/api/intelligence/visits", json=dict(**preconditions(client),
                    idempotency_key="during-native", session_key="another-session", confirmation="home_visible", briefing_id=old["id"]))
                assert reply.status_code == 201, reply.text
            else:
                save(client, clock, 180, 2)
        finally:
            release.set()
        terminal = wait_run(client, response.json()["resource_id"], timeout=60)
        if mutation == "visit":
            assert terminal["status"] == "completed", terminal
            result = runtime(app, terminal["snapshot_id"])
            assert result["input"]["visit_window"]["last_confirmed_visit_at"] is None
        else:
            assert terminal["status"] == "stale", terminal
            assert client.get("/api/intelligence/briefings/latest").json()["id"] == old["id"]
        assert state["calls"] == 2
