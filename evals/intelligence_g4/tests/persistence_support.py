"""Only authored/mock data and isolated SQLite; no settings/env/user DB loading."""

import json
import time
from datetime import datetime, timedelta, timezone

from cfaw_news.database import Database
from cfaw_news.intelligence.history_store import HistoryStore
from cfaw_news.intelligence.persistence_migrate import maintain


def LocalClient(app, **kwargs):
    from fastapi.testclient import TestClient
    return TestClient(app, client=("127.0.0.1", 50000), **kwargs)


class Clock:
    def __init__(self):
        self.value = datetime(2026, 1, 1, tzinfo=timezone.utc)

    def __call__(self):
        return self.value.isoformat(timespec="microseconds")

    def advance(self, seconds=1):
        self.value += timedelta(seconds=seconds)
        return self()


def setup_store(folder, **kwargs):
    folder.mkdir(parents=True, exist_ok=True)
    path, anchor = folder / "local.db", folder / "trusted-head.json"
    maintain(path, anchor, "upgrade")
    database = Database("sqlite:///" + path.resolve().as_posix())
    return database, HistoryStore(database, anchor, **kwargs), path, anchor


def setup_app(folder, *, mode="real", runtime=None, timeout=30, migrated=True):
    from cfaw_news.config import Settings
    from cfaw_news.main import create_app
    root = folder / "project"
    (root / "data").mkdir(parents=True)
    (root / "data/sources.json").write_text(json.dumps(dict(sources=[])), encoding="utf-8")
    path, anchor = folder / "app.db", folder / "app-anchor.json"
    if migrated:
        maintain(path, anchor, "upgrade")
    settings = Settings(_env_file=None, root=root, database_url="sqlite:///" + path.resolve().as_posix(),
        llm_mode="baseline", news_auto_refresh=False, news_media_fetch=False, news_reading_fetch=False,
        intelligence_enabled=True, intelligence_mode=mode, intelligence_anchor=anchor,
        intelligence_synthetic_provenance="evals/intelligence_g4/tests/persistence_support.py" if mode != "real" else None,
        intelligence_timeout_seconds=timeout)
    app = create_app(settings)
    clock = Clock()
    app.state.intelligence.clock = clock
    app.state.intelligence.store.clock = clock
    if runtime:
        app.state.intelligence.runtime = runtime
    return app, clock, path, anchor


def current_status(client):
    for _ in range(100):
        response = client.get("/api/intelligence/status")
        data = response.json()
        if data.get("state") == "ready" and data.get("head"):
            return data
        time.sleep(0.01)
    raise AssertionError(data)


def preconditions(client):
    head = current_status(client)["head"]
    return dict(expected_head=head["sha256"], expected_epoch=head["epoch"])


def save_persona(client, *, key="persona-1", expected=0):
    return client.post("/api/intelligence/persona", json=dict(**preconditions(client),
        idempotency_key=key, expected_persona_version=expected, domain_interests=["agent tooling"]))


def capture(app, clock, *, origin="real", body="Atlas Tool releases local agent tooling.", status="covered"):
    from cfaw_news.intelligence.contracts import SourcePolicy
    from cfaw_news.intelligence.document_store import add_coverage, capture_version
    clock.advance()
    policy = SourcePolicy(source_id="official", source_url="https://example.com/feed",
        source_label="Authored engineering mock", source_role="official", record_origin=origin,
        rights="permitted" if origin == "real" else "synthetic",
        allowed_use=("metadata", "excerpt", "fulltext"), max_excerpt_chars=16000,
        rights_evidence_uri="https://example.test/AI-authored-policy-not-a-real-license")
    with app.state.database.session.begin() as session:
        version = capture_version(session, dict(id="authored-rss", source_id="official",
            source_url="https://example.com/article", title="Atlas Tool release", summary="",
            paragraphs=[dict(text=body)] if body else [], published_at="2025-12-31T00:00:00Z"),
            policy, observed_at=clock(), available_at=clock())
        add_coverage(session, "official", clock(), clock(), clock(), status,
                     "bounded_parse" if status == "covered" else "source_failed")
    return version


def start(client, *, key="run-1", persona_id=None):
    status = current_status(client)
    return client.post("/api/intelligence/briefings", json=dict(**preconditions(client), idempotency_key=key,
        persona_version_id=persona_id or status["head"]["persona_version_id"],
        expected_latest_version=status["head"]["publication_version"], runtime_policy_sha256=status["runtime_policy_sha256"],
        profile="focus70-radar30-v1"))


def wait_run(client, identifier, *, timeout=30):
    until = time.monotonic() + timeout
    while time.monotonic() < until:
        response = client.get("/api/intelligence/runs/" + identifier)
        if response.status_code == 200:
            value = response.json()
            if value["status"] not in {"queued", "running"}:
                return value
        time.sleep(0.02)
    raise AssertionError("run did not finish")
