import asyncio
import hashlib
import json
import time
from pathlib import Path

import httpx
import pytest
from cfaw_news.config import Settings
from cfaw_news.database import Article, Database, Goal
from cfaw_news.ingestion import NewsIngestor, catalog, parse_source
from cfaw_news.main import create_app
from cfaw_news.service import build_run, invalidation_reason
from fastapi.testclient import TestClient
from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[1]
PRIMARY = {"chinanews", "ithome", "36kr", "solidot", "ifanr", "geekpark", "mit", "hn"}


def rss(host="www.ithome.com", title="Mac 会议新闻", tracking="", image_url=""):
    image = f'<img src="{image_url}">' if image_url else ""
    return f"""<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/">
    <channel><title>Test</title><item><title>{title}</title>
    <link>https://{host}/post/1{tracking}</link>
    <description><![CDATA[<p>来源摘要</p>{image}<script>bad()</script>]]></description>
    <content:encoded><![CDATA[<p>来源正文片段</p>]]></content:encoded>
    <pubDate>Thu, 15 Oct 2026 06:00:00 GMT</pubDate></item></channel></rss>""".encode()


@pytest.fixture
def settings(tmp_path):
    return Settings(
        _env_file=None,
        database_url=f"sqlite:///{(tmp_path / 'news.db').as_posix()}",
        root=ROOT,
        llm_mode="baseline",
        news_auto_refresh=False,
        news_media_fetch=False,
    )


@pytest.fixture
def mocked_network(monkeypatch):
    calls = []
    controls = {"failed": set(), "changed": False, "redirect": False}
    monkeypatch.setattr(
        "socket.getaddrinfo", lambda *a, **kw: [(2, 1, 6, "", ("93.184.216.34", 443))]
    )

    def handler(request):
        calls.append(request)
        if request.url.host in controls["failed"]:
            return httpx.Response(503)
        if controls["redirect"] and request.url.host == "www.ithome.com":
            return httpx.Response(302, headers={"location": "https://unlisted.example/feed"})
        if request.url.host == "hacker-news.firebaseio.com":
            if request.url.path.endswith("newstories.json"):
                return httpx.Response(200, json=[1, 2, -1, "bad", 1])
            number = int(request.url.path.split("/")[-1].split(".")[0])
            if controls.get("hn_item_error") and number == 1:
                return httpx.Response(503)
            return httpx.Response(
                200,
                json={
                    "id": number,
                    "type": "story",
                    "title": f"HN story {number}",
                    "time": 1792044000,
                    "url": "https://example.com/article",
                    "text": "<b>Community text</b>" if number == 1 else "",
                },
            )
        etag = '"v2"' if controls["changed"] else '"v1"'
        if request.headers.get("if-none-match") == etag:
            return httpx.Response(304, headers={"etag": etag})
        return httpx.Response(
            200,
            content=rss(
                request.url.host,
                "Mac 会议更正" if controls["changed"] else "Mac 会议新闻",
                image_url=controls.get("image_url", ""),
            ),
            headers={"etag": etag},
        )

    original = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: original(**kwargs, transport=httpx.MockTransport(handler)),
    )
    return calls, controls


def test_primary_overlay_preserves_migrated_assets():
    sources = catalog(ROOT)["sources"]
    assert {s["id"] for s in sources if s["enabled"]} == PRIMARY
    assert {s["id"] for s in sources if s["primary"]} == PRIMARY
    manifest = json.loads((ROOT / "docs/provenance/migration-manifest.json").read_text("utf-8"))
    for item in manifest["copied_assets"]:
        assert (
            hashlib.sha256((ROOT / item["destination"]).read_bytes()).hexdigest() == item["sha256"]
        )


def test_rss_mapping_canonical_identity_and_timestamp():
    source = next(s for s in catalog(ROOT)["sources"] if s["id"] == "ithome")
    first = parse_source(source, rss(tracking="?utm_source=test#fragment"))[0]
    second = parse_source(source, rss())[0]
    assert first["id"] == second["id"]
    assert first["content_hash"] == second["content_hash"]
    assert first["summary"] == "来源摘要"
    assert first["paragraphs"] == [{"id": "p1", "text": "来源摘要", "kind": "rss_description"}]
    assert first["published_at"] == "2026-10-15T06:00:00+00:00"
    source = {**source, "summary_field": "none", "body_field": "content:encoded"}
    row = parse_source(source, rss())[0]
    assert row["summary"] == ""
    assert row["paragraphs"][0] == {"id": "p1", "text": "来源正文片段", "kind": "rss_body"}


def test_atom_updated_time_does_not_invent_publication():
    source = {"id": "atom", "label": "Atom", "kind": "atom"}
    body = b"""<feed xmlns="http://www.w3.org/2005/Atom"><title>Feed</title><entry>
    <title>Entry</title><link href="https://example.com/1"/>
    <updated>2026-10-15T06:00:00Z</updated><summary>Summary</summary></entry></feed>"""
    row = parse_source(source, body)[0]
    assert row["published_at"] is None
    assert row["updated_at"] == "2026-10-15T06:00:00+00:00"


@pytest.mark.parametrize(
    ("markup", "expected"),
    [
        (
            '<description><![CDATA[<img src="/cover.jpg">]]></description>',
            "https://example.com/cover.jpg",
        ),
        (
            '<media:thumbnail url="https://cdn.example.com/photo.jpg"/>',
            "https://cdn.example.com/photo.jpg",
        ),
        (
            '<enclosure url="https://example.com/pic.jpg" type="image/jpeg"/>',
            "https://example.com/pic.jpg",
        ),
        (
            '<description><![CDATA[<img src="https://127.0.0.1/secret"><img src="javascript:bad"><img width="1" src="https://example.com/pixel"><img src="https://example.com/real.jpg">]]></description>',
            "https://example.com/real.jpg",
        ),
        ('<enclosure url="https://example.com/audio.mp3" type="audio/mpeg"/>', None),
        ('<media:thumbnail url="https://[broken/cover.jpg"/>', None),
    ],
)
def test_feed_images_are_optional_source_metadata(markup, expected):
    body = f"""<rss version="2.0" xmlns:media="http://search.yahoo.com/mrss/"><channel>
    <item><title>Story</title><link>https://example.com/news</link>{markup}</item>
    </channel></rss>""".encode()
    row = parse_source({"id": "images", "label": "Images", "kind": "rss"}, body)[0]
    assert row["image_url"] == expected


def test_image_change_preserves_text_evidence_identity(settings):
    with TestClient(create_app(settings)) as client:
        engine = client.app.state.news_ingestor
        source = engine.sources["ithome"]
        rows = parse_source(source, rss())

        async def read(*args):
            return rows, {}

        engine.read = read
        client.post("/api/sources/refresh", json={"source_ids": ["ithome"]})
        before = client.get("/api/articles?source_id=ithome").json()[0]
        rows[0]["image_url"] = "https://example.com/new-cover.jpg"
        result = client.post("/api/sources/refresh", json={"source_ids": ["ithome"]}).json()[
            "results"
        ][0]
        after = client.get("/api/articles?source_id=ithome").json()[0]
        assert after["image_url"] == rows[0]["image_url"]
        assert after["content_hash"] == before["content_hash"]
        assert after["captured_at"] == before["captured_at"]
        assert result["updated_count"] == 0


def test_hn_keeps_submission_and_original_article_distinct():
    source = {"id": "hn", "label": "HN", "kind": "hn_official"}
    row = parse_source(
        source,
        json.dumps(
            [
                {
                    "id": 10,
                    "type": "story",
                    "title": "Story",
                    "time": 1792044000,
                    "url": "https://example.com/news?utm_source=hn",
                    "text": "<p>Submission</p>",
                },
                {"id": 11, "type": "story", "title": "Deleted", "deleted": True},
                {"id": 12, "type": "comment", "text": "comment"},
            ]
        ).encode(),
    )[0]
    assert row["published_at"] is None and row["submitted_at"]
    assert row["source_url"] == "https://news.ycombinator.com/item?id=10"
    assert row["original_url"] == "https://example.com/news"
    assert row["paragraphs"][0]["kind"] == "community_text"


def test_refresh_all_eight_filters_pagination_and_conditional_dedup(settings, mocked_network):
    calls, _ = mocked_network
    with TestClient(create_app(settings)) as client:
        result = client.post("/api/sources/refresh", json={"source_ids": sorted(PRIMARY)})
        assert result.status_code == 200
        assert all(r["status"] == "ok" for r in result.json()["results"])
        rows = client.get("/api/articles?origin=feed").json()
        assert len(rows) == 9
        first = {r["id"]: r for r in rows}
        assert len(client.get("/api/articles?origin=archive").json()) == 26
        assert len(client.get("/api/articles?origin=feed&category=tech").json()) == 5
        assert len(client.get("/api/articles?source_id=hn").json()) == 2
        ordered = client.get("/api/articles?origin=feed&limit=2").json()
        rest = client.get("/api/articles?origin=feed&offset=2&limit=2").json()
        assert {r["id"] for r in ordered}.isdisjoint(r["id"] for r in rest)
        again = client.post("/api/sources/refresh", json={"source_ids": sorted(PRIMARY)}).json()
        assert all(r["new_count"] == 0 and r["updated_count"] == 0 for r in again["results"])
        assert any(r.headers.get("if-none-match") for r in calls)
        for row in client.get("/api/articles?origin=feed").json():
            old = first[row["id"]]
            assert row["content_hash"] == old["content_hash"]
            assert row["captured_at"] == old["captured_at"]
            assert row["first_seen_at"] == old["first_seen_at"]
        states = client.get("/api/sources").json()
        assert all(s["state"]["status"] == "ok" for s in states if s["primary"])


def test_refresh_failure_preserves_cache_and_success_time(settings, mocked_network):
    _, controls = mocked_network
    with TestClient(create_app(settings)) as client:
        client.post("/api/sources/refresh", json={"source_ids": ["ithome"]})
        before = client.get("/api/articles?source_id=ithome").json()
        state = next(s["state"] for s in client.get("/api/sources").json() if s["id"] == "ithome")
        controls["failed"].add("www.ithome.com")
        failure = client.post("/api/sources/refresh", json={"source_ids": ["ithome"]}).json()[
            "results"
        ][0]
        assert failure["status"] == "error" and failure["error_code"] == "http_503"
        assert failure["last_success_at"] == state["last_success_at"]
        assert client.get("/api/articles?source_id=ithome").json() == before


def test_legacy_cache_fetches_image_metadata_before_reusing_validators(settings, mocked_network):
    calls, _ = mocked_network
    with TestClient(create_app(settings)) as client:
        client.post("/api/sources/refresh", json={"source_ids": ["ithome"]})
        engine = client.app.state.news_ingestor
        old_state = engine.state("ithome")
        old_state.pop("image_metadata_version")
        engine.save_state("ithome", old_state)
        before = client.get("/api/articles?source_id=ithome").json()[0]
        calls.clear()
        result = client.post("/api/sources/refresh", json={"source_ids": ["ithome"]}).json()[
            "results"
        ][0]
        assert not result["not_modified"]
        assert not calls[0].headers.get("if-none-match")
        after = client.get("/api/articles?source_id=ithome").json()[0]
        assert after["content_hash"] == before["content_hash"]
        assert after["captured_at"] == before["captured_at"]
        again = client.post("/api/sources/refresh", json={"source_ids": ["ithome"]}).json()[
            "results"
        ][0]
        assert again["not_modified"]


def test_source_update_keeps_old_snapshot_and_first_seen(settings, mocked_network):
    _, controls = mocked_network
    with TestClient(create_app(settings)) as client:
        client.post("/api/sources/refresh", json={"source_ids": ["ithome"]})
        database = client.app.state.database
        before = client.get("/api/articles?source_id=ithome").json()[0]
        with database.session.begin() as session:
            goal = Goal(
                data={
                    "name": "来源摘要",
                    "purpose": "核实来源摘要内容",
                    "scope": "",
                    "constraints": "",
                    "keywords": ["来源摘要"],
                    "trial_requested": False,
                }
            )
            session.add(goal)
            session.flush()
            run = build_run(session, goal, 1, "baseline")
            run_id = run.id
            assert before["id"] in {row["id"] for row in run.snapshot["evidence"]}
            saved_before = json.loads(
                json.dumps(
                    next(row for row in run.snapshot["evidence"] if row["id"] == before["id"])
                )
            )
        controls["changed"] = True
        result = client.post("/api/sources/refresh", json={"source_ids": ["ithome"]}).json()[
            "results"
        ][0]
        after = client.get("/api/articles?source_id=ithome").json()[0]
        assert result["updated_count"] == 1 and result["new_count"] == 0
        assert after["first_seen_at"] == before["first_seen_at"]
        assert after["content_hash"] != before["content_hash"]
        from cfaw_news.database import Run

        with database.session() as session:
            saved = session.get(Run, run_id)
            evidence = next(row for row in saved.snapshot["evidence"] if row["id"] == before["id"])
            assert evidence == saved_before
            assert invalidation_reason(session, saved)


def test_redirect_outside_catalog_is_rejected(settings, mocked_network):
    calls, controls = mocked_network
    controls["redirect"] = True
    with TestClient(create_app(settings)) as client:
        result = client.post("/api/sources/refresh", json={"source_ids": ["ithome"]}).json()[
            "results"
        ][0]
        assert result["status"] == "error"
        assert not any(r.url.host == "unlisted.example" for r in calls)


def test_hn_item_failure_does_not_publish_partial_refresh(settings, mocked_network):
    _, controls = mocked_network
    with TestClient(create_app(settings)) as client:
        client.post("/api/sources/refresh", json={"source_ids": ["hn"]})
        before = client.get("/api/articles?source_id=hn").json()
        controls["hn_item_error"] = True
        result = client.post("/api/sources/refresh", json={"source_ids": ["hn"]}).json()
        assert result["results"][0]["status"] == "error"
        assert client.get("/api/articles?source_id=hn").json() == before


def test_restart_recovers_interrupted_source(settings):
    database = Database(settings.database_url)
    database.create()
    engine = NewsIngestor(database, ROOT)
    engine.save_state(
        "ithome",
        {
            "status": "refreshing",
            "last_success_at": "2026-10-14T00:00:00+00:00",
            "next_refresh_at": "2099-01-01T00:00:00+00:00",
        },
    )
    called = []
    done = asyncio.Event()

    async def fake_refresh(ids):
        called.extend(ids)
        done.set()
        return []

    engine.refresh = fake_refresh

    async def run():
        engine.start()
        recovered = engine.state("ithome")
        assert recovered["status"] == "error" and recovered["error_code"] == "interrupted"
        assert recovered["last_success_at"] == "2026-10-14T00:00:00+00:00"
        await asyncio.wait_for(done.wait(), 1)
        await engine.close()

    asyncio.run(run())
    assert "ithome" in called
    database.engine.dispose()


def test_startup_backfills_legacy_image_cache_without_waiting(settings, mocked_network):
    calls, controls = mocked_network
    with TestClient(create_app(settings)) as client:
        client.post("/api/sources/refresh", json={"source_ids": sorted(PRIMARY)})
        before = client.get("/api/articles?source_id=ithome").json()[0]
        engine = client.app.state.news_ingestor
        old_state = engine.state("ithome")
        old_state.pop("image_metadata_version")
        old_state["next_refresh_at"] = "2099-01-01T00:00:00+00:00"
        engine.save_state("ithome", old_state)

    calls.clear()
    controls["image_url"] = "https://example.com/source-cover.jpg"
    configured = settings.model_copy(update={"news_auto_refresh": True})
    with TestClient(create_app(configured)) as client:
        for _ in range(150):
            after = client.get("/api/articles?source_id=ithome").json()[0]
            if after.get("image_url"):
                break
            time.sleep(0.01)
        else:
            pytest.fail("legacy image metadata was not backfilled at startup")
        assert after["image_url"] == controls["image_url"]
        assert after["content_hash"] == before["content_hash"]
        assert after["captured_at"] == before["captured_at"]
        assert after["first_seen_at"] == before["first_seen_at"]
        assert len(calls) == 1 and calls[0].url.host == "www.ithome.com"
        assert not calls[0].headers.get("if-none-match")
        state = client.app.state.news_ingestor.state("ithome")
        assert state["image_metadata_version"] == 1 and state["updated_count"] == 0
        assert client.get("/api/runs").json() == []
        assert client.get("/api/schedules").json() == []


def test_concurrent_refresh_of_same_source_is_coalesced(settings):
    database = Database(settings.database_url)
    database.create()
    engine = NewsIngestor(database, ROOT)
    entered, release = asyncio.Event(), asyncio.Event()
    reads = []

    async def fake_read(client, source, previous):
        reads.append(source["id"])
        entered.set()
        await release.wait()
        return parse_source(source, rss()), {}

    engine.read = fake_read

    async def run():
        first = asyncio.create_task(engine.refresh(["ithome"]))
        await entered.wait()
        second = await engine.refresh(["ithome"])
        release.set()
        return await first, second

    first, second = asyncio.run(run())
    assert reads == ["ithome"]
    assert first[0]["new_count"] == 1 and second[0]["status"] == "refreshing"
    database.engine.dispose()


def test_due_schedule_is_persistent_and_does_not_refetch_early(settings, mocked_network):
    calls, _ = mocked_network
    database = Database(settings.database_url)
    database.create()
    engine = NewsIngestor(database, ROOT)
    asyncio.run(engine.refresh_due())
    count = len(calls)
    restarted = NewsIngestor(database, ROOT)
    assert asyncio.run(restarted.refresh_due()) == []
    assert len(calls) == count
    state = restarted.state("ithome")
    restarted.save_state("ithome", {**state, "next_refresh_at": "2000-01-01T00:00:00+00:00"})
    results = asyncio.run(restarted.refresh_due())
    assert [r["source_id"] for r in results] == ["ithome"]
    database.engine.dispose()


def test_background_polling_ingests_without_triggering_goal_runs(settings, mocked_network):
    configured = settings.model_copy(update={"news_auto_refresh": True})
    with TestClient(create_app(configured)) as client:
        for _ in range(150):
            sources = client.get("/api/sources").json()
            if all(s["state"]["status"] == "ok" for s in sources if s["primary"]):
                break
            time.sleep(0.01)
        else:
            pytest.fail("background refresh did not finish")
        assert len(client.get("/api/articles?origin=feed").json()) == 9
        assert client.get("/api/runs").json() == []
        assert client.get("/api/schedules").json() == []
        with client.app.state.database.session() as session:
            assert len(list(session.scalars(select(Article)))) == 35
