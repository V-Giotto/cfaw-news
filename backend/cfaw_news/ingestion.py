import asyncio
import ipaddress
import json
import logging
import socket
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

import feedparser
import httpx
from sqlalchemy import select

from .database import Article, SourceState, fingerprint, utcnow
from .seed import safe_url

logger = logging.getLogger(__name__)


class PlainText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self.hidden += 1

    def handle_endtag(self, tag):
        if tag in {"script", "style"}:
            self.hidden = max(0, self.hidden - 1)

    def handle_data(self, data):
        if not self.hidden and data.strip():
            self.parts.append(data.strip())


def plain_text(value: str, limit=2000):
    parser = PlainText()
    parser.feed(value)
    return " ".join(parser.parts)[:limit]


def catalog(root):
    config = json.loads((root / "data/sources.json").read_text(encoding="utf-8"))
    live_path = root / "data/live_sources.json"
    live = json.loads(live_path.read_text("utf-8"))["sources"] if live_path.exists() else []
    overrides = {source["id"]: source for source in live}
    sources = {source["id"]: source for source in config["sources"]}
    for source_id, value in overrides.items():
        sources[source_id] = {**sources.get(source_id, {}), **value}
    config["sources"] = [
        {**source, "primary": source_id in overrides, "enabled": source_id in overrides}
        for source_id, source in sources.items()
    ]
    return config


def canonical_url(url):
    if not safe_url(url):
        return ""
    parts = urlsplit(url)
    if parts.username or parts.password:
        return ""
    query = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if not key.lower().startswith("utm_") and key.lower() not in {"fbclid", "gclid"}
    ]
    return urlunsplit(
        (parts.scheme.lower(), parts.netloc.lower(), parts.path, urlencode(query), "")
    )


async def validate_feed_url(url: str, allowed_hosts: set[str]):
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or parsed.hostname not in allowed_hosts
        or parsed.username
        or parsed.password
        or parsed.port not in {None, 443}
    ):
        raise ValueError("来源跳转超出允许的 HTTPS 域名")
    addresses = await asyncio.to_thread(
        socket.getaddrinfo, parsed.hostname, 443, type=socket.SOCK_STREAM
    )
    if not addresses or any(not ipaddress.ip_address(row[4][0]).is_global for row in addresses):
        raise ValueError("来源解析到非公网地址，已停止获取")


async def fetch_document(client, url, allowed_hosts, headers=None):
    for _ in range(4):
        await validate_feed_url(url, allowed_hosts)
        async with client.stream("GET", url, headers=headers) as response:
            if response.is_redirect and response.status_code != 304:
                url = urljoin(url, response.headers.get("location", ""))
                continue
            if response.status_code != 304:
                response.raise_for_status()
            validators = {
                key: response.headers[key]
                for key in ("etag", "last-modified")
                if key in response.headers
            }
            if response.status_code == 304:
                return None, validators
            body = bytearray()
            async for chunk in response.aiter_bytes(65536):
                body.extend(chunk)
                if len(body) > 2_000_000:
                    raise ValueError("来源响应超过 2MB 上限")
            return bytes(body), validators
    raise ValueError("来源跳转次数超过上限")


def feed_field(entry, field):
    if field == "none":
        return ""
    if field in {"content:encoded", "content"}:
        return " ".join(part.get("value", "") for part in entry.get("content", []))
    return entry.get("summary", "") if field in {"description", "summary"} else ""


class FeedImages(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.urls = []

    def handle_starttag(self, tag, attrs):
        if tag != "img":
            return
        attrs = dict(attrs)
        if any(
            str(attrs.get(key, "")).isdigit() and int(attrs[key]) <= 4
            for key in ("width", "height")
        ):
            return
        self.urls.extend(attrs.get(key, "") for key in ("data-src", "src"))


def feed_image(entry, base_url):
    """Presentation metadata only: never fetch article pages or infer evidence from images."""
    candidates = []
    for key in ("media_thumbnail", "media_content", "enclosures"):
        for item in entry.get(key, []):
            if item.get("medium", "image") == "image" and item.get("type", "image/").startswith(
                "image/"
            ):
                candidates.append(item.get("url") or item.get("href", ""))
    parser = FeedImages()
    parser.feed(feed_field(entry, "description") + feed_field(entry, "content"))
    candidates.extend(parser.urls)
    for value in candidates:
        if not value:
            continue
        try:
            url = canonical_url(urljoin(base_url, value))
            parts = urlsplit(url)
            host = parts.hostname or ""
        except (TypeError, ValueError):
            continue
        if (
            parts.scheme != "https"
            or not host
            or host in {"localhost", "localhost.localdomain"}
            or host.endswith((".local", ".localhost"))
        ):
            continue
        try:
            if not ipaddress.ip_address(host).is_global:
                continue
        except ValueError:
            pass
        return url
    return None


def article_row(source, url, title, summary, paragraphs, published_at, **extra):
    row = {
        "id": "feed:" + fingerprint(url)[:32],
        "title": title,
        "original_title": title,
        "source": source["label"],
        "source_url": url,
        "published_at": published_at,
        "summary": summary,
        "paragraphs": paragraphs,
        "coverage_note": "来源提供的摘要/片段，可能截断；未抓取网页全文。",
        "source_role": "RSS/公开来源",
        "origin": "feed",
        "source_id": source["id"],
        "category": source.get("category", "other"),
        "language": source.get("language", ""),
        "same_event_as": None,
        **extra,
    }
    row["content_hash"] = fingerprint(row)
    row["captured_at"] = utcnow()
    return row


def parse_hn(source, items):
    rows = []
    for item in items:
        if item.get("type") != "story" or item.get("deleted") or item.get("dead"):
            continue
        title = plain_text(item.get("title", ""), 240)
        if not title or not isinstance(item.get("id"), int):
            continue
        text = plain_text(item.get("text", ""), 4000)
        submitted = item.get("time")
        date = datetime.fromtimestamp(submitted, timezone.utc).isoformat() if submitted else None
        rows.append(
            article_row(
                source,
                f"https://news.ycombinator.com/item?id={item['id']}",
                title,
                text[:2000],
                [{"id": "p1", "text": text, "kind": "community_text"}] if text else [],
                None,
                submitted_at=date,
                original_url=canonical_url(item.get("url", "")),
                source_role="社区提交（不是原报道正文）",
                coverage_note="时间为 HN 提交时间；标题/文本来自社区，外链正文尚未读取。",
            )
        )
    return rows


def parse_source(source: dict, body: bytes) -> list[dict]:
    if source["kind"] == "hn_official":
        return parse_hn(source, json.loads(body))
    if source["kind"] == "hn":
        hits = json.loads(body).get("hits", [])
        items = [
            {
                "id": int(hit["objectID"]),
                "type": "story",
                "title": hit.get("title", ""),
                "url": hit.get("url", ""),
                "time": hit.get("created_at_i"),
                "text": hit.get("story_text") or "",
            }
            for hit in hits[:20]
            if str(hit.get("objectID", "")).isdigit()
        ]
        return parse_hn(source, items)
    parsed = feedparser.parse(body)
    if not parsed.entries:
        raise ValueError("来源未返回可解析的条目")
    rows = []
    for entry in parsed.entries[: min(source.get("max_items", 20), 60)]:
        url = canonical_url(entry.get("link", ""))
        title = plain_text(entry.get("title", ""), 240)
        if not url or not title:
            continue
        summary = plain_text(feed_field(entry, source.get("summary_field", "description")))
        body_field = source.get("body_field", "content:encoded")
        body_text = plain_text(feed_field(entry, body_field), 4000)
        published = entry.get("published_parsed")
        updated = entry["updated_parsed"] if "updated_parsed" in entry else None
        date = datetime(*published[:6], tzinfo=timezone.utc).isoformat() if published else None
        updated_at = datetime(*updated[:6], tzinfo=timezone.utc).isoformat() if updated else None
        rows.append(
            article_row(
                source,
                url,
                title,
                summary,
                [
                    {
                        "id": "p1",
                        "text": body_text,
                        "kind": "rss_description" if body_field == "description" else "rss_body",
                    }
                ]
                if body_text
                else [],
                date,
                updated_at=updated_at,
            )
        )
        # Images decorate the reader; changing one must not invalidate textual evidence.
        rows[-1]["image_url"] = feed_image(entry, url)
    if not rows:
        raise ValueError("来源条目没有有效标题或链接")
    return rows


class NewsIngestor:
    """Single-process polling. No model calls or dependency on goal execution."""

    def __init__(self, database, root):
        self.database = database
        self.config = catalog(root)
        self.sources = {source["id"]: source for source in self.config["sources"]}
        self.allowed = {urlsplit(source["url"]).hostname for source in self.sources.values()}
        self.allowed.update(self.config.get("redirect_hosts", []))
        self.locks = {source_id: asyncio.Lock() for source_id in self.sources}
        self.semaphore = asyncio.Semaphore(3)
        self.task = None

    def state(self, source_id):
        with self.database.session() as session:
            value = session.get(SourceState, source_id)
            return dict(value.data) if value else {"status": "idle"}

    def save_state(self, source_id, data):
        with self.database.session.begin() as session:
            value = session.get(SourceState, source_id)
            if value:
                value.data = data
            else:
                session.add(SourceState(source_id=source_id, data=data))

    def list_sources(self):
        with self.database.session() as session:
            states = {value.source_id: value.data for value in session.scalars(select(SourceState))}
            counts = {}
            for article in session.scalars(select(Article).where(Article.origin == "feed")):
                source_id = article.data.get("source_id")
                counts[source_id] = counts.get(source_id, 0) + 1
        return [
            {
                **source,
                "state": states.get(source_id, {"status": "idle"}),
                "article_count": counts.get(source_id, 0),
            }
            for source_id, source in self.sources.items()
        ]

    async def read(self, client, source, previous):
        if source["kind"] == "hn_official":
            body, _ = await fetch_document(client, source["url"], self.allowed)
            ids = json.loads(body)
            if not isinstance(ids, list) or not ids:
                raise ValueError("HN 未返回条目列表")
            item_ids = [value for value in ids if type(value) is int and value > 0]
            item_ids = list(dict.fromkeys(item_ids))[: source.get("max_items", 20)]
            gate = asyncio.Semaphore(3)

            async def item(value):
                async with gate:
                    data, _ = await fetch_document(
                        client,
                        f"https://hacker-news.firebaseio.com/v0/item/{value}.json",
                        self.allowed,
                    )
                    result = json.loads(data)
                    return result if isinstance(result, dict) else {}

            results = await asyncio.gather(
                *(item(value) for value in item_ids), return_exceptions=True
            )
            for result in results:
                if isinstance(result, BaseException):
                    raise result
            rows = parse_hn(source, results)
            if not rows:
                raise ValueError("HN 未返回有效新闻提交")
            return rows, {}
        # Existing caches need one full fetch to populate the new display metadata.
        validators = (
            previous.get("validators", {}) if previous.get("image_metadata_version") == 1 else {}
        )
        headers = {}
        if validators.get("etag"):
            headers["If-None-Match"] = validators["etag"]
        if validators.get("last-modified"):
            headers["If-Modified-Since"] = validators["last-modified"]
        body, validators = await fetch_document(client, source["url"], self.allowed, headers)
        rows = await asyncio.to_thread(parse_source, source, body) if body is not None else None
        return rows, validators or previous.get("validators", {})

    async def one(self, client, source_id):
        if self.locks[source_id].locked():
            return {
                "source_id": source_id,
                "status": "refreshing",
                "count": 0,
                "message": "该来源正在刷新",
            }
        async with self.locks[source_id], self.semaphore:
            source = self.sources[source_id]
            previous = self.state(source_id)
            self.save_state(
                source_id, {**previous, "status": "refreshing", "last_attempt_at": utcnow()}
            )
            try:
                rows, validators = await asyncio.wait_for(self.read(client, source, previous), 60)
                added = changed = unchanged = 0
                now = utcnow()
                with self.database.session.begin() as session:
                    for row in rows or []:
                        existing = session.get(Article, row["id"])
                        if existing:
                            first_seen = existing.data.get(
                                "first_seen_at", existing.data["captured_at"]
                            )
                            if existing.content_hash == row["content_hash"]:
                                unchanged += 1
                                existing.data = {
                                    **existing.data,
                                    "image_url": row.get("image_url"),
                                    "last_seen_at": now,
                                }
                            else:
                                changed += 1
                                existing.content_hash = row["content_hash"]
                                existing.data = {
                                    **row,
                                    "first_seen_at": first_seen,
                                    "last_seen_at": now,
                                }
                        else:
                            added += 1
                            row.update(first_seen_at=now, last_seen_at=now)
                            session.add(
                                Article(
                                    id=row["id"],
                                    content_hash=row["content_hash"],
                                    origin="feed",
                                    data=row,
                                )
                            )
                count = len(rows) if rows is not None else previous.get("count", 0)
                state = {
                    "status": "ok",
                    "last_attempt_at": now,
                    "last_success_at": now,
                    "next_refresh_at": (
                        datetime.now(timezone.utc)
                        + timedelta(seconds=source.get("interval_seconds", 900))
                    ).isoformat(),
                    "count": count,
                    "new_count": added,
                    "updated_count": changed,
                    "unchanged_count": unchanged if rows is not None else count,
                    "not_modified": rows is None,
                    "validators": validators,
                    "image_metadata_version": 1,
                    "error": None,
                    "error_code": None,
                }
            except (
                ValueError,
                TypeError,
                OSError,
                httpx.HTTPError,
                KeyError,
                OverflowError,
            ) as exc:
                code = (
                    "timeout"
                    if isinstance(exc, (TimeoutError, httpx.TimeoutException))
                    else (
                        f"http_{exc.response.status_code}"
                        if isinstance(exc, httpx.HTTPStatusError)
                        else "unavailable"
                    )
                )
                state = {
                    **previous,
                    "status": "error",
                    "last_attempt_at": utcnow(),
                    "next_refresh_at": (
                        datetime.now(timezone.utc)
                        + timedelta(seconds=source.get("interval_seconds", 900))
                    ).isoformat(),
                    "new_count": 0,
                    "updated_count": 0,
                    "error_code": code,
                    "error": "来源超时、不可用或无法解析；已保留此前资料。",
                }
            self.save_state(source_id, state)
            return {"source_id": source_id, **state}

    async def refresh(self, source_ids):
        async with httpx.AsyncClient(
            timeout=15,
            limits=httpx.Limits(max_connections=6, max_keepalive_connections=6),
            follow_redirects=False,
            trust_env=False,
            headers={"User-Agent": "CFAW-News/0.2 local-reader"},
        ) as client:
            return await asyncio.gather(
                *(self.one(client, value) for value in dict.fromkeys(source_ids))
            )

    async def refresh_due(self):
        now = utcnow()
        due = []
        for source_id, source in self.sources.items():
            if source.get("primary") and self.state(source_id).get("next_refresh_at", "") <= now:
                due.append(source_id)
        return await self.refresh(due) if due else []

    def start(self):
        for source_id, source in self.sources.items():
            state = self.state(source_id)
            if state["status"] == "refreshing":
                self.save_state(
                    source_id,
                    {
                        **state,
                        "status": "error",
                        "next_refresh_at": utcnow(),
                        "error": "上次刷新被中断，等待重新获取。",
                        "error_code": "interrupted",
                    },
                )
            elif source.get("primary") and state.get("image_metadata_version") != 1:
                # Upgrades must populate display metadata immediately, even when
                # an older process scheduled its next fetch far into the future.
                self.save_state(source_id, {**state, "next_refresh_at": utcnow()})
        self.task = asyncio.create_task(self.poll())

    async def poll(self):
        while True:
            try:
                await self.refresh_due()
            except Exception as exc:
                logger.error("News refresh failed (%s)", type(exc).__name__)
            await asyncio.sleep(15)

    async def close(self):
        if self.task:
            self.task.cancel()
            await asyncio.gather(self.task, return_exceptions=True)
