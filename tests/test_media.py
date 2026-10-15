import asyncio
import base64
import copy
import json
import socket
import ssl
from datetime import datetime
from pathlib import Path

import httpx
import pytest
from cfaw_news.config import Settings
from cfaw_news.database import Article, ArticleMedia, Goal, Run
from cfaw_news.ingestion import article_row
from cfaw_news.main import create_app
from cfaw_news.media import (
    DNS_CACHE,
    MEDIA_REVISION,
    OriginTLS,
    PageImages,
    image_extension,
    pinned_addresses,
    public_document,
    reddit_post_url,
)
from cfaw_news.service import build_run
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII="
)


@pytest.fixture(autouse=True)
def clear_dns_cache():
    DNS_CACHE.clear()
    yield
    DNS_CACHE.clear()


@pytest.fixture
def media_app(tmp_path):
    settings = Settings(
        _env_file=None,
        root=ROOT,
        database_url=f"sqlite:///{(tmp_path / 'media.db').as_posix()}",
        news_auto_refresh=False,
        news_media_fetch=False,
        llm_mode="baseline",
    )
    app = create_app(settings)
    app.state.media_cache.root = tmp_path / "covers"
    with TestClient(app) as client:
        row = article_row(
            {"id": "hn", "label": "HN"},
            "https://news.ycombinator.com/item?id=1",
            "完整标题 News headline",
            "evidence summary",
            [{"id": "p1", "text": "evidence summary", "kind": "community_text"}],
            None,
            original_url="https://publisher.example/story",
        )
        with app.state.database.session.begin() as session:
            session.add(
                Article(id=row["id"], origin="feed", content_hash=row["content_hash"], data=row)
            )
        yield client, app.state.media_cache, row


@pytest.fixture
def cover_documents(monkeypatch):
    calls = []
    controls = {"fail": False, "empty": False}

    async def read(url, *, image=False, referer=""):
        calls.append((url, image, referer))
        if controls["fail"]:
            raise httpx.ConnectError("offline")
        if image:
            return url, "image/png", PNG
        markup = b'<html><meta property="og:image" content="/cover.png"></html>'
        return url, "text/html", b"<html></html>" if controls["empty"] else markup

    monkeypatch.setattr("cfaw_news.media.public_document", read)
    return calls, controls


def test_original_page_cover_is_served_locally_without_changing_evidence(
    media_app, cover_documents
):
    client, cache, article = media_app
    with cache.database.session.begin() as session:
        goal = Goal(
            data={
                "name": "summary",
                "purpose": "evidence summary",
                "scope": "",
                "constraints": "",
                "keywords": ["evidence"],
                "trial_requested": False,
            }
        )
        session.add(goal)
        session.flush()
        run = build_run(session, goal, 1, "baseline")
        saved_snapshot = copy.deepcopy(run.snapshot)
        run_id = run.id
    asyncio.run(cache.process(article))
    shown = next(
        a for a in client.get("/api/articles?origin=feed").json() if a["id"] == article["id"]
    )
    assert shown["image_status"] == "ready" and shown["image_origin"] == "page_metadata"
    assert shown["image_url"].startswith("/api/articles/") and "?v=" in shown["image_url"]
    response = client.get(shown["image_url"])
    assert response.status_code == 200 and response.content == PNG
    assert response.headers["content-type"] == "image/png"
    assert response.headers["x-content-type-options"] == "nosniff"
    with cache.database.session() as session:
        assert session.get(Article, article["id"]).data == article
        assert session.get(Run, run_id).snapshot == saved_snapshot
    assert client.get("/api/articles/missing/image").status_code == 404


def test_feed_image_has_priority_and_cache_survives_remote_failure(media_app, cover_documents):
    _, cache, article = media_app
    calls, controls = cover_documents
    article = {**article, "image_url": "https://cdn.example/feed.png"}
    asyncio.run(cache.process(article))
    original = cache.decorate([article])[0]
    assert len(calls) == 1 and calls[0][1] is True
    assert original["image_origin"] == "feed"
    controls["fail"] = True
    asyncio.run(cache.process(article))
    assert cache.decorate([article])[0]["image_url"] == original["image_url"]


def test_no_image_and_unavailable_have_distinct_persisted_status(media_app, cover_documents):
    _, cache, article = media_app
    _, controls = cover_documents
    controls["empty"] = True
    asyncio.run(cache.process(article))
    assert cache.decorate([article])[0]["image_status"] == "no_image"
    controls["fail"] = True
    asyncio.run(cache.process(article))
    assert cache.decorate([article])[0]["image_status"] == "unavailable"


def test_demand_queue_coalesces_requests_and_reuses_cached_cover(media_app, cover_documents):
    _, cache, article = media_app
    cache.enabled = True

    async def check():
        cache.start()
        try:
            first = cache.decorate([article] * 40)
            cache.decorate([article])
            assert all(a["image_status"] == "pending" for a in first)
            assert cache.queue.qsize() == 1
            await asyncio.wait_for(cache.queue.join(), 1)
            assert cache.decorate([article])[0]["image_status"] == "ready"
            assert cache.queue.empty()
            cache.decorate([{**article, "id": "archive", "origin": "archive"}])
            assert cache.queue.empty()
        finally:
            await cache.close()

    asyncio.run(check())


def test_invalid_cache_path_cannot_be_served(media_app):
    client, cache, article = media_app
    with cache.database.session.begin() as session:
        session.add(
            ArticleMedia(
                article_id=article["id"],
                data={"filename": "../../secret.png", "content_type": "image/png"},
            )
        )
    assert client.get(f"/api/articles/{article['id']}/image").status_code == 404
    assert cache.image_file({"filename": "not-a-digest.png"}) is None


def test_parser_prefers_share_image_then_article_picture_and_skips_icons():
    parser = PageImages()
    parser.feed("""<img src="/logo.png"><meta property="og:image" content="//cdn.example/share.png">
    <meta name="twitter:image" content="/twitter.png"><main><img width="1" src="/track.png">
    <img src="/article.jpg"></main><img src="/other.jpg">""")
    assert parser.candidates("https://publisher.example/post") == [
        "https://cdn.example/share.png",
        "https://publisher.example/twitter.png",
        "https://publisher.example/article.jpg",
        "https://publisher.example/other.jpg",
    ]


@pytest.mark.parametrize("body", [b"<svg></svg>", b"<script>bad()</script>", b"not a photo"])
def test_active_or_unknown_image_formats_are_not_cached(body):
    with pytest.raises(ValueError):
        image_extension(body)


@pytest.fixture
def pinned_transport(monkeypatch):
    calls = []
    controls = {
        "redirect": False,
        "private_dns": False,
        "oversize": False,
        "denial": False,
        "proxy_denial": False,
    }

    def addresses(*args, **kwargs):
        return [
            (
                socket.AF_INET,
                socket.SOCK_STREAM,
                6,
                "",
                ("127.0.0.1" if controls["private_dns"] else "93.184.216.34", 443),
            )
        ]

    def handler(request):
        calls.append(request)
        if controls["proxy_denial"]:
            raise httpx.ProxyError("403 Forbidden", request=request)
        if controls["denial"]:
            return httpx.Response(403)
        if controls["redirect"]:
            return httpx.Response(302, headers={"location": "https://127.0.0.1/secret"})
        return httpx.Response(
            200,
            headers={"content-type": "image/png"},
            content=PNG + (b"x" * 4_000_000 if controls["oversize"] else b""),
        )

    original = httpx.AsyncClient
    monkeypatch.setattr("socket.getaddrinfo", addresses)
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: original(**kwargs, transport=httpx.MockTransport(handler)),
    )
    return calls, controls


def test_outbound_connection_is_pinned_but_tls_and_host_use_original_name(pinned_transport):
    calls, _ = pinned_transport
    result = asyncio.run(
        public_document(
            "https://publisher.example/image.png",
            image=True,
            referer="https://publisher.example/article?private=query",
        )
    )
    assert result[2] == PNG
    assert calls[0].url.host == "93.184.216.34"
    assert calls[0].headers["host"] == "publisher.example"
    assert calls[0].extensions["sni_hostname"] == "publisher.example"
    assert calls[0].headers["referer"] == "https://publisher.example/"
    assert "cookie" not in calls[0].headers and "authorization" not in calls[0].headers


def test_address_attempt_limit_keeps_ipv4_when_host_has_many_ipv6_records(monkeypatch):
    addresses = [
        "2606:4700::1111",
        "2606:4700::1001",
        "2001:4860:4860::8888",
        "2001:4860:4860::8844",
        "93.184.216.34",
        "1.1.1.1",
    ]
    monkeypatch.setattr(
        "socket.getaddrinfo",
        lambda *args, **kwargs: [(0, 1, 6, "", (value, 443)) for value in addresses],
    )
    assert asyncio.run(pinned_addresses("https://publisher.example/story")) == [
        "93.184.216.34",
        "2606:4700::1111",
        "1.1.1.1",
    ]


def test_private_dns_and_redirect_targets_are_rejected_before_connection(pinned_transport):
    calls, controls = pinned_transport
    controls["private_dns"] = True
    with pytest.raises(ValueError):
        asyncio.run(public_document("https://publisher.example/story"))
    assert not calls
    controls.update(private_dns=False, redirect=True)

    # Both original and redirect URLs are checked; make the redirect resolve locally.
    def addresses(host, *args, **kwargs):
        return [(2, 1, 6, "", ("127.0.0.1" if host == "127.0.0.1" else "93.184.216.34", 443))]

    from unittest.mock import patch

    with patch("socket.getaddrinfo", addresses), pytest.raises(ValueError):
        asyncio.run(public_document("https://publisher.example/story"))
    assert len(calls) == 1


def test_oversize_images_are_rejected(pinned_transport):
    _, controls = pinned_transport
    controls["oversize"] = True
    with pytest.raises(ValueError, match="image_too_large"):
        asyncio.run(public_document("https://publisher.example/big.png", image=True))


def test_proxy_tls_verifies_original_domain_when_tunnel_target_is_numeric():
    context = OriginTLS("publisher.example")
    connection = context.wrap_bio(ssl.MemoryBIO(), ssl.MemoryBIO(), server_hostname="93.184.216.34")
    assert connection.server_hostname == "publisher.example"
    assert context.check_hostname is True
    assert context.verify_mode == ssl.CERT_REQUIRED
    assert context.context.get_ca_certs()


@pytest.mark.parametrize("dns_error", [False, True])
def test_failed_system_route_uses_public_dns_and_reuses_verified_address(monkeypatch, dns_error):
    calls = []

    def addresses(*args, **kwargs):
        if dns_error:
            raise socket.gaierror("system DNS unavailable")
        return [(2, 1, 6, "", ("8.8.4.4", 443))]

    def handler(request):
        calls.append(request)
        if request.url.host == "dns.google":
            assert dict(request.url.params) in [
                {"name": "publisher.example", "type": "A"},
                {"name": "publisher.example", "type": "AAAA"},
            ]
            return httpx.Response(
                200,
                json={"Status": 0, "Answer": [{"type": 1, "TTL": 120, "data": "93.184.216.34"}]},
            )
        if request.url.host == "8.8.4.4":
            raise httpx.ConnectError("unreachable local DNS result", request=request)
        assert request.url.host == "93.184.216.34"
        assert request.headers["host"] == "publisher.example"
        return httpx.Response(200, headers={"content-type": "image/png"}, content=PNG)

    original = httpx.AsyncClient
    monkeypatch.setattr("socket.getaddrinfo", addresses)
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: original(**kwargs, transport=httpx.MockTransport(handler)),
    )

    async def check():
        assert (await public_document("https://publisher.example/photo.png", image=True))[2] == PNG
        before = len(calls)
        assert (await public_document("https://publisher.example/other.png", image=True))[2] == PNG
        assert len(calls) == before + 1

    asyncio.run(check())
    assert len([r for r in calls if r.url.host == "dns.google"]) == 2
    assert all("cookie" not in r.headers and "authorization" not in r.headers for r in calls)


def test_encrypted_dns_cannot_introduce_a_private_destination(monkeypatch):
    from cfaw_news.media import encrypted_addresses

    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(
            200, json={"Status": 0, "Answer": [{"type": 1, "TTL": 60, "data": "127.0.0.1"}]}
        )

    original = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: original(**kwargs, transport=httpx.MockTransport(handler)),
    )
    with pytest.raises(ValueError, match="non_public_address"):
        asyncio.run(encrypted_addresses("publisher.example"))
    assert all(r.url.host == "dns.google" for r in calls)
    assert not DNS_CACHE


@pytest.mark.parametrize("proxy_denial", [False, True])
def test_http_or_proxy_denial_does_not_trigger_dns_fallback(pinned_transport, proxy_denial):
    calls, controls = pinned_transport
    controls.update(denial=True, proxy_denial=proxy_denial)
    with pytest.raises(httpx.HTTPError):
        asyncio.run(public_document("https://publisher.example/story"))
    assert len(calls) == 1 and calls[0].url.host == "93.184.216.34"
    assert not DNS_CACHE


@pytest.fixture
def reddit_documents(monkeypatch):
    calls = []
    controls = {"text_only": False, "denied": False}

    async def read(url, *, image=False, referer="", json_data=False):
        calls.append((url, image, json_data))
        if json_data:
            assert url.startswith("https://www.reddit.com/oembed?")
            if controls["denied"]:
                response = httpx.Response(403, request=httpx.Request("GET", url))
                response.raise_for_status()
            return (
                url,
                "application/json",
                json.dumps(
                    {"provider_name": "reddit", "html": "<script>never execute</script>"}
                ).encode(),
            )
        if image:
            assert url == "https://preview.redd.it/post.jpg?width=640&crop=smart"
            return url, "image/png", PNG
        assert url.startswith("https://embed.reddit.com/r/")
        markup = '<img src="https://styles.redditmedia.com/communityIcon.png"><img src="https://id.rlcdn.com/472486.gif">'
        if not controls["text_only"]:
            markup += '<img src="https://preview.redd.it/post.jpg?width=640&amp;crop=smart">'
        return url, "text/html", markup.encode()

    async def addresses(url):
        return ["93.184.216.34"]

    monkeypatch.setattr("cfaw_news.media.public_document", read)
    monkeypatch.setattr("cfaw_news.media.pinned_addresses", addresses)
    return calls, controls


def test_reddit_official_embed_recovers_post_image_without_icons_or_scripts(
    media_app, reddit_documents
):
    client, cache, article = media_app
    calls, _ = reddit_documents
    article = {**article, "original_url": "https://www.reddit.com/r/example/comments/abc123/photo/"}
    asyncio.run(cache.process(article))
    shown = cache.decorate([article])[0]
    assert shown["image_status"] == "ready" and shown["image_origin"] == "reddit_embed"
    assert client.get(shown["image_url"]).content == PNG
    assert len(calls) == 3 and calls[0][2] is True
    assert calls[1][0].startswith("https://embed.reddit.com/")
    assert not any("widgets.js" in call[0] for call in calls)
    with cache.database.session() as session:
        assert (
            session.get(Article, article["id"]).data["original_url"]
            == "https://publisher.example/story"
        )


def test_reddit_text_post_clears_old_failure_without_using_community_icon(
    media_app, reddit_documents
):
    _, cache, article = media_app
    calls, controls = reddit_documents
    article = {**article, "original_url": "https://www.reddit.com/r/example/comments/abc123/text/"}
    controls["denied"] = True
    asyncio.run(cache.process(article))
    assert cache.decorate([article])[0]["image_error"] == "http_403"
    controls.update(denied=False, text_only=True)
    asyncio.run(cache.process(article))
    shown = cache.decorate([article])[0]
    assert shown["image_status"] == "no_image" and shown["image_error"] is None
    assert not shown["image_url"]
    assert not any(call[1] for call in calls)


def test_reddit_embed_denial_is_reported_without_trying_raw_or_other_endpoints(
    media_app, reddit_documents
):
    _, cache, article = media_app
    calls, controls = reddit_documents
    controls["denied"] = True
    article = {**article, "original_url": "https://www.reddit.com/r/example/comments/abc123/post/"}
    asyncio.run(cache.process(article))
    assert len(calls) == 1 and cache.decorate([article])[0]["image_error"] == "http_403"
    with cache.database.session() as session:
        data = session.get(ArticleMedia, article["id"]).data
    assert (
        datetime.fromisoformat(data["retry_at"]) - datetime.fromisoformat(data["checked_at"])
    ).total_seconds() >= 3600


@pytest.mark.parametrize(
    "url",
    [
        "https://www.reddit.com.attacker.example/r/x/comments/abc123/post/",
        "https://www.reddit.com/r/example/",
        "https://www.reddit.com/r/x/comments/abc123/post/commentid/",
    ],
)
def test_reddit_adapter_only_accepts_post_links_on_exact_provider_hosts(url):
    assert reddit_post_url(url) is None


def test_old_failure_revision_requeues_once_but_keeps_backoff_for_new_failures(
    media_app, cover_documents
):
    _, cache, article = media_app
    cache.enabled = True
    with cache.database.session.begin() as session:
        session.add(
            ArticleMedia(
                article_id=article["id"],
                data={
                    "status": "unavailable",
                    "page_url": article["original_url"],
                    "feed_image": None,
                    "retry_at": "2099-01-01T00:00:00+00:00",
                    "fetch_revision": MEDIA_REVISION - 1,
                },
            )
        )
    assert cache.decorate([article])[0]["image_status"] == "pending"
    assert cache.queue.qsize() == 1
    cache.decorate([article])
    assert cache.queue.qsize() == 1
    cache.queue.get_nowait()
    cache.pending.clear()
    _, controls = cover_documents
    controls["fail"] = True
    asyncio.run(cache.process(article))
    assert cache.decorate([article])[0]["image_status"] == "unavailable"
    assert cache.queue.empty()
    with cache.database.session() as session:
        data = session.get(ArticleMedia, article["id"]).data
    delay = (
        datetime.fromisoformat(data["retry_at"]) - datetime.fromisoformat(data["checked_at"])
    ).total_seconds()
    assert 0 < delay < 300 and data["error_code"] == "connection_failed"


def test_brand_svg_and_tracking_images_do_not_create_false_cover_failures():
    parser = PageImages()
    parser.feed(
        '<meta property="og:image" content="/img/company-poster-logo.svg"><img src="https://id.rlcdn.com/472486.gif">'
    )
    assert parser.candidates("https://publisher.example/story") == []


def test_mixed_public_reserved_dns_rechecks_public_dns_before_any_connection(monkeypatch):
    def addresses(*args, **kwargs):
        return [(2, 1, 6, "", ("93.184.216.34", 443)), (10, 1, 6, "", ("2001::1", 443))]

    async def clean(host):
        assert host == "publisher.example"
        return ["1.1.1.1"]

    monkeypatch.setattr("socket.getaddrinfo", addresses)
    monkeypatch.setattr("cfaw_news.media.encrypted_addresses", clean)
    assert asyncio.run(pinned_addresses("https://publisher.example/story")) == ["1.1.1.1"]
