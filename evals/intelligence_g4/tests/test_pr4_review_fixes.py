"""Independent fault shapes from PR4 review; isolated SQLite and authored mocks only."""

import json
import sqlite3
import threading
import time

import pytest
from cfaw_news.intelligence.checkpoint import Checkpoint, PersistenceError
from cfaw_news.intelligence.contracts import canonical, digest
from cfaw_news.intelligence.corpus_trust import capture as corpus
from cfaw_news.intelligence.corpus_trust import packed
from cfaw_news.intelligence.history_store import HistoryStore, entry_pin, genesis
from cfaw_news.intelligence.models import G4Base, G4Capture, G4ServiceEvent, G4SourcePolicy
from cfaw_news.intelligence.persistence_migrate import maintain, restore_with_epoch
from cfaw_news.intelligence.persistence_models import BriefingRun, IdempotentRequest, TrustedHead
from cfaw_news.main import create_app
from sqlalchemy import select

from .persistence_support import (
    LocalClient,
    capture,
    current_status,
    preconditions,
    save_persona,
    setup_app,
    start,
    wait_run,
)
from .test_history_db import append, head
from .test_publication_races import Paused, published

HEADERS = {"Origin": "http://127.0.0.1:8000"}


def source_rows(path):
    with sqlite3.connect(path) as connection:
        return {t.name: connection.execute(f'SELECT * FROM "{t.name}"').fetchall()
                for t in G4Base.metadata.sorted_tables}


def replace_sources(path, values):
    """Simulate partial file restore with the exact original Schema, not an HTTP delete."""
    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA foreign_keys=OFF")
        triggers = connection.execute("SELECT name,sql FROM sqlite_master WHERE type='trigger' AND tbl_name LIKE 'g4_%'").fetchall()
        for name, _ in triggers:
            connection.execute(f'DROP TRIGGER "{name}"')
        for table in reversed(G4Base.metadata.sorted_tables):
            connection.execute(f'DELETE FROM "{table.name}"')
        for table in G4Base.metadata.sorted_tables:
            for row in values[table.name]:
                connection.execute(f'INSERT INTO "{table.name}" VALUES ({",".join("?" for _ in row)})', row)
        for _, sql in triggers:
            connection.execute(sql)


def write_proof(folder, name, **value):
    (folder / (name + ".json")).write_bytes(canonical(value))


def test_source_only_rollback_cannot_publish_or_be_blessed_by_epoch(tmp_path):
    app, clock, path, anchor = setup_app(tmp_path)
    with LocalClient(app, base_url="http://127.0.0.1:8000", headers=HEADERS) as client:
        first = published(client, app, clock)
        before = source_rows(path)
    maintain(path, anchor, "backup", backup=tmp_path / "consistent-v1.db")
    app = create_app(app.state.intelligence.settings)
    app.state.intelligence.clock = app.state.intelligence.store.clock = clock
    with LocalClient(app, base_url="http://127.0.0.1:8000", headers=HEADERS) as client:
        second_version = capture(app, clock, body="Atlas Tool corrects local agent latency to >= 25 ms.")
        response = start(client, key="second")
        assert wait_run(client, response.json()["resource_id"])["status"] == "completed"
        second = client.get("/api/intelligence/briefings/latest").json()
        assert second["version"] == first["version"] + 1
        status = current_status(client)
        checkpoint = anchor.read_bytes()
        request = dict(json.loads(response.request.content), idempotency_key="after-rollback",
            expected_head=status["head"]["sha256"], expected_latest_version=second["version"])
        replace_sources(path, before)
        after = client.get("/api/intelligence/status").json()
        assert after["state"] == "unavailable" and after["code"] == "G4_CORPUS_PREFIX_LOST"
        rejected = client.post("/api/intelligence/briefings", json=request)
        assert rejected.status_code == 503 and rejected.json()["code"] == "G4_CORPUS_EPOCH_ADOPTION_REQUIRED"
        current = json.loads(anchor.read_bytes())
        assert current["heads"] == json.loads(checkpoint)["heads"]
        assert current["recovery_required"] == "G4_CORPUS_PREFIX_LOST"
        with app.state.database.session() as session:
            trusted = session.get(TrustedHead, "real:local")
            assert trusted.latest_snapshot_id == second["id"] and trusted.publication_version == 2
        write_proof(tmp_path, "corpus-rollback-proof", status=after, post_status=rejected.status_code,
            missing_version=second_version.doc_version_id, latest_retained=second["id"], checkpoint_heads_unchanged=True,
            recovery_required=current["recovery_required"])
    # New anchor acknowledgement cannot conceal an internally inconsistent history.
    with pytest.raises(PersistenceError, match="CORPUS_PREFIX_LOST"):
        maintain(path, tmp_path / "rejected-adoption.json", "adopt-restore", backup=tmp_path / "bad-copy.db", acknowledge_restore=True)
    # A consistent complete older backup may be restored only to fresh paths/epoch.
    from cfaw_news.intelligence.migrate import sha
    restored, renewed = tmp_path / "restored.db", tmp_path / "restored-head.json"
    restore_with_epoch(tmp_path / "consistent-v1.db", restored, renewed,
        expected_sha256=sha(tmp_path / "consistent-v1.db"), acknowledge_restore=True)
    assert json.loads(renewed.read_bytes())["epoch"] != json.loads(checkpoint)["epoch"]


@pytest.mark.parametrize("damage", ["document", "version", "coverage", "policy", "capture", "service_event", "watermark", "rewrite"])
def test_accepted_source_records_and_watermarks_cannot_disappear_or_change(tmp_path, damage):
    app, clock, path, anchor = setup_app(tmp_path)
    version = capture(app, clock)
    db = app.state.database
    with db.session.begin() as session:
        policy = session.scalar(select(G4SourcePolicy))
        session.add(G4Capture(capture_id="controlled-poll", source_id=policy.source_id,
            observed_at=clock(), source_policy_sha256=policy.policy_sha256,
            data=dict(observed_at=clock(), version_ids=[version.doc_version_id])))
        session.add(G4ServiceEvent(event_id="controlled-service-event", occurred_at=clock(), kind="started"))
    store = HistoryStore(db, anchor, clock=clock)
    append(store, head(store))  # Accept all source rows, even before a briefing is published.
    rows = source_rows(path)
    if damage in {"document", "version", "coverage", "policy", "capture", "service_event"}:
        table = dict(document="g4_documents", version="g4_document_versions", coverage="g4_coverage_windows",
                     policy="g4_source_policies", capture="g4_captures", service_event="g4_service_events")[damage]
        rows[table] = []
    elif damage == "watermark":
        row = list(rows["g4_documents"][0])
        row[-1] = "2026-01-01T00:00:00.000000+00:00"
        rows["g4_documents"] = [row]
    else:
        row = list(rows["g4_captures"][0])
        row[-1] = row[-1].replace("controlled", "modified") if "controlled" in row[-1] else row[-1] + " "
        # Canonical-equivalent whitespace is not a semantic change; alter an actual field.
        data = json.loads(row[-1])
        data["extra"] = "modified-receipt"
        row[-1] = json.dumps(data)
        rows["g4_captures"] = [row]
    replace_sources(path, rows)
    with pytest.raises(PersistenceError, match="CORPUS_(PREFIX_LOST|CHAIN_INVALID)"):
        with store.read():
            pass
    db.engine.dispose()


def test_source_append_duplicate_observation_and_restart_keep_exact_prefix(tmp_path):
    app, clock, _, anchor = setup_app(tmp_path)
    db, store = app.state.database, app.state.intelligence.store
    one = capture(app, clock)
    append(store, head(store))
    repeated = capture(app, clock)
    assert repeated.doc_version_id == one.doc_version_id
    append(store, head(store), key="reobserve")
    two = capture(app, clock, body="Atlas Tool corrects local agent latency to <= 10 ms.")
    append(store, head(store), key="new-version")
    with HistoryStore(db, anchor).read() as (session, _):
        prefix = packed(corpus(session))
        assert prefix["value"]["documents"][one.document_id]["version_ids"] == [one.doc_version_id, two.doc_version_id]
    db.engine.dispose()


def test_detected_source_loss_requires_explicit_new_epoch_even_after_exact_repair(tmp_path):
    app, clock, path, anchor = setup_app(tmp_path)
    capture(app, clock)
    store = app.state.intelligence.store
    append(store, head(store))
    good = source_rows(path)
    damaged = {**good, "g4_coverage_windows": []}
    replace_sources(path, damaged)
    with pytest.raises(PersistenceError, match="CORPUS_PREFIX_LOST"):
        with store.read():
            pass
    replace_sources(path, good)
    with pytest.raises(PersistenceError, match="CORPUS_EPOCH_ADOPTION_REQUIRED"):
        with HistoryStore(app.state.database, anchor).read():
            pass
    renewed = tmp_path / "repaired-new-epoch.json"
    maintain(path, renewed, "adopt-restore", backup=tmp_path / "before-adoption.db", acknowledge_restore=True)
    assert json.loads(renewed.read_bytes())["epoch"] != json.loads(anchor.read_bytes())["epoch"]
    with HistoryStore(app.state.database, renewed).read():
        pass


def test_old_checkpoint_requires_explicit_adoption_and_new_epoch(tmp_path):
    malformed = tmp_path / "nonobject-checkpoint.json"
    for raw in (b"[]", b"null"):
        malformed.write_bytes(raw)
        with pytest.raises(PersistenceError, match="G4_CHECKPOINT_INVALID"):
            Checkpoint(malformed).read()
    app, clock, path, anchor = setup_app(tmp_path)
    with LocalClient(app, base_url="http://127.0.0.1:8000", headers=HEADERS) as client:
        published(client, app, clock)
    original = json.loads(anchor.read_bytes())
    legacy = {k: v for k, v in original.items() if k != "corpus"}
    legacy["revision"] = "g4-checkpoint-v1"
    anchor.write_bytes(canonical(legacy))
    with pytest.raises(PersistenceError, match="CORPUS_EPOCH_ADOPTION_REQUIRED"):
        with HistoryStore(app.state.database, anchor).read():
            pass
    renewed = tmp_path / "adopted.json"
    maintain(path, renewed, "adopt-restore", backup=tmp_path / "upgrade-copy.db", acknowledge_restore=True)
    assert json.loads(renewed.read_bytes())["epoch"] != original["epoch"]
    with HistoryStore(app.state.database, renewed).read():
        pass


def legacy_journal(path, anchor):
    """Old body grammar and checkpoint, retaining all hash-bound historical inputs."""
    checkpoint = json.loads(anchor.read_bytes())
    with sqlite3.connect(path) as connection:
        triggers = connection.execute("SELECT name,sql FROM sqlite_master WHERE type='trigger' AND tbl_name LIKE 'intelligence_%'").fetchall()
        for name, _ in triggers:
            connection.execute(f'DROP TRIGGER "{name}"')
        for stream in checkpoint["heads"]:
            previous = genesis(checkpoint["database_id"], stream)
            rows = connection.execute("SELECT id,sequence,kind,created_at,data FROM intelligence_entries WHERE stream_id=? ORDER BY sequence", (stream,)).fetchall()
            for old_id, sequence, kind, timestamp, body in rows:
                body = json.loads(body)
                body.pop("corpus", None)
                pin = entry_pin(stream, sequence, previous, kind, timestamp, body)
                connection.execute("UPDATE intelligence_entries SET id=?,previous_sha256=?,data=? WHERE id=?",
                                   (pin, previous, json.dumps(body), old_id))
                previous = pin
            connection.execute("UPDATE intelligence_heads SET sha256=? WHERE id=?", (previous, stream))
            checkpoint["heads"][stream]["sha256"] = previous
        for _, sql in triggers:
            connection.execute(sql)
    checkpoint.pop("corpus")
    checkpoint.pop("recovery_required")
    checkpoint["revision"] = "g4-checkpoint-v1"
    anchor.write_bytes(canonical(checkpoint))


@pytest.mark.parametrize("lose_v2", [False, True])
def test_legacy_body_adoption_checks_previously_bound_runtime_evidence(tmp_path, lose_v2):
    app, clock, path, anchor = setup_app(tmp_path)
    with LocalClient(app, base_url="http://127.0.0.1:8000", headers=HEADERS) as client:
        published(client, app, clock)
        v1 = source_rows(path)
        capture(app, clock, body="Atlas Tool corrects latency to >= 25 ms.")
        response = start(client, key="second")
        assert wait_run(client, response.json()["resource_id"])["status"] == "completed"
    legacy_journal(path, anchor)
    if lose_v2:
        replace_sources(path, v1)
    renewed = tmp_path / "new-epoch.json"
    if lose_v2:
        with pytest.raises(PersistenceError, match="CORPUS_PREFIX_LOST"):
            maintain(path, renewed, "adopt-restore", backup=tmp_path / "copy.db", acknowledge_restore=True)
        assert not renewed.exists()
    else:
        maintain(path, renewed, "adopt-restore", backup=tmp_path / "copy.db", acknowledge_restore=True)
        with HistoryStore(app.state.database, renewed).read():
            pass


def test_source_loss_while_computing_cannot_commit_new_snapshot(tmp_path):
    app, clock, path, _ = setup_app(tmp_path, mode="synthetic_development")
    with LocalClient(app, base_url="http://127.0.0.1:8000", headers=HEADERS) as client:
        previous = published(client, app, clock)
        rows = source_rows(path)
        capture(app, clock, origin="synthetic", body="Atlas Tool corrects latency to >= 25 ms.")
        paused = Paused()
        app.state.intelligence.runtime = paused
        response = start(client, key="changed-input")
        try:
            assert paused.started.wait(5)
            replace_sources(path, rows)
        finally:
            paused.release.set()
        assert paused.finished.wait(5)
        until = time.monotonic() + 5
        while app.state.intelligence.computations and time.monotonic() < until:
            time.sleep(0.01)
        with app.state.database.session() as session:
            assert session.get(TrustedHead, "synthetic:local").latest_snapshot_id == previous["id"]
            assert session.get(BriefingRun, response.json()["resource_id"]).status != "completed"
        assert client.get("/api/intelligence/status").json()["state"] == "unavailable"


@pytest.mark.parametrize("suffix", ["start", "terminal", "publish"])
def test_client_internal_lookalike_key_cancel_does_not_poison_service(tmp_path, suffix):
    paused = Paused()
    app, clock, _, _ = setup_app(tmp_path, mode="synthetic_development", runtime=paused)
    with LocalClient(app, base_url="http://127.0.0.1:8000", headers=HEADERS) as client:
        save_persona(client)
        capture(app, clock, origin="synthetic")
        identifier = start(client).json()["resource_id"]
        try:
            assert paused.started.wait(5)
            state = client.get("/api/intelligence/runs/" + identifier).json()
            key = "run:" + identifier + ":" + suffix
            body = dict(**preconditions(client), idempotency_key=key, expected_run_version=state["version"])
            response = client.post("/api/intelligence/runs/" + identifier + "/cancel", json=body)
            assert response.status_code == 200, response.text
            assert client.post("/api/intelligence/runs/" + identifier + "/cancel", json=body).json()["deduplicated"]
        finally:
            paused.release.set()
        assert paused.finished.wait(5)
        assert wait_run(client, identifier)["status"] == "cancelled"
        assert current_status(client)["state"] == "ready"
        write_proof(tmp_path, "request-namespace-proof", key=key, cancel_status=response.status_code,
            service_state=client.get("/api/intelligence/status").json()["state"])


def test_legacy_client_terminal_key_conflict_does_not_block_internal_recovery(tmp_path):
    app, clock, _, _ = setup_app(tmp_path)
    with LocalClient(app, base_url="http://127.0.0.1:8000", headers=HEADERS) as client:
        save_persona(client)
        capture(app, clock)
        app.state.intelligence.launch = lambda _: None
        identifier = start(client).json()["resource_id"]
        service = app.state.intelligence
        key = "run:" + identifier + ":terminal"
        def apply(session, _):
            # Valid journal materialization of the old raw-key client cancellation receipt.
            row = IdempotentRequest(id=digest([service.stream, key]), stream_id=service.stream, key=key,
                operation="cancel:" + identifier, request_sha256=digest({}), data=dict(resource_id=identifier))
            session.add(row)
            return dict(resource_id=identifier), [row], {}
        service.store.mutate(service.stream, key="seed-old-receipt", operation="mock-old-client", payload={},
            expected_head=None, apply=apply)
    renewed = create_app(service.settings)
    renewed.state.intelligence.clock = renewed.state.intelligence.store.clock = clock
    with LocalClient(renewed, base_url="http://127.0.0.1:8000", headers=HEADERS) as client:
        assert current_status(client)["state"] == "ready"
        assert wait_run(client, identifier)["status"] == "interrupted"
        with renewed.state.database.session() as session:
            assert session.get(IdempotentRequest, digest([service.stream, "system", key]))
            assert session.get(IdempotentRequest, digest([service.stream, key]))


def test_legacy_client_receipt_still_deduplicates_without_rewriting_history(tmp_path):
    app, clock, _, _ = setup_app(tmp_path)
    store = app.state.intelligence.store
    first = append(store, head(store), value="legacy-value")
    def apply(session, _):
        request = IdempotentRequest(id=digest(["real:local", "old-retry"]), stream_id="real:local", key="old-retry",
            operation="test-persona", request_sha256=digest(dict(operation="test-persona", payload=dict(value="legacy-value"))),
            data=dict(resource_id=first["resource_id"]))
        session.add(request)
        return dict(resource_id=first["resource_id"]), [request], {}
    seeded = store.mutate("real:local", key="seed-legacy-client", operation="controlled-legacy-receipt", payload={},
                         expected_head=None, apply=apply)
    again = append(store, "0" * 64, key="old-retry", value="legacy-value")
    assert again["deduplicated"] and again["resource_id"] == first["resource_id"]
    assert again["head"]["sequence"] == seeded["head"]["sequence"]
    app.state.database.engine.dispose()


class Blocking:
    def __init__(self):
        self.release, self.started, self.finished = threading.Event(), threading.Event(), threading.Event()
        self.lock = threading.Lock()
        self.active, self.peak, self.calls = 0, 0, 0

    def __call__(self, raw, **kwargs):
        with self.lock:
            self.active += 1
            self.calls += 1
            self.peak = max(self.peak, self.active)
        self.started.set()
        try:
            assert self.release.wait(10)
            return None  # Deliberately uncooperative/invalid result, never publishable.
        finally:
            with self.lock:
                self.active -= 1
            self.finished.set()


@pytest.mark.parametrize("workers", [1, 2])
def test_timeout_keeps_actual_worker_permit_and_bounds_queue(tmp_path, workers):
    blocked = Blocking()
    app, clock, _, _ = setup_app(tmp_path, runtime=blocked, timeout=0.08)
    if workers == 2:
        settings = app.state.intelligence.settings
        settings.intelligence_max_workers = 2
        app = create_app(settings)
        app.state.intelligence.clock = app.state.intelligence.store.clock = clock
        app.state.intelligence.runtime = blocked
    with LocalClient(app, base_url="http://127.0.0.1:8000", headers=HEADERS) as client:
        save_persona(client)
        capture(app, clock)
        try:
            for index in range(workers):
                first = start(client, key="timeout-" + str(index)).json()["resource_id"]
                assert blocked.started.wait(5)
                assert wait_run(client, first)["status"] == "timed_out"
            queued = [start(client, key="queued-" + str(i)) for i in range(2)]
            assert all(r.status_code == 202 for r in queued)
            overflow = start(client, key="queue-overflow")
            assert overflow.status_code == 429
            time.sleep(0.15)
            assert blocked.active == blocked.peak == blocked.calls == workers
            assert all(client.get("/api/intelligence/runs/" + r.json()["resource_id"]).json()["status"] == "queued" for r in queued)
            write_proof(tmp_path, "worker-capacity-proof", configured_workers=workers, actual_active=blocked.active,
                peak=blocked.peak, actual_started=blocked.calls, queued=2, overflow_status=overflow.status_code)
        finally:
            blocked.release.set()
        assert blocked.finished.wait(5)
        for response in queued:
            assert wait_run(client, response.json()["resource_id"])["status"] in {"failed", "timed_out"}
        assert blocked.peak == workers and client.get("/api/intelligence/briefings/latest").status_code == 404


def test_shutdown_retains_process_owner_until_timed_out_thread_really_exits(tmp_path):
    blocked = Blocking()
    app, clock, _, _ = setup_app(tmp_path, runtime=blocked, timeout=0.08)
    try:
        with LocalClient(app, base_url="http://127.0.0.1:8000", headers=HEADERS) as client:
            save_persona(client)
            capture(app, clock)
            identifier = start(client).json()["resource_id"]
            assert wait_run(client, identifier)["status"] == "timed_out"
        service = app.state.intelligence
        assert blocked.active == 1 and service.worker_lock is not None
        replacement = create_app(service.settings)
        replacement.state.intelligence.clock = replacement.state.intelligence.store.clock = clock
        with LocalClient(replacement, base_url="http://127.0.0.1:8000", headers=HEADERS) as client:
            assert not current_status(client)["worker_available"]
            assert start(client, key="no-owner").status_code == 503
    finally:
        blocked.release.set()
    assert blocked.finished.wait(5)
    until = time.monotonic() + 5
    while service.worker_lock is not None and time.monotonic() < until:
        time.sleep(0.01)
    assert service.worker_lock is None
