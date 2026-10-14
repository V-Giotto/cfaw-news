import asyncio
import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest
from cfaw_news.config import Settings
from cfaw_news.database import Article, Run
from cfaw_news.ingestion import parse_source, validate_feed_url
from cfaw_news.main import create_app
from cfaw_news.providers import BaselineProvider, CompatibleProvider, validate_judgment
from cfaw_news.retrieval import search, tokenize
from cfaw_news.schemas import Citation, Judgment
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def settings(tmp_path):
    return Settings(
        _env_file=None,
        database_url=f"sqlite:///{(tmp_path / 'test.db').as_posix()}",
        root=ROOT,
        demo_seed=True,
        llm_mode="baseline",
    )


@pytest.fixture
def client(settings):
    with TestClient(create_app(settings)) as value:
        yield value


def check(client, goal=None):
    goal = goal or client.get("/api/goals").json()[0]
    response = client.post(
        f"/api/goals/{goal['id']}/checks", json={"expected_version": goal["version"]}
    )
    assert response.status_code == 202
    run_id = response.json()["id"]
    for _ in range(100):
        result = client.get(f"/api/runs/{run_id}").json()
        if result["status"] not in {"queued", "running"}:
            assert result["status"] == "completed", result
            return result
        time.sleep(0.01)
    pytest.fail("run did not finish")


def interval(run):
    start = (datetime.now(timezone.utc) + timedelta(days=2)).replace(second=0, microsecond=0)
    return {
        "start": start.isoformat(),
        "end": (
            start + timedelta(minutes=run["result"]["proposal"]["duration_minutes"])
        ).isoformat(),
    }


def test_baseline_end_to_end_and_snapshot_citations(client):
    assert client.get("/api/health").json()["status"] == "ok"
    assert client.get("/api/config").json()["counts"]["articles"] == 26
    run = check(client)
    assert run["result"]["outcome"] == "needs_review"
    assert run["metrics"]["token_usage"] is None
    assert len(run["snapshot"]["evidence"]) <= 8
    validate_judgment(Judgment.model_validate(run["result"]), run["snapshot"])
    assert "未调用大模型" in "".join(run["result"]["uncertainties"])


def test_approval_is_explicit_and_idempotent(client):
    run = check(client)
    assert client.get("/api/schedules").json() == []
    body = interval(run)
    first = client.post(f"/api/runs/{run['id']}/approve", json=body)
    second = client.post(f"/api/runs/{run['id']}/approve", json=body)
    assert first.status_code == second.status_code == 200
    assert first.json()["created"] is True
    assert second.json()["created"] is False
    assert first.json()["schedule"]["id"] == second.json()["schedule"]["id"]
    assert len(client.get("/api/schedules").json()) == 1


def test_approval_rejects_conflicts(client):
    run = check(client)
    body = interval(run)
    assert client.post(f"/api/runs/{run['id']}/approve", json=body).status_code == 200
    goals = client.get("/api/goals").json()
    goal = goals[1]
    patch = {key: goal[key] for key in ("name", "purpose", "scope", "constraints", "keywords")}
    patch.update(expected_version=goal["version"], trial_requested=True)
    goal = client.patch(f"/api/goals/{goal['id']}", json=patch).json()
    other = check(client, goal)
    assert client.post(f"/api/runs/{other['id']}/approve", json=body).status_code == 409


def test_goal_version_invalidates_old_approval_and_optimistic_update(client):
    run = check(client)
    goal = client.get("/api/goals").json()[0]
    patch = {
        key: goal[key]
        for key in ("name", "purpose", "scope", "constraints", "keywords", "trial_requested")
    }
    patch.update(expected_version=goal["version"], purpose="修改后的目标，只核实当前设备可用性")
    assert client.patch(f"/api/goals/{goal['id']}", json=patch).status_code == 200
    assert client.patch(f"/api/goals/{goal['id']}", json=patch).status_code == 409
    assert client.post(f"/api/runs/{run['id']}/approve", json=interval(run)).status_code == 409


def test_changed_article_invalidates_approval_but_keeps_snapshot(client):
    run = check(client)
    before = run["snapshot"]["evidence"][0]
    with client.app.state.database.session.begin() as session:
        article = session.get(Article, before["id"])
        article.content_hash = "new-version"
        article.data = {**article.data, "summary": "已更新的正文", "content_hash": "new-version"}
    assert client.post(f"/api/runs/{run['id']}/approve", json=interval(run)).status_code == 409
    stored = client.get(f"/api/runs/{run['id']}").json()["snapshot"]["evidence"][0]
    assert stored == before


def test_user_decision_suppresses_same_evidence_proposal(client):
    run = check(client)
    assert (
        client.post(f"/api/runs/{run['id']}/decisions", json={"choice": "dismissed"}).status_code
        == 200
    )
    assert client.post(f"/api/runs/{run['id']}/approve", json=interval(run)).status_code == 409
    second = check(client)
    assert second["result"]["proposal"] is None
    assert second["result"]["change_kind"] == "unchanged"


def test_unknown_citation_and_fabricated_paragraph_are_rejected(client):
    run = check(client)
    result = Judgment.model_validate(run["result"])
    result.citations = [Citation(article_id="made-up", paragraph_id="p1")]
    with pytest.raises(ValueError, match="报道"):
        validate_judgment(result, run["snapshot"])
    result.citations = [
        Citation(article_id=run["snapshot"]["evidence"][0]["id"], paragraph_id="p999")
    ]
    with pytest.raises(ValueError, match="段落"):
        validate_judgment(result, run["snapshot"])


def test_no_candidate_does_not_call_model(settings):
    class MustNotCall:
        async def judge(self, snapshot):
            raise AssertionError("empty evidence must skip inference")

    with TestClient(create_app(settings, MustNotCall())) as client:
        goal = client.post(
            "/api/goals", json={"name": "zzquux123", "purpose": "zzquux123 xyzzy987"}
        ).json()
        run = check(client, goal)
        assert run["result"]["outcome"] == "insufficient_evidence"
        assert run["metrics"]["model_called"] is False
        assert run["result"]["proposal"] is None


class SlowProvider(BaselineProvider):
    async def judge(self, snapshot):
        await asyncio.sleep(0.2)
        return await super().judge(snapshot)


def test_cancel_cannot_publish_a_late_result(settings):
    with TestClient(create_app(settings, SlowProvider())) as client:
        goal = client.get("/api/goals").json()[0]
        run = client.post(f"/api/goals/{goal['id']}/checks", json={"expected_version": 1}).json()
        assert client.post(f"/api/runs/{run['id']}/cancel").status_code == 200
        time.sleep(0.25)
        stored = client.get(f"/api/runs/{run['id']}").json()
        assert stored["status"] == "cancelled" and stored["result"] is None


def test_edit_during_inference_cannot_publish(settings):
    with TestClient(create_app(settings, SlowProvider())) as client:
        goal = client.get("/api/goals").json()[0]
        run = client.post(f"/api/goals/{goal['id']}/checks", json={"expected_version": 1}).json()
        patch = {
            key: goal[key]
            for key in ("name", "purpose", "scope", "constraints", "keywords", "trial_requested")
        }
        patch.update(expected_version=1, purpose="现在只关注另一类使用场景")
        assert client.patch(f"/api/goals/{goal['id']}", json=patch).status_code == 200
        time.sleep(0.3)
        stored = client.get(f"/api/runs/{run['id']}").json()
        assert stored["status"] == "stale" and stored["result"] is None


def test_events_are_persisted_and_support_reconnection(client):
    run = check(client)
    response = client.get(f"/api/runs/{run['id']}/events")
    assert "text/event-stream" in response.headers["content-type"]
    assert '"kind": "completed"' in response.text
    last = max(
        int(line.removeprefix("id: "))
        for line in response.text.splitlines()
        if line.startswith("id: ")
    )
    assert (
        client.get(f"/api/runs/{run['id']}/events", headers={"Last-Event-ID": str(last)}).text == ""
    )


def test_results_survive_restart_and_incomplete_runs_are_reported(settings):
    with TestClient(create_app(settings)) as client:
        run = check(client)
        database = client.app.state.database
        with database.session.begin() as session:
            session.add(
                Run(
                    id="interrupted",
                    goal_id=run["goal_id"],
                    goal_version=1,
                    mode="baseline",
                    snapshot={},
                    basis_hash="old",
                    status="running",
                )
            )
    with TestClient(create_app(settings)) as restarted:
        assert restarted.get(f"/api/runs/{run['id']}").json()["status"] == "completed"
        assert restarted.get("/api/runs/interrupted").json()["status"] == "failed"
        assert len(restarted.get("/api/goals").json()) == 3


def test_bm25_has_stable_topk_and_han_bigrams(client):
    assert tokenize("中文会议 Mac") == ["中文", "文会", "会议", "mac"]
    goal = client.get("/api/goals").json()[0]
    articles = client.get("/api/articles").json()
    result = search(goal, articles, 3)
    assert len(result) == 3
    assert [row["id"] for row in result] == [row["id"] for row in search(goal, articles, 3)]
    assert search({"name": "nonsensezz", "purpose": "xyzquux"}, articles) == []


def test_feed_parser_preserves_source_and_strips_active_markup():
    body = b'<rss version="2.0"><channel><title>Example</title><item><title>New</title><link>https://example.com/post</link><description><![CDATA[<b>Fact</b><script>bad()</script>]]></description></item></channel></rss>'
    row = parse_source({"id": "test", "kind": "rss", "label": "Example"}, body)[0]
    assert row["summary"] == "Fact"
    assert row["published_at"] is None
    assert row["paragraphs"] == []


def test_feed_url_rejects_nonpublic_dns(monkeypatch):
    monkeypatch.setattr("socket.getaddrinfo", lambda *a, **kw: [(2, 1, 6, "", ("127.0.0.1", 443))])
    with pytest.raises(ValueError, match="非公网"):
        asyncio.run(validate_feed_url("https://example.com/feed", {"example.com"}))


def test_compatible_adapter_repairs_invalid_references_once(client, settings, monkeypatch):
    snapshot = check(client)["snapshot"]
    good = asyncio.run(BaselineProvider().judge(snapshot))[0].model_dump()
    bad = {**good, "citations": [{"article_id": "unknown", "paragraph_id": "p1"}]}
    calls = []

    def handler(request):
        calls.append(request)
        value = bad if len(calls) == 1 else good
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": json.dumps(value)}}],
                "usage": {"prompt_tokens": 20, "completion_tokens": 30},
            },
        )

    original_client = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kw: original_client(**kw, transport=httpx.MockTransport(handler)),
    )
    configured = settings.model_copy(
        update={
            "llm_mode": "compatible",
            "llm_base_url": "https://model.example/v1",
            "llm_model": "test-model",
        }
    )
    result, metrics = asyncio.run(CompatibleProvider(configured).judge(snapshot))
    assert result.citations
    assert metrics["repair_count"] == 1 and len(calls) == 2
    assert len(metrics["token_usage"]) == 2


def test_invalid_and_unknown_resource_requests_are_explicit(client):
    assert client.get("/api/runs/absent").status_code == 404
    assert client.post("/api/goals", json={"name": "", "purpose": ""}).status_code == 422
    assert (
        client.post("/api/sources/refresh", json={"source_ids": ["private-url"]}).status_code == 422
    )
