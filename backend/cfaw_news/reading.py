"""Bounded source reading cache, separate from immutable model evidence."""

import asyncio
import hashlib
import ipaddress
import logging
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import quote, urlsplit
from uuid import uuid4

import httpx
import lxml.html
import trafilatura
from lxml.etree import LxmlError

from .article_html import article_markup
from .database import Article, ArticleReading, utcnow
from .media import IMAGE_TYPES, image_extension, public_document, public_url

READING_REVISION = 2
PAGE_READING_REVISION = 1
HTML_LIMIT = 2_000_000
TEXT_LIMIT = 120_000
NODE_LIMIT = 2500
logger = logging.getLogger(__name__)
ALLOWED = {
    "p",
    "div",
    "section",
    "article",
    "main",
    "span",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "a",
    "img",
    "figure",
    "figcaption",
    "blockquote",
    "pre",
    "code",
    "ul",
    "ol",
    "li",
    "strong",
    "b",
    "em",
    "i",
    "br",
    "hr",
    "table",
    "thead",
    "tbody",
    "tr",
    "th",
    "td",
    "sup",
    "sub",
    "dl",
    "dt",
    "dd",
    "s",
    "del",
}
HIDDEN = {
    "script",
    "style",
    "iframe",
    "object",
    "embed",
    "form",
    "input",
    "button",
    "nav",
    "footer",
    "header",
    "aside",
    "svg",
    "canvas",
    "video",
    "audio",
    "link",
    "meta",
    "base",
    "noscript",
    "template",
}


def safe_link(value, base):
    try:
        result = public_url(value, base) if value else ""
        host = urlsplit(result).hostname
        try:
            if host and not ipaddress.ip_address(host).is_global:
                return ""
        except ValueError:
            pass  # Public hostnames are resolved and pinned only when fetching.
        return result
    except (ValueError, TypeError, UnicodeError):
        return ""


def reading_document(markup, url, *, source="rss", truncated=False):
    """Convert HTML to a strict JSON tree. Never send untrusted HTML to React."""
    over_limit = len(markup) > HTML_LIMIT
    parser = lxml.html.HTMLParser(no_network=True, remove_comments=True, recover=True)
    root = lxml.html.fragment_fromstring(
        markup[:HTML_LIMIT] or "<div/>", create_parent="div", parser=parser
    )
    images, texts = [], []
    used = count = 0
    clipped = bool(truncated or over_limit)

    def text_node(text):
        nonlocal used, clipped
        text = (text or "").replace("\x00", "")
        if not text:
            return []
        if used + len(text) > TEXT_LIMIT:
            clipped = True
        text = text[: max(0, TEXT_LIMIT - used)]
        used += len(text)
        if text.strip():
            texts.append(text.strip())
        return [{"tag": "text", "text": text}] if text else []

    def walk(element, depth=0):
        nonlocal count, clipped
        if count >= NODE_LIMIT or depth > 32:
            clipped = True
            return []
        count += 1
        tag = element.tag.lower() if isinstance(element.tag, str) else ""
        if tag in HIDDEN or "hidden" in element.attrib or element.get("aria-hidden") == "true":
            return []
        if re.search(
            r"(?:display\s*:\s*none|visibility\s*:\s*hidden)", element.get("style", ""), re.I
        ):
            return []
        if tag == "img":
            value = (
                element.get("data-src") or element.get("data-original") or element.get("src") or ""
            )
            if not value or value.startswith("data:"):
                srcset = element.get("data-srcset") or element.get("srcset", "")
                value = srcset.split(",")[0].strip().split(" ")[0]
            src = safe_link(value, url)
            if not src or any(
                str(element.get(k, "")).isdigit() and int(element.get(k)) <= 4
                for k in ("width", "height")
            ):
                return []
            path = urlsplit(src).path.lower()
            if path.endswith(".svg") or any(
                word in path for word in ("pixel", "tracker", "avatar", "favicon")
            ):
                return []
            if len(images) >= 40:
                clipped = True
                return []
            if src not in images:
                images.append(src)
            return [{"tag": "img", "image": images.index(src), "alt": element.get("alt", "")[:300]}]
        children = text_node(element.text)
        for child in element:
            children.extend(walk(child, depth + 1))
            children.extend(text_node(child.tail))
        if tag not in ALLOWED:
            return children
        if not children and tag not in {"br", "hr"}:
            return []
        node = {"tag": tag, "children": children}
        if tag == "a":
            href = safe_link(element.get("href", ""), url)
            if href:
                node["href"] = href
            else:
                node["tag"] = "span"
        return [node]

    nodes = walk(root)
    plain = "\n".join(texts)
    return {
        "status": "ready" if plain else "empty",
        "source": source,
        "origin_url": url,
        "nodes": nodes,
        "images": images,
        "text_chars": len(plain),
        "truncated": clipped,
        "fetched_at": utcnow(),
        "revision": READING_REVISION,
        "text_hash": hashlib.sha256(plain.encode()).hexdigest(),
    }


def extract_page(markup, url):
    original_size = len(markup)
    html = article_markup(markup[:HTML_LIMIT], url)
    if html is None:
        # Readability libraries can discard data-* attributes before resolving lazy
        # images. Normalize these first so a transparent placeholder isn't cached.
        parser = lxml.html.HTMLParser(no_network=True, remove_comments=True, recover=True)
        tree = lxml.html.fromstring(markup[:HTML_LIMIT], parser=parser)
        for image in tree.iter("img"):
            candidate = next(
                (
                    image.get(key)
                    for key in ("data-original", "data-src", "data-actualsrc", "data-lazy-src", "src")
                    if image.get(key) and not image.get(key).startswith("data:")
                ),
                "",
            )
            source = safe_link(candidate, url)
            if source:
                image.set("src", source)
        normalized = lxml.html.tostring(tree, encoding="unicode")
        html = trafilatura.extract(
            normalized,
            url=url,
            output_format="html",
            include_comments=False,
            include_images=True,
            include_links=True,
            include_tables=True,
            include_formatting=True,
            favor_precision=True,
        )
    if not html:
        raise ValueError("no_readable_content")
    data = reading_document(html, url, source="web", truncated=original_size >= HTML_LIMIT)
    data["page_revision"] = PAGE_READING_REVISION
    if data["text_chars"] < 120:
        raise ValueError("no_readable_content")
    return data


class ReadingCache:
    def __init__(self, database, media, *, enabled=True):
        self.database, self.media, self.enabled = database, media, enabled
        self.queue = asyncio.Queue(maxsize=32)
        self.pending = set()
        self.tasks = []
        self.asset_locks = {}
        self.host_locks = {}
        self.image_gate = asyncio.Semaphore(4)

    def get(self, article):
        with self.database.session() as session:
            record = session.get(ArticleReading, article["id"])
            data = dict(record.data) if record else {}
        fresh = (
            data.get("revision") == READING_REVISION
            and data.get("evidence_hash") == article["content_hash"]
            and (data.get("source") != "web" or data.get("page_revision") == PAGE_READING_REVISION)
        )
        if fresh and (data.get("status") == "ready" or data.get("retry_at", "") > utcnow()):
            return self.present(article["id"], data)
        if self.enabled and article.get("origin") == "feed":
            if article["id"] not in self.pending and not self.queue.full():
                self.pending.add(article["id"])
                self.queue.put_nowait(dict(article))
            return {"status": "fetching", "nodes": [], "source": "web", "text_chars": 0}
        return {
            "status": "unavailable",
            "nodes": [],
            "error": "原文读取未开启，可打开原始来源。",
            "text_chars": 0,
        }

    def present(self, article_id, data):
        result = {
            k: v
            for k, v in data.items()
            if k not in {"images", "assets", "evidence_hash", "text_hash"}
        }
        result["image_count"] = len(data.get("images", []))
        result["image_base"] = f"/api/articles/{quote(article_id, safe='')}/reading/images/"
        return result

    async def process(self, article):
        url = article.get("original_url") or article.get("source_url", "")
        gate = self.host_locks.setdefault(urlsplit(url).hostname, asyncio.Semaphore(2))
        try:
            async with gate:
                final, kind, body = await asyncio.wait_for(
                    public_document(url, max_bytes=HTML_LIMIT), 35
                )
                if not body:
                    raise ValueError("unsupported_document")
                markup = httpx.Response(200, content=body, headers={"content-type": kind}).text
                data = await asyncio.to_thread(extract_page, markup, final)
        except (ValueError, OSError, httpx.HTTPError, UnicodeError, LxmlError) as exc:
            code = (
                f"http_{exc.response.status_code}"
                if isinstance(exc, httpx.HTTPStatusError)
                else "unavailable"
            )
            data = {
                "status": "unavailable",
                "nodes": [],
                "text_chars": 0,
                "source": "web",
                "revision": READING_REVISION,
                "error_code": code,
                "error": "暂时未能读取原文，已保留来源片段与原始链接。",
                "retry_at": (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat(),
            }
        data["evidence_hash"] = article["content_hash"]
        data["page_revision"] = PAGE_READING_REVISION
        with self.database.session.begin() as session:
            current = session.get(Article, article["id"])
            if not current or current.content_hash != article["content_hash"]:
                return
            record = session.get(ArticleReading, article["id"])
            # A feed refresh may have supplied a complete reading while this job ran.
            if (
                record
                and record.data.get("source") == "rss"
                and record.data.get("status") == "ready"
                and record.data.get("evidence_hash") == current.content_hash
            ):
                return
            if record:
                record.data = data
            else:
                session.add(ArticleReading(article_id=article["id"], data=data))

    async def image(self, article_id, index):
        key = (article_id, index)
        async with self.asset_locks.setdefault(key, asyncio.Lock()):
            with self.database.session() as session:
                record = session.get(ArticleReading, article_id)
                data = dict(record.data) if record else {}
            urls = data.get("images", [])
            if not 0 <= index < min(40, len(urls)):
                raise ValueError("unknown_image")
            url = urls[index]
            previous = data.get("assets", {}).get(str(index), {})
            file = self.media.image_file(previous)
            if file:
                return file, previous["content_type"]
            if not self.media.enabled:
                raise ValueError("image_fetch_disabled")
            if previous.get("retry_at", "") > utcnow():
                raise ValueError("image_temporarily_unavailable")
            try:
                host_gate = self.host_locks.setdefault(urlsplit(url).hostname, asyncio.Semaphore(2))
                async with self.image_gate, host_gate:
                    _, _, body = await asyncio.wait_for(
                        public_document(url, image=True, referer=data["origin_url"]), 18
                    )
                extension = image_extension(body)
                filename = hashlib.sha256(body).hexdigest() + "." + extension
                self.media.root.mkdir(parents=True, exist_ok=True)
                file = self.media.root / filename
                if not file.exists():
                    temp = self.media.root / (uuid4().hex + ".tmp")
                    try:
                        temp.write_bytes(body)
                        temp.replace(file)
                    finally:
                        temp.unlink(missing_ok=True)
                asset = {"filename": filename, "content_type": IMAGE_TYPES[extension]}
            except (ValueError, OSError, httpx.HTTPError) as exc:
                asset = {
                    "retry_at": (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat()
                }
                self.save_asset(article_id, index, url, asset)
                raise ValueError("image_temporarily_unavailable") from exc
            self.save_asset(article_id, index, url, asset)
            return file, asset["content_type"]

    def save_asset(self, article_id, index, url, asset):
        with self.database.session.begin() as session:
            record = session.get(ArticleReading, article_id)
            if (
                record
                and index < len(record.data.get("images", []))
                and record.data["images"][index] == url
            ):
                record.data = {
                    **record.data,
                    "assets": {**record.data.get("assets", {}), str(index): asset},
                }

    async def worker(self):
        while True:
            article = await self.queue.get()
            try:
                await self.process(article)
            except Exception as exc:
                # One malformed publisher document must not stop the worker pool.
                # Log the class only: remote responses can contain private URLs.
                logger.warning("Reading job failed: %s", type(exc).__name__)
            finally:
                self.pending.discard(article["id"])
                self.queue.task_done()

    def start(self):
        if self.enabled:
            self.tasks = [asyncio.create_task(self.worker()) for _ in range(2)]

    async def close(self):
        for task in self.tasks:
            task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)
