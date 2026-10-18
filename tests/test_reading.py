import asyncio
import base64
import copy
from pathlib import Path

import httpx
import pytest
from cfaw_news.config import Settings
from cfaw_news.database import Article, ArticleReading, Decision, Goal, Run, Schedule
from cfaw_news.ingestion import article_row, parse_source
from cfaw_news.main import create_app
from cfaw_news.reading import NODE_LIMIT, TEXT_LIMIT, extract_page, reading_document
from cfaw_news.service import build_run
from fastapi.testclient import TestClient
from sqlalchemy import func, select

ROOT = Path(__file__).resolve().parents[1]
PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII="
)


def test_chinanews_reading_excludes_header_download_ad_and_other_articles():
    markup = '<header><p>Navigation words</p><img src="/toparr.png"></header><div class="left_zw"><p>' + "这是文章的真实正文与事实描述。" * 40 + '</p><img src="//i2.chinanews.com.cn/photo.jpg"></div><div class="download_wrapper"><p>Download advertisement</p><img src="/download.png"></div><aside><p>Unrelated article</p><img src="/other.jpg"></aside>'
    result = extract_page(markup, "https://www.chinanews.com.cn/sh/2026/10-18/10716877.shtml")
    assert result["images"] == ["https://i2.chinanews.com.cn/photo.jpg"]
    assert result["text_chars"] >= 400
    assert all(text not in str(result["nodes"]) for text in ("Navigation", "Download", "Unrelated"))


def test_missing_chinanews_body_fails_closed_for_reading():
    with pytest.raises(ValueError, match="no_readable_content"):
        extract_page('<article><p>' + 'Recommendation text. ' * 100 + '</p></article>', "https://www.chinanews.com.cn/test.shtml")


def test_chinanews_gallery_keeps_current_photo_and_caption_without_neighboring_galleries():
    markup = '<nav><img src="/toparr.png"></nav><div class="tuji_current_img left"><div class="current_img"><img src="//i2.chinanews.com.cn/current.jpg"></div></div><div class="current_img_desc_wrapper"><p>' + 'This is the caption describing the current photograph. ' * 8 + '</p></div><div class="tuji_list"><img src="/another-gallery.jpg"></div>'
    result = extract_page(markup, "https://www.chinanews.com.cn/tp/hd2011/2026/10-18/1208213.shtml")
    assert result["images"] == ["https://i2.chinanews.com.cn/current.jpg"]
    assert 'caption describing the current' in str(result["nodes"])


@pytest.fixture
def reading_app(tmp_path):
    settings = Settings(
        _env_file=None,
        root=ROOT,
        database_url=f"sqlite:///{(tmp_path / 'reading.db').as_posix()}",
        llm_mode="baseline",
        news_auto_refresh=False,
        news_media_fetch=False,
        news_reading_fetch=False,
    )
    app = create_app(settings)
    app.state.media_cache.root = tmp_path / "media"
    with TestClient(app) as client:
        row = article_row(
            {"id": "github-blog", "label": "GitHub Blog"},
            "https://github.blog/test/",
            "A GitHub article",
            "content summary",
            [{"id": "p1", "text": "content evidence", "kind": "rss_body"}],
            None,
        )
        with app.state.database.session.begin() as session:
            session.add(
                Article(id=row["id"], origin="feed", content_hash=row["content_hash"], data=row)
            )
        yield client, app, row


def cached(app, row, markup):
    document = reading_document(markup, row["source_url"])
    document["evidence_hash"] = row["content_hash"]
    with app.state.database.session.begin() as session:
        session.add(ArticleReading(article_id=row["id"], data=document))
    return document


def test_reader_removes_active_content_resolves_media_and_bounds_trees():
    document = reading_document(
        """<h2 onclick="bad()">Heading</h2><script>secret</script>
        <iframe src="/bad"></iframe><form>private form</form><p hidden>invisible</p>
        <a href="javascript:bad()">safe text</a><a href="/reference">reference</a>
        <img src="data:image/png,bad" data-src="/photo.png" onerror="bad()" alt="Photo">
        <img src="http://127.0.0.1/secret"><img src="/pixel.gif" width="1">
        <pre><code>print(&quot;hello&quot;)</code></pre><table><tr><td>cell</td></tr></table>""",
        "https://github.blog/news/",
    )
    text = str(document["nodes"])
    assert all(
        word not in text
        for word in (
            "onclick",
            "onerror",
            "javascript:",
            "secret",
            "private form",
            "invisible",
            "iframe",
        )
    )
    assert "https://github.blog/reference" in text
    assert document["images"] == ["https://github.blog/photo.png"]
    assert "code" in text and "table" in text and 'print("hello")' in text
    assert reading_document("<p>" + "a" * (TEXT_LIMIT + 100) + "</p>", "https://example.com")[
        "truncated"
    ]
    assert reading_document("<p>a</p>" * (NODE_LIMIT + 10), "https://example.com")["truncated"]


def test_complete_rss_is_persisted_separately_from_bounded_snapshot(reading_app):
    client, app, _ = reading_app
    engine = app.state.news_ingestor
    source = engine.sources["github-blog"]
    body = (
        "<rss xmlns:content='http://purl.org/rss/1.0/modules/content/'><channel><item>"
        "<title>content full story</title><link>https://github.blog/full/</link>"
        "<description>content summary</description><content:encoded><![CDATA[<h2>Full body</h2><p>"
        + "content " * 1500
        + "</p><img src='/full.jpg'/>]]></content:encoded></item></channel></rss>"
    ).encode()

    async def read(*args):
        return parse_source(source, body), {}

    engine.read = read
    assert (
        client.post("/api/sources/refresh", json={"source_ids": ["github-blog"]}).json()["results"][
            0
        ]["new_count"]
        == 1
    )
    article = next(
        a for a in client.get("/api/articles").json() if a["title"] == "content full story"
    )
    assert "_reading" not in article and len(article["paragraphs"][0]["text"]) == 4000
    response = client.get(f"/api/articles/{article['id']}/reading").json()
    assert response["source"] == "rss" and response["text_chars"] > 10000
    assert (
        response["image_count"] == 1
        and "images" not in response
        and "evidence_hash" not in response
    )
    with app.state.database.session.begin() as session:
        goal = Goal(
            data={
                "name": "content",
                "purpose": "content",
                "scope": "",
                "constraints": "",
                "keywords": ["content"],
                "trial_requested": False,
            }
        )
        session.add(goal)
        session.flush()
        run = build_run(session, goal, 1, "baseline")
        snapshot = copy.deepcopy(run.snapshot)
        run_id = run.id
        assert all("_reading" not in item for item in snapshot["evidence"])
    # A later source body change must not modify a saved run or its paragraphs.
    with app.state.database.session.begin() as session:
        reading = session.get(ArticleReading, article["id"])
        reading.data = {**reading.data, "nodes": [], "text_chars": 0}
    with app.state.database.session() as session:
        assert session.get(Run, run_id).snapshot == snapshot


def test_web_body_extraction_does_not_change_evidence_or_create_domain_actions(
    reading_app, monkeypatch
):
    client, app, row = reading_app
    calls = []

    async def read(url, **kwargs):
        calls.append((url, kwargs))
        html = (
            "<html><body><nav>MENU</nav><article><h1>Article</h1>"
            + "".join(
                f"<p>Detailed content paragraph {i}. "
                + "Source article text with enough meaningful information. " * 5
                + "</p>"
                for i in range(6)
            )
            + '<img src="/placeholder.png" data-original="/body.png"></article><footer>FOOTER</footer></body></html>'
        )
        return url, "text/html; charset=utf-8", html.encode()

    monkeypatch.setattr("cfaw_news.reading.public_document", read)
    before = client.get(f"/api/articles/{row['id']}").json()
    asyncio.run(app.state.reading_cache.process(row))
    response = client.get(f"/api/articles/{row['id']}/reading").json()
    assert (
        response["status"] == "ready"
        and response["source"] == "web"
        and response["text_chars"] > 1000
    )
    assert "MENU" not in str(response["nodes"]) and "FOOTER" not in str(response["nodes"])
    assert calls[0][1]["max_bytes"] == 2_000_000
    with app.state.database.session() as session:
        assert session.get(ArticleReading, row["id"]).data["images"] == [
            "https://github.blog/body.png"
        ]
    assert client.get(f"/api/articles/{row['id']}").json() == before
    with app.state.database.session() as session:
        for model in (Run, Decision, Schedule):
            assert session.scalar(select(func.count()).select_from(model)) == 0


def test_reading_image_only_fetches_saved_index_and_reuses_local_cache(reading_app, monkeypatch):
    client, app, row = reading_app
    cached(app, row, '<p>Source body</p><img src="/photo.png">')
    calls = []

    async def read(url, **kwargs):
        calls.append(url)
        return url, "image/png", PNG

    monkeypatch.setattr("cfaw_news.reading.public_document", read)
    app.state.media_cache.enabled = True
    url = f"/api/articles/{row['id']}/reading/images/"
    assert client.get(url + "41").status_code == 404
    first = client.get(url + "0")
    assert first.status_code == 200 and first.content == PNG
    assert first.headers["x-content-type-options"] == "nosniff"
    assert client.get(url + "0").content == PNG
    assert calls == ["https://github.blog/photo.png"]


def test_failure_is_explicit_and_backed_off(reading_app, monkeypatch):
    client, app, row = reading_app

    async def read(*args, **kwargs):
        raise httpx.ConnectError("offline")

    monkeypatch.setattr("cfaw_news.reading.public_document", read)
    asyncio.run(app.state.reading_cache.process(row))
    app.state.reading_cache.enabled = True
    response = client.get(f"/api/articles/{row['id']}/reading").json()
    assert response["status"] == "unavailable" and response["nodes"] == []
    assert app.state.reading_cache.queue.empty()
    assert response["retry_at"]


def test_stale_web_job_cannot_replace_new_evidence(reading_app, monkeypatch):
    _, app, row = reading_app

    async def read(url, **kwargs):
        with app.state.database.session.begin() as session:
            session.get(Article, row["id"]).content_hash = "new-version"
        return (
            url,
            "text/html",
            b"<article><p>" + b"Detailed public article content. " * 60 + b"</p></article>",
        )

    monkeypatch.setattr("cfaw_news.reading.public_document", read)
    asyncio.run(app.state.reading_cache.process(row))
    with app.state.database.session() as session:
        assert session.get(ArticleReading, row["id"]) is None


def test_queue_coalesces_and_disabled_reading_is_explicit(reading_app):
    client, app, row = reading_app
    route = f"/api/articles/{row['id']}/reading"
    assert client.get(route).json()["status"] == "unavailable"
    app.state.reading_cache.enabled = True
    assert client.get(route).json()["status"] == "fetching"
    assert client.get(route).json()["status"] == "fetching"
    assert app.state.reading_cache.queue.qsize() == 1
    assert client.get("/api/articles/missing/reading").status_code == 404


def test_ruanyifeng_uses_https_and_atom_content_for_reading():
    source = {
        "id": "ruanyifeng",
        "label": "阮一峰",
        "kind": "atom",
        "body_field": "content",
        "body_is_full": True,
        "article_https": True,
    }
    markup = b'<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>Weekly</title><link href="http://www.ruanyifeng.com/blog/weekly.html"/><content type="html">&lt;p&gt;Full weekly body&lt;/p&gt;</content></entry></feed>'
    article = parse_source(source, markup)[0]
    assert article["source_url"].startswith("https://")
    assert article["_reading"]["text_chars"] == 16


def test_worker_survives_a_bad_document(reading_app):
    _, app, row = reading_app
    cache = app.state.reading_cache

    async def run():
        handled = []

        async def process(article):
            handled.append(article["id"])
            if len(handled) == 1:
                raise RuntimeError("malformed document")

        cache.process = process
        worker = asyncio.create_task(cache.worker())
        await cache.queue.put(row)
        await cache.queue.put({**row, "id": "second"})
        await asyncio.wait_for(cache.queue.join(), 1)
        worker.cancel()
        await asyncio.gather(worker, return_exceptions=True)
        assert handled == [row["id"], "second"]

    asyncio.run(run())
