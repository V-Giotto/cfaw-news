"""Mock transport regressions. These tests do not validate a live model."""

import asyncio
import json
import time
from pathlib import Path

import httpx
import pytest
from cfaw_news.config import Settings
from cfaw_news.database import Database, Goal, Run
from cfaw_news.live_check import preview_check, run_check
from cfaw_news.main import create_app
from cfaw_news.providers import BaselineProvider, CompatibleProvider, ProviderError
from cfaw_news.seed import seed
from cfaw_news.service import build_run
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[1]
SECRET = "test-secret-never-persist"


@pytest.fixture
def configured(tmp_path):
    return Settings(
        _env_file=None, root=ROOT,
        database_url=f"sqlite:///{(tmp_path / 'provider.db').as_posix()}",
        llm_mode="compatible", llm_model="test-model", llm_base_url="https://model.example/v1",
        llm_api_key=SecretStr(SECRET), news_auto_refresh=False, news_media_fetch=False,
        demo_seed=True, archive_seed=True,
    )


@pytest.fixture
def snapshot():
    database = Database("sqlite:///:memory:")
    database.create()
    seed(database, ROOT, demo=True, include_archive=True)
    with database.session.begin() as session:
        goal = session.scalar(select(Goal))
        result = build_run(session, goal, 1, "compatible").snapshot
    database.engine.dispose()
    return result


def mock_transport(monkeypatch, handler):
    original = httpx.AsyncClient
    monkeypatch.setattr(
        httpx, "AsyncClient",
        lambda **kwargs: original(**kwargs, transport=httpx.MockTransport(handler)),
    )


def valid_output(snapshot):
    return asyncio.run(BaselineProvider().judge(snapshot))[0].model_dump()


def envelope(value, **extra):
    return {
        "id": "response-1", "model": "resolved-test-model", "system_fingerprint": "revision-1",
        "choices": [{"finish_reason": "stop", "message": {"content": json.dumps(value)}}],
        "usage": {"prompt_tokens": 20, "completion_tokens": 30, "total_tokens": 50}, **extra,
    }


@pytest.mark.parametrize("status,code", [
    (401, "authentication"), (403, "authentication"), (402, "quota"),
    (429, "rate_limit"), (500, "provider_http"),
])
def test_http_errors_are_safe_and_do_not_retry(configured, snapshot, monkeypatch, status, code):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(status, text=f"sensitive body {SECRET}")

    mock_transport(monkeypatch, handler)
    with pytest.raises(ProviderError) as caught:
        asyncio.run(CompatibleProvider(configured).judge(snapshot))
    error = caught.value
    assert error.code == code and len(calls) == 1
    assert error.metrics["model_called"] is True
    assert error.metrics["attempts"][0]["http_status"] == status
    assert error.metrics["request_count"] == 1 and error.metrics["repair_count"] == 0
    assert SECRET not in str(error) + json.dumps(error.metrics)


@pytest.mark.parametrize("exception,code", [
    (httpx.ReadTimeout, "timeout"), (httpx.ConnectError, "connection"),
])
def test_network_errors_keep_unknown_usage(configured, snapshot, monkeypatch, exception, code):
    def handler(request):
        raise exception(SECRET, request=request)

    mock_transport(monkeypatch, handler)
    with pytest.raises(ProviderError) as caught:
        asyncio.run(CompatibleProvider(configured).judge(snapshot))
    assert caught.value.code == code
    assert caught.value.metrics["usage_complete"] is False
    assert caught.value.metrics["token_usage"] == []
    assert SECRET not in str(caught.value)


@pytest.mark.parametrize("reason,code", [
    ("length", "output_truncated"), ("content_filter", "content_filtered"),
])
def test_unfinished_output_is_rejected_even_if_json_is_valid(
    configured, snapshot, monkeypatch, reason, code,
):
    value = envelope(valid_output(snapshot))
    value["choices"][0]["finish_reason"] = reason
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json=value)

    mock_transport(monkeypatch, handler)
    with pytest.raises(ProviderError) as caught:
        asyncio.run(CompatibleProvider(configured).judge(snapshot))
    assert caught.value.code == code and len(calls) == 1
    assert caught.value.metrics["token_usage"][0]["total_tokens"] == 50
    assert caught.value.metrics["usage_complete"] is True
    assert caught.value.metrics["validation_passed"] is False


def test_repair_keeps_both_usages_and_safe_response_metadata(configured, snapshot, monkeypatch):
    good = valid_output(snapshot)
    bad = {**good, "citations": [{"article_id": "invented", "paragraph_id": "p1"}]}
    calls = []

    def handler(request):
        calls.append(request)
        value = envelope(bad if len(calls) == 1 else good)
        value["usage"]["debug"] = SECRET
        value["choices"][0]["message"]["reasoning_content"] = "private reasoning"
        value["id"] = f"response-{SECRET}"
        return httpx.Response(200, json=value)

    mock_transport(monkeypatch, handler)
    result, metrics = asyncio.run(CompatibleProvider(configured).judge(snapshot))
    assert result.citations and metrics["validation_passed"] is True
    assert metrics["request_count"] == 2 and metrics["repair_count"] == 1
    assert [row["total_tokens"] for row in metrics["token_usage"]] == [50, 50]
    assert metrics["usage_complete"] is True and metrics["response_model"] == "resolved-test-model"
    assert metrics["attempts"][1]["system_fingerprint"] == "revision-1"
    assert SECRET not in json.dumps(metrics) and "private reasoning" not in json.dumps(metrics)


@pytest.mark.parametrize("payload", [
    [], {"choices": [None]}, {"choices": []},
    {"choices": [{"message": {"content": "", "reasoning_content": "not a final answer"}}]},
    {"choices": [{"message": {"content": "{broken"}}]},
])
def test_invalid_output_has_one_bounded_repair(configured, snapshot, monkeypatch, payload):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json=payload)

    mock_transport(monkeypatch, handler)
    with pytest.raises(ProviderError) as caught:
        asyncio.run(CompatibleProvider(configured).judge(snapshot))
    assert caught.value.code == "invalid_output" and len(calls) == 2
    assert caught.value.metrics["validation_passed"] is False


def test_oversized_input_and_no_candidate_never_send_request(configured, snapshot, monkeypatch):
    def handler(request):
        pytest.fail("no request expected")

    mock_transport(monkeypatch, handler)
    with pytest.raises(ProviderError) as caught:
        asyncio.run(CompatibleProvider(configured).judge({**snapshot, "oversize": "字" * 64000}))
    assert caught.value.code == "input_too_large"
    assert caught.value.metrics["model_called"] is False
    result, metrics = asyncio.run(CompatibleProvider(configured).judge({**snapshot, "evidence": []}))
    assert result.outcome == "insufficient_evidence" and metrics["model_called"] is False


def poll(client, run_id):
    for _ in range(200):
        run = client.get(f"/api/runs/{run_id}").json()
        if run["status"] not in {"queued", "running"}:
            return run
        time.sleep(0.01)
    pytest.fail("run did not finish")


def start(client):
    goal = client.get("/api/goals").json()[0]
    return client.post(
        f"/api/goals/{goal['id']}/checks", json={"expected_version": goal["version"]}
    ).json()["id"]


def test_failure_telemetry_persists_without_result_or_secret(configured, monkeypatch):
    mock_transport(monkeypatch, lambda request: httpx.Response(401, text=SECRET))
    with TestClient(create_app(configured)) as client:
        run_id = start(client)
        run = poll(client, run_id)
        assert run["status"] == "failed" and run["result"] is None
        assert run["metrics"]["error_code"] == "authentication"
        assert run["metrics"]["candidate_count"] > 0 and run["metrics"]["elapsed_ms"] >= 0
        assert SECRET not in json.dumps(run)
        assert client.get("/api/schedules").json() == []
    with TestClient(create_app(configured)) as restarted:
        assert restarted.get(f"/api/runs/{run_id}").json()["metrics"] == run["metrics"]


def test_cancel_during_real_adapter_request_preserves_cancellation(configured, monkeypatch):
    async def handler(request):
        await asyncio.sleep(60)
        pytest.fail("request must be cancelled")

    mock_transport(monkeypatch, handler)
    with TestClient(create_app(configured)) as client:
        run_id = start(client)
        for _ in range(200):
            if client.get(f"/api/runs/{run_id}").json()["status"] == "running":
                break
            time.sleep(0.01)
        assert client.post(f"/api/runs/{run_id}/cancel").status_code == 200
        for _ in range(200):
            run = client.get(f"/api/runs/{run_id}").json()
            if run["metrics"].get("error_code") == "cancelled":
                break
            time.sleep(0.01)
        assert run["status"] == "cancelled" and run["result"] is None
        assert run["metrics"]["model_called"] is True
        assert run["metrics"]["usage_complete"] is False


def test_edited_goal_cannot_publish_but_retains_returned_usage(configured, monkeypatch):
    async def handler(request):
        payload = json.loads(request.content)
        snapshot = json.loads(payload["messages"][1]["content"].removeprefix("SNAPSHOT:\n"))
        result, _ = await BaselineProvider().judge(snapshot)
        await asyncio.sleep(0.15)
        return httpx.Response(200, json=envelope(result.model_dump()))

    mock_transport(monkeypatch, handler)
    with TestClient(create_app(configured)) as client:
        run_id = start(client)
        for _ in range(200):
            if client.get(f"/api/runs/{run_id}").json()["status"] == "running":
                break
            time.sleep(0.01)
        goal = client.get("/api/goals").json()[0]
        fields = {key: goal[key] for key in (
            "name", "purpose", "scope", "constraints", "keywords", "trial_requested",
        )}
        fields.update(expected_version=goal["version"], purpose="只核实另一项条件与目标")
        assert client.patch(f"/api/goals/{goal['id']}", json=fields).status_code == 200
        run = poll(client, run_id)
        assert run["status"] == "stale" and run["result"] is None
        assert run["metrics"]["token_usage"][0]["total_tokens"] == 50
        with client.app.state.database.session() as session:
            assert session.get(Run, run_id).result is None


@pytest.mark.parametrize("http_status", [200, 429])
def test_acceptance_runner_isolates_storage_and_reports_failures(
    configured, tmp_path, monkeypatch, http_status,
):
    original = httpx.AsyncClient
    requests = []

    async def handler(request):
        requests.append(request)
        if http_status != 200:
            return httpx.Response(http_status, text=SECRET)
        payload = json.loads(request.content)
        snapshot = json.loads(payload["messages"][1]["content"].removeprefix("SNAPSHOT:\n"))
        result, _ = await BaselineProvider().judge(snapshot)
        return httpx.Response(200, json=envelope(result.model_dump()))

    def client(**kwargs):
        if "transport" not in kwargs:
            kwargs["transport"] = httpx.MockTransport(handler)
        return original(**kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", client)
    output_dir = tmp_path / "isolated-check"
    output_dir.mkdir()
    report = asyncio.run(run_check(configured, output_dir))
    assert report["live_model_check_passed"] is (http_status == 200)
    assert len(requests) == 1  # The empty-evidence run and restart never call the provider.
    assert not (tmp_path / "provider.db").exists()
    saved = (output_dir / "report.json").read_text("utf-8")
    assert json.loads(saved) == report and SECRET not in saved
    if http_status == 200:
        assert all(report["checks"].values())
        assert report["semantic_quality_verified"] is False
        assert "scripted" in report["decision_origin"]
    else:
        assert report["run"]["metrics"]["error_code"] == "rate_limit"
        assert report["run"]["result"] is None


def test_payload_preview_never_calls_network(configured, tmp_path, monkeypatch):
    def must_not_call(**kwargs):
        pytest.fail("preview must not create a network client")

    monkeypatch.setattr(httpx, "AsyncClient", must_not_call)
    path = preview_check(configured, tmp_path)
    preview = json.loads(path.read_text("utf-8"))
    assert preview["model_called"] is False and preview["maximum_requests"] == 2
    assert len(preview["snapshot"]["evidence"]) == 8
    assert all(row["origin"] == "archive" for row in preview["snapshot"]["evidence"])
    assert SECRET not in path.read_text("utf-8")
