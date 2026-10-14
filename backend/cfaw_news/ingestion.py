import asyncio
import ipaddress
import json
import socket
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

import feedparser
import httpx

from .database import Article, fingerprint, utcnow
from .seed import safe_url


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
    return json.loads((root / "data/sources.json").read_text(encoding="utf-8"))


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


async def fetch_bytes(client, url: str, allowed_hosts: set[str]):
    for _ in range(4):
        await validate_feed_url(url, allowed_hosts)
        async with client.stream("GET", url) as response:
            if response.is_redirect:
                url = urljoin(url, response.headers.get("location", ""))
                continue
            response.raise_for_status()
            body = bytearray()
            async for chunk in response.aiter_bytes(65536):
                body.extend(chunk)
                if len(body) > 2_000_000:
                    raise ValueError("来源响应超过 2MB 上限")
            return bytes(body)
    raise ValueError("来源跳转次数超过上限")


def parse_source(source: dict, body: bytes) -> list[dict]:
    rows = []
    if source["kind"] == "hn":
        entries = [
            {
                "title": hit.get("title", ""),
                "link": hit.get("url", ""),
                "summary": "",
                "content": [],
                "published_parsed": None,
            }
            for hit in json.loads(body).get("hits", [])
        ]
    else:
        parsed = feedparser.parse(body)
        if not parsed.entries:
            raise ValueError("来源未返回可解析的条目")
        entries = parsed.entries
    for entry in entries[:20]:
        url = safe_url(entry.get("link", ""))
        title = plain_text(entry.get("title", ""), 240)
        if not url or not title:
            continue
        article_id = "feed:" + fingerprint(url.split("#")[0])[:32]
        summary = plain_text(entry.get("summary", ""))
        body_text = plain_text(
            " ".join(part.get("value", "") for part in entry.get("content", [])), 4000
        )
        published = entry.get("published_parsed") or entry.get("updated_parsed")
        date = datetime(*published[:6], tzinfo=timezone.utc).isoformat() if published else None
        row = {
            "id": article_id,
            "title": title,
            "original_title": title,
            "source": source["label"],
            "source_url": url,
            "published_at": date,
            "summary": summary,
            "paragraphs": [{"id": "p1", "text": body_text, "kind": "rss_body"}]
            if body_text
            else [],
            "coverage_note": "实时来源条目；未抓取网页全文，正文只来自 RSS 已提供内容。",
            "source_role": "RSS/公开来源",
            "origin": "feed",
            "source_id": source["id"],
            "same_event_as": None,
        }
        row["content_hash"] = fingerprint(row)
        row["captured_at"] = utcnow()
        rows.append(row)
    return rows


async def refresh(database, root, source_ids):
    config = catalog(root)
    sources = {source["id"]: source for source in config["sources"]}
    allowed = {urlsplit(source["url"]).hostname for source in sources.values()}
    allowed.update(config.get("redirect_hosts", []))
    limits = httpx.Limits(max_connections=3, max_keepalive_connections=3)
    async with httpx.AsyncClient(
        timeout=15,
        limits=limits,
        follow_redirects=False,
        trust_env=False,
        headers={"User-Agent": "CFAW-News/0.2 local-reader"},
    ) as client:

        async def one(source_id):
            try:
                source = sources[source_id]
                body = await fetch_bytes(client, source["url"], allowed)
                rows = await asyncio.to_thread(parse_source, source, body)
                with database.session.begin() as session:
                    for row in rows:
                        existing = session.get(Article, row["id"])
                        if existing:
                            existing.content_hash = row["content_hash"]
                            existing.data = row
                        else:
                            session.add(
                                Article(
                                    id=row["id"],
                                    content_hash=row["content_hash"],
                                    origin="feed",
                                    data=row,
                                )
                            )
                return {"source_id": source_id, "status": "ok", "count": len(rows)}
            except (ValueError, OSError, httpx.HTTPError, KeyError):
                return {
                    "source_id": source_id,
                    "status": "error",
                    "count": 0,
                    "message": "来源不可用、超时或响应无法解析；已保留原有资料。",
                }

        return await asyncio.gather(*(one(source_id) for source_id in dict.fromkeys(source_ids)))
