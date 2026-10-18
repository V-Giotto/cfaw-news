"""Bounded, display-only cover discovery. Nothing here becomes textual evidence."""

import asyncio
import hashlib
import ipaddress
import json
import re
import socket
import warnings
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from io import BytesIO
from itertools import zip_longest
from pathlib import Path
from time import monotonic
from urllib.parse import quote, urlencode, urljoin, urlsplit, urlunsplit
from uuid import uuid4

import httpx
from PIL import Image
from sqlalchemy import select

from .article_html import article_markup
from .database import ArticleMedia, utcnow

IMAGE_TYPES = {"jpg": "image/jpeg", "png": "image/png", "webp": "image/webp", "gif": "image/gif"}
DNS_CACHE = {}
MEDIA_REVISION = 4


class OriginTLS:
    """Keep hostname verification when a proxy tunnels to a checked numeric IP.

    httpcore's HTTP CONNECT path does not honor the sni_hostname extension.
    Delegate TLS configuration to HTTPX, including the configured trust store,
    and bind both SNI and certificate matching to the original publisher host.
    Each client has its own context; the proxy's own TLS context is separate.
    """

    def __init__(self, hostname):
        self.hostname = hostname
        self.context = httpx.create_ssl_context()

    def __getattr__(self, name):
        return getattr(self.context, name)

    def wrap_bio(self, incoming, outgoing, server_side=False, server_hostname=None, session=None):
        return self.context.wrap_bio(
            incoming,
            outgoing,
            server_side=server_side,
            server_hostname=self.hostname,
            session=session,
        )


def public_url(value, base=""):
    parts = urlsplit(urljoin(base, value))
    host = (parts.hostname or "").rstrip(".").lower()
    if (
        parts.scheme not in {"http", "https"}
        or not host
        or parts.username
        or parts.password
        or parts.port not in {None, 80, 443}
        or host == "localhost"
        or host.endswith((".localhost", ".local", ".internal"))
        or len(value) > 4096
    ):
        raise ValueError("not_public_https")
    host = host.encode("idna").decode()
    authority = f"[{host}]" if ":" in host else host
    # Try HTTPS for old HTTP links; never downgrade or connect to an HTTP service.
    return urlunsplit(("https", authority, parts.path or "/", parts.query, ""))


def checked_addresses(addresses):
    addresses = list(dict.fromkeys(addresses))
    if not addresses or any(not ipaddress.ip_address(value).is_global for value in addresses):
        raise ValueError("non_public_address")
    ipv4 = [value for value in addresses if ":" not in value]
    ipv6 = [value for value in addresses if ":" in value]
    # Keep both families in the bounded attempt list, even for CDN hosts with
    # many IPv6 records on networks where only IPv4 is reachable.
    return [value for pair in zip_longest(ipv4, ipv6) for value in pair if value][:3]


async def pinned_addresses(url):
    host = urlsplit(url).hostname
    cached = DNS_CACHE.get(host)
    if cached and cached[0] > monotonic():
        return checked_addresses(cached[1])
    records = await asyncio.to_thread(socket.getaddrinfo, host, 443, type=socket.SOCK_STREAM)
    addresses = [record[4][0] for record in records]
    try:
        return checked_addresses(addresses)
    except ValueError:
        # A mixed public/reserved answer can be poisoned DNS. Obtain a fresh
        # public answer instead of silently dropping records or using private
        # ones. Purely private destinations remain rejected without fallback.
        if not any(ipaddress.ip_address(value).is_global for value in addresses):
            raise
        return await encrypted_addresses(host)


async def encrypted_addresses(host):
    """Only public hostnames, never article paths or personal application data."""
    async with httpx.AsyncClient(timeout=4, follow_redirects=False) as client:

        async def lookup(kind):
            response = await client.get(
                "https://dns.google/resolve",
                params={"name": host, "type": kind},
                headers={"Accept": "application/dns-json"},
            )
            response.raise_for_status()
            result = response.json()
            if not isinstance(result, dict) or result.get("Status") != 0:
                return []
            return result.get("Answer", [])

        results = await asyncio.gather(lookup("A"), lookup("AAAA"), return_exceptions=True)
    answers = [
        answer
        for result in results
        if isinstance(result, list)
        for answer in result
        if isinstance(answer, dict) and answer.get("type") in {1, 28}
    ]
    addresses = checked_addresses(answer["data"] for answer in answers)
    ttl = min([max(0, int(answer.get("TTL", 60))) for answer in answers] + [300])
    if len(DNS_CACHE) >= 128:
        DNS_CACHE.pop(next(iter(DNS_CACHE)))
    DNS_CACHE[host] = (monotonic() + ttl, addresses)
    return addresses


async def connection_addresses(url):
    try:
        local = await pinned_addresses(url)
    except socket.gaierror:
        local = []
    for address in local:
        yield address
    # This generator reaches the external resolver only after every local
    # address failed to connect. A HTTP denial or invalid public target stops
    # the caller before this fallback; neither is retried through another route.
    for address in await encrypted_addresses(urlsplit(url).hostname):
        if address not in local:
            yield address


async def public_document(url, *, image=False, referer="", json_data=False, max_bytes=None):
    """Pin each connection to a checked IP; retain the original TLS name and Host."""
    url = public_url(url)
    for _ in range(4):
        host = urlsplit(url).hostname
        headers = {
            "Host": host,
            "User-Agent": "CFAW-News/0.2 cover-reader",
            "Accept": "image/*"
            if image
            else "application/json"
            if json_data
            else "text/html,application/xhtml+xml",
        }
        if referer:
            page = urlsplit(public_url(referer))
            headers["Referer"] = f"{page.scheme}://{page.netloc}/"
        limit = max_bytes or (4_000_000 if image else 524_288)
        redirected = False
        last_error = None
        async for address in connection_addresses(url):
            target = httpx.URL(url).copy_with(host=address)
            # Fresh clients isolate cookies and TLS sessions of virtual hosts.
            try:
                async with httpx.AsyncClient(
                    timeout=httpx.Timeout(7, connect=3),
                    follow_redirects=False,
                    verify=OriginTLS(host),
                    trust_env=True,
                ) as client:
                    async with client.stream(
                        "GET", target, headers=headers, extensions={"sni_hostname": host}
                    ) as response:
                        if response.is_redirect:
                            url = public_url(response.headers.get("location", ""), url)
                            redirected = True
                            break
                        response.raise_for_status()
                        content_type = response.headers.get("content-type", "")
                        kind = content_type.split(";")[0].strip().lower()
                        if image and not kind.startswith("image/"):
                            raise ValueError("not_an_image")
                        if json_data and kind != "application/json":
                            raise ValueError("not_json")
                        if (
                            not image
                            and not json_data
                            and kind not in {"text/html", "application/xhtml+xml"}
                        ):
                            return url, content_type, b""
                        body = bytearray()
                        async for chunk in response.aiter_bytes(32768):
                            body.extend(chunk)
                            if len(body) > limit:
                                if image:
                                    raise ValueError("image_too_large")
                                del body[limit:]
                                break
                        return url, content_type, bytes(body)
            except httpx.ProxyError:
                raise
            except httpx.TransportError as exc:
                last_error = exc
        if redirected:
            continue
        if last_error:
            raise last_error
    raise ValueError("too_many_redirects")


def reddit_post_url(value):
    parts = urlsplit(public_url(value))
    if parts.hostname not in {"reddit.com", "www.reddit.com", "old.reddit.com"} or not re.fullmatch(
        r"/r/[A-Za-z0-9_]+/comments/[A-Za-z0-9]+(?:/[^/]+)?/?", parts.path
    ):
        return None
    return urlunsplit(("https", "www.reddit.com", parts.path, "", ""))


async def reddit_images(post):
    """Use Reddit's public embed service; never execute its returned scripts.

    The frame URL follows the post path, as documented by the oEmbed widget.
    Only Reddit post-media CDNs are candidates; community icons, avatars,
    marketing artwork and tracking pixels are not article photographs.
    """
    endpoint = "https://www.reddit.com/oembed?" + urlencode({"url": post, "format": "json"})
    _, _, body = await public_document(endpoint, json_data=True)
    metadata = json.loads(body)
    if not isinstance(metadata, dict) or str(metadata.get("provider_name", "")).lower() != "reddit":
        raise ValueError("invalid_reddit_embed")
    embed = "https://embed.reddit.com" + urlsplit(post).path
    try:
        await pinned_addresses(embed)
    except (ValueError, socket.gaierror):
        # This is a fixed official service, not an arbitrary private URL.
        # Some proxy DNS configurations return local synthetic IP addresses.
        # Resolve the service through public DNS and still pin only public IPs.
        await encrypted_addresses("embed.reddit.com")
    final, content_type, body = await public_document(embed)
    parser = PageImages()
    parser.feed(httpx.Response(200, headers={"content-type": content_type}, content=body).text)
    values = [metadata.get("thumbnail_url", "")] + parser.meta + parser.content + parser.other
    result = []
    for value in values:
        try:
            url = public_url(value, final) if value else ""
        except (ValueError, TypeError, UnicodeError):
            continue
        if urlsplit(url).hostname in {"i.redd.it", "preview.redd.it"} and url not in result:
            result.append(url)
    return result[:4], embed


class PageImages(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.meta = []
        self.content = []
        self.other = []
        self.article_depth = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in {"article", "main"}:
            self.article_depth += 1
        if tag == "meta":
            name = (attrs.get("property") or attrs.get("name") or "").lower()
            if name in {
                "og:image",
                "og:image:url",
                "og:image:secure_url",
                "twitter:image",
                "twitter:image:src",
            }:
                self.meta.append(attrs.get("content", ""))
        if tag == "link" and "image_src" in (attrs.get("rel") or "").lower().split():
            self.meta.append(attrs.get("href", ""))
        if tag != "img":
            return
        if any(
            str(attrs.get(key, "")).isdigit() and int(attrs[key]) < 120
            for key in ("width", "height")
        ):
            return
        values = self.content if self.article_depth else self.other
        for key in ("data-src", "src"):
            value = attrs.get(key) or ""
            path = value.lower().split("?")[0]
            if value and not any(
                word in path for word in ("logo", "avatar", "favicon", "badge", "pixel", "toparr", ".svg")
            ):
                values.append(value)

    def handle_endtag(self, tag):
        if tag in {"article", "main"}:
            self.article_depth = max(0, self.article_depth - 1)

    def candidates(self, base):
        urls = []
        for value in self.meta + self.content + self.other:
            if not value:
                continue
            try:
                url = public_url(value, base)
            except (ValueError, TypeError, UnicodeError):
                continue
            parts = urlsplit(url)
            if (
                parts.path.lower().endswith(".svg")
                or any(
                    word in parts.path.lower()
                    for word in ("logo", "avatar", "favicon", "badge", "pixel", "toparr")
                )
                or parts.hostname == "id.rlcdn.com"
            ):
                continue
            if url not in urls:
                urls.append(url)
        return urls[:4]


def image_extension(body):
    if body.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if body.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if body.startswith((b"GIF87a", b"GIF89a")):
        return "gif"
    if body.startswith(b"RIFF") and body[8:12] == b"WEBP":
        return "webp"
    raise ValueError("unsupported_image")


def cover_dimensions(body):
    """Inspect raster headers and structure; never upscale tiny interface assets."""
    image_extension(body)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(body), formats=["JPEG", "PNG", "GIF", "WEBP"]) as picture:
                width, height = picture.size
                if width * height > 40_000_000 or max(width, height) > 20_000:
                    raise ValueError("image_too_large")
                if min(width, height) < 120:
                    raise ValueError("image_too_small")
                picture.verify()
                return width, height
    except (Image.DecompressionBombWarning, Image.DecompressionBombError) as exc:
        raise ValueError("image_too_large") from exc
    except SyntaxError as exc:
        raise ValueError("unsupported_image") from exc


class MediaCache:
    def __init__(self, database, root, *, enabled=True):
        self.database = database
        self.root = Path(root).resolve()
        self.enabled = enabled
        self.queue = asyncio.Queue(maxsize=160)
        self.pending = set()
        self.tasks = []
        self.host_locks = {}
        self.checked_files = {}

    def image_file(self, data):
        filename = data.get("filename", "")
        stem, _, extension = filename.partition(".")
        if (
            len(stem) != 64
            or any(c not in "0123456789abcdef" for c in stem)
            or extension not in IMAGE_TYPES
        ):
            return None
        path = (self.root / filename).resolve()
        return path if path.is_relative_to(self.root) and path.is_file() else None

    def cover_file(self, data):
        path = self.image_file(data)
        if not path:
            return None
        try:
            stat = path.stat()
            key = (path.name, stat.st_size, stat.st_mtime_ns)
            if key not in self.checked_files:
                if len(self.checked_files) >= 512:
                    self.checked_files.pop(next(iter(self.checked_files)))
                try:
                    if stat.st_size > 4_000_000:
                        raise ValueError("image_too_large")
                    cover_dimensions(path.read_bytes())
                    valid = True
                except (ValueError, OSError):
                    valid = False
                self.checked_files[key] = valid
            return path if self.checked_files[key] else None
        except OSError:
            return None

    def decorate(self, articles):
        if not articles:
            return []
        with self.database.session() as session:
            entries = {
                m.article_id: m.data
                for m in session.scalars(
                    select(ArticleMedia).where(
                        ArticleMedia.article_id.in_([a["id"] for a in articles])
                    )
                )
            }
        result = []
        for article in articles:
            data = entries.get(article["id"], {})
            file = self.cover_file(data)
            page = article.get("original_url") or article.get("source_url", "")
            if self.enabled and article.get("origin") == "feed" and page:
                fresh = (
                    data.get("page_url") == page
                    and data.get("feed_image") == article.get("image_url")
                    and data.get("retry_at", "") > utcnow()
                    and data.get("fetch_revision") == MEDIA_REVISION
                )
                if (
                    (not fresh or (data.get("status") == "ready" and not file))
                    and article["id"] not in self.pending
                    and not self.queue.full()
                ):
                    self.pending.add(article["id"])
                    self.queue.put_nowait(dict(article))
            status = (
                "ready"
                if file
                else "pending"
                if article["id"] in self.pending
                else "unavailable" if data.get("status") == "ready"
                else data.get("status", "no_image")
            )
            result.append(
                {
                    **article,
                    "image_url": f"/api/articles/{quote(article['id'], safe='')}/image?v={data['filename'][:16]}"
                    if file
                    else article.get("image_url"),
                    "image_status": status,
                    "image_origin": data.get("origin"),
                    "image_error": (data.get("error_code") or "invalid_cached_image") if status == "unavailable" else None,
                }
            )
        return result

    async def discover(self, article):
        page_url = article.get("original_url") or article.get("source_url", "")
        candidates = []
        if article.get("image_url"):
            candidates.append((article["image_url"], "feed"))

        async def download(url, origin, page):
            final, _, body = await public_document(url, image=True, referer=page)
            extension = image_extension(body)
            width, height = cover_dimensions(body)
            self.root.mkdir(parents=True, exist_ok=True)
            filename = hashlib.sha256(body).hexdigest() + "." + extension
            path = self.root / filename
            if not path.exists():
                temp = self.root / (uuid4().hex + ".tmp")
                try:
                    temp.write_bytes(body)
                    temp.replace(path)
                finally:
                    temp.unlink(missing_ok=True)
            return {
                "filename": filename,
                "content_type": IMAGE_TYPES[extension],
                "origin": origin,
                "source_image_url": final,
                "width": width, "height": height,
            }

        for url, origin in candidates:
            try:
                return await download(url, origin, page_url)
            except (ValueError, OSError, httpx.HTTPError):
                pass
        post = reddit_post_url(page_url)
        if post:
            urls, final_page = await reddit_images(post)
            origin = "reddit_embed"
        else:
            final_page, content_type, body = await public_document(page_url)
            if not body:
                return None
            markup = httpx.Response(200, headers={"content-type": content_type}, content=body).text
            scoped = article_markup(markup, final_page)
            if scoped is not None:
                markup = scoped
            if not markup:
                raise ValueError("article_body_missing")
            parser = PageImages()
            parser.feed(markup)
            urls = parser.candidates(final_page)
            origin = "page_metadata"
        error = None
        for url in urls:
            try:
                return {**await download(url, origin, final_page), "discovery_url": final_page}
            except (ValueError, OSError, httpx.HTTPError) as exc:
                error = exc
        if error:
            raise error
        return None

    async def process(self, article):
        page = article.get("original_url") or article.get("source_url", "")
        host = urlsplit(page).hostname or ""
        gate = self.host_locks.setdefault(host, asyncio.Semaphore(2))
        try:
            async with gate:
                result = await asyncio.wait_for(self.discover(article), 30)
            data = {
                **(result or {}),
                "status": "ready" if result else "no_image",
                "error_code": None,
            }
        except (ValueError, OSError, httpx.HTTPError, UnicodeError) as exc:
            reason = (
                f"http_{exc.response.status_code}"
                if isinstance(exc, httpx.HTTPStatusError)
                else "timeout"
                if isinstance(exc, (TimeoutError, httpx.TimeoutException))
                else "dns_lookup_failed"
                if isinstance(exc, socket.gaierror)
                else "connection_failed"
                if isinstance(exc, httpx.TransportError)
                else "dns_non_public"
                if isinstance(exc, ValueError) and str(exc) == "non_public_address"
                else "unsupported_image"
                if isinstance(exc, ValueError) and str(exc) == "unsupported_image"
                else "image_fetch_failed"
            )
            data = {"status": "unavailable", "error_code": reason}
        with self.database.session.begin() as session:
            entry = session.get(ArticleMedia, article["id"])
            attempts = (
                (entry.data.get("attempts", 0) if entry else 0) + 1
                if data["status"] == "unavailable"
                else 0
            )
            code = data.get("error_code")
            delay = (
                86400
                if data["status"] == "ready" or code in {"http_401", "http_403"}
                else 21600
                if data["status"] == "no_image" or code in {"http_404", "http_410", "unsupported_image"}
                else 300
                if code == "http_429"
                else min(1800, 60 * 2 ** min(max(0, attempts - 1), 5))
            )
            data.update(
                page_url=page,
                feed_image=article.get("image_url"),
                checked_at=utcnow(),
                retry_at=(datetime.now(timezone.utc) + timedelta(seconds=delay)).isoformat(),
                fetch_revision=MEDIA_REVISION,
                attempts=attempts,
            )
            if entry:
                if (
                    data["status"] == "unavailable"
                    and entry.data.get("page_url") == page
                    and entry.data.get("feed_image") == article.get("image_url")
                    and self.cover_file(entry.data)
                ):
                    data = {**entry.data, **data}
                entry.data = data
            else:
                session.add(ArticleMedia(article_id=article["id"], data=data))

    async def worker(self):
        while True:
            article = await self.queue.get()
            try:
                await self.process(article)
            finally:
                self.pending.discard(article["id"])
                self.queue.task_done()

    def start(self):
        if self.enabled:
            self.tasks = [asyncio.create_task(self.worker()) for _ in range(4)]

    async def close(self):
        for task in self.tasks:
            task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)
