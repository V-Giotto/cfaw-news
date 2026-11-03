"""Scoped local HTTP guard, available even without the optional native runtime wheel."""

import asyncio
import ipaddress
import json
import threading
from typing import Literal
from urllib.parse import parse_qsl, urlsplit

from pydantic import BaseModel, ConfigDict
from starlette.responses import JSONResponse, Response


class BoundaryError(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    schema_revision: Literal["g4-pr4-error-v1"] = "g4-pr4-error-v1"
    code: str
    database_state: Literal["unchanged", "committed", "unknown"] = "unchanged"


class DisabledStatus(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    schema_revision: Literal["g4-pr4-disabled-v1"] = "g4-pr4-disabled-v1"
    enabled: Literal[False] = False
    state: Literal["disabled"] = "disabled"
    scope: Literal["local_single_user_no_multiuser_auth"] = "local_single_user_no_multiuser_auth"


def error_response(code, status, database_state="unchanged"):
    return JSONResponse(BoundaryError(code=code, database_state=database_state).model_dump(), status_code=status)


class IntelligenceBoundary:
    def __init__(self, app, *, origins, max_body=65536, max_requests=4):
        self.app, self.origins = app, set(origins)
        self.max_body, self.max_requests = max_body, max_requests
        self.active, self.lock = 0, threading.Lock()

    async def __call__(self, scope, receive, send):
        path = scope.get("path", "")
        if scope["type"] != "http" or not (path == "/api/intelligence" or path.startswith("/api/intelligence/")):
            return await self.app(scope, receive, send)
        if len(path) > 2048:
            return await error_response("G4_REQUEST_TOO_LARGE", 413)(scope, receive, send)
        try:
            address = ipaddress.ip_address(scope.get("client", (None,))[0])
            address = getattr(address, "ipv4_mapped", None) or address
            if not address.is_loopback:
                raise ValueError
        except (ValueError, TypeError, IndexError):
            return await error_response("G4_LOCAL_CLIENT_REQUIRED", 403)(scope, receive, send)
        headers = {}
        for name, value in scope["headers"]:
            key = name.lower()
            if key in headers and key in {b"host", b"origin", b"content-length", b"content-type"}:
                return await error_response("G4_DUPLICATE_HEADER", 400)(scope, receive, send)
            headers[key] = value.decode("latin1")
        try:
            host = headers.get(b"host", "")
            parsed = urlsplit("http://" + host)
            if (len(host) > 256 or parsed.hostname not in {"localhost", "127.0.0.1", "::1"}
                    or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment):
                raise ValueError
            parsed.port  # Reject malformed/out-of-range ports.
        except ValueError:
            return await error_response("G4_HOST_FORBIDDEN", 400)(scope, receive, send)
        method = scope["method"]
        origin = headers.get(b"origin")
        if (origin is not None and origin not in self.origins) or method == "POST" and origin is None:
            return await error_response("G4_ORIGIN_FORBIDDEN", 403)(scope, receive, send)
        original_send = send
        async def scoped_send(message):
            if message["type"] == "http.response.start" and origin is not None:
                response_headers = [(k, v) for k, v in message.get("headers", [])
                                    if k.lower() not in {b"access-control-allow-origin", b"access-control-expose-headers"}]
                response_headers += [(b"access-control-allow-origin", origin.encode("latin1")),
                                     (b"access-control-expose-headers", b"ETag"), (b"vary", b"Origin")]
                message = {**message, "headers": response_headers}
            await original_send(message)
        send = scoped_send
        if method not in {"GET", "HEAD", "POST", "OPTIONS"}:
            return await error_response("G4_METHOD_NOT_ALLOWED", 405)(scope, receive, send)
        if method == "OPTIONS":
            requested = {h.strip().lower() for h in headers.get(b"access-control-request-headers", "").split(",") if h.strip()}
            if (origin is None or headers.get(b"access-control-request-method") not in {"GET", "HEAD", "POST"}
                    or requested - {"content-type", "if-none-match"}):
                return await error_response("G4_PREFLIGHT_FORBIDDEN", 400)(scope, receive, send)
            return await Response(status_code=204, headers={"Access-Control-Allow-Methods": "GET, HEAD, POST",
                "Access-Control-Allow-Headers": "Content-Type, If-None-Match"})(scope, receive, send)
        raw_query = scope.get("query_string", b"")
        if len(raw_query) > 4096:
            return await error_response("G4_REQUEST_TOO_LARGE", 413)(scope, receive, send)
        pairs = parse_qsl(raw_query.decode("latin1"), keep_blank_values=True)
        names = [p[0] for p in pairs]
        relative = path.removeprefix("/api/intelligence")
        allowed = {"/events/detail": {"briefing_id", "event_snapshot_id"},
                   "/archive": {"briefing_id"}, "/coverage": {"briefing_id"},
                   "/persona": {"as_of"}, "/persona/versions": {"as_of", "limit", "offset"},
                   "/interactions": {"as_of", "limit", "offset"}}
        if len(names) != len(set(names)) or set(names) - allowed.get(relative, set()):
            return await error_response("G4_QUERY_INVALID", 422)(scope, receive, send)
        with self.lock:
            full = self.active >= self.max_requests
            if not full:
                self.active += 1
        if full:
            return await error_response("G4_REQUEST_CAPACITY_EXCEEDED", 429)(scope, receive, send)
        try:
            if method != "POST":
                return await self.app(scope, receive, send)
            if headers.get(b"content-type", "").split(";")[0].strip().lower() != "application/json":
                return await error_response("G4_JSON_REQUIRED", 415)(scope, receive, send)
            length = headers.get(b"content-length")
            if length is not None and (not length.isdigit() or int(length) > self.max_body):
                return await error_response("G4_REQUEST_TOO_LARGE", 413)(scope, receive, send)
            payload = bytearray()
            while True:
                try:
                    message = await asyncio.wait_for(receive(), timeout=5)
                except asyncio.TimeoutError:
                    return await error_response("G4_REQUEST_BODY_TIMEOUT", 408)(scope, receive, send)
                if message["type"] == "http.disconnect":
                    return
                payload.extend(message.get("body", b""))
                if len(payload) > self.max_body:
                    return await error_response("G4_REQUEST_TOO_LARGE", 413)(scope, receive, send)
                if not message.get("more_body", False):
                    break
            if length is not None and int(length) != len(payload):
                return await error_response("G4_CONTENT_LENGTH_INVALID", 400)(scope, receive, send)
            def unique(items):
                result = {}
                for key, value in items:
                    if key in result:
                        raise ValueError
                    result[key] = value
                return result
            def invalid_constant(_):
                raise ValueError
            try:
                json.loads(payload, object_pairs_hook=unique, parse_constant=invalid_constant)
            except (ValueError, UnicodeError, RecursionError):
                return await error_response("G4_JSON_INVALID", 422)(scope, receive, send)
            sent = False
            async def replay():
                nonlocal sent
                if not sent:
                    sent = True
                    return dict(type="http.request", body=bytes(payload), more_body=False)
                return await receive()
            await self.app(scope, replay, send)
        finally:
            with self.lock:
                self.active -= 1
