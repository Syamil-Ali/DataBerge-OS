from __future__ import annotations

import hmac
import json
import logging
import threading
import time
import uuid
from collections import defaultdict, deque

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse, Response

from app import settings

logger = logging.getLogger("data_berge.http")

_UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
_CSRF_EXEMPT_PATHS = {"/api/auth/login", "/api/auth/register"}
_RATE_LIMITED_PATHS = {"/api/auth/login", "/api/auth/register"}


class AuthRateLimiter:
    """Small bounded limiter for the supported single-instance deployment."""

    def __init__(self, limit: int, window_seconds: int) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str, now: float | None = None) -> tuple[bool, int]:
        current = now if now is not None else time.monotonic()
        cutoff = current - self.window_seconds
        with self._lock:
            events = self._events[key]
            while events and events[0] <= cutoff:
                events.popleft()
            if len(events) >= self.limit:
                retry_after = max(1, int(self.window_seconds - (current - events[0])))
                return False, retry_after
            events.append(current)
            if len(self._events) > 10_000:
                self._events = defaultdict(deque, {k: v for k, v in self._events.items() if v and v[-1] > cutoff})
            return True, 0


class RedisRateLimiter:
    """Atomic fixed-window limiter shared by every API replica."""

    _SCRIPT = """
    local current = redis.call('INCR', KEYS[1])
    if current == 1 then
      redis.call('EXPIRE', KEYS[1], ARGV[1])
    end
    local ttl = redis.call('TTL', KEYS[1])
    return {current, ttl}
    """

    def __init__(self, limit: int, window_seconds: int) -> None:
        self.limit = limit
        self.window_seconds = window_seconds

    def allow(self, key: str, now: float | None = None) -> tuple[bool, int]:
        from app.services.redis_runtime import redis_client

        current, ttl = redis_client().eval(
            self._SCRIPT,
            1,
            f"rate-limit:{key}",
            self.window_seconds,
        )
        return int(current) <= self.limit, max(1, int(ttl))


rate_limiter = (RedisRateLimiter if settings.REDIS_URL else AuthRateLimiter)(
    settings.AUTH_RATE_LIMIT_REQUESTS,
    settings.AUTH_RATE_LIMIT_WINDOW_SECONDS,
)


class RequestBodyTooLarge(Exception):
    pass


class RequestBodyLimitMiddleware:
    """Enforce a request cap before Starlette parses multipart or JSON bodies."""

    def __init__(self, app, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = {key.lower(): value for key, value in scope.get("headers", [])}
        content_length = headers.get(b"content-length")
        if content_length:
            try:
                if int(content_length) > self.max_bytes:
                    response = JSONResponse({"detail": "Request body is too large"}, status_code=413)
                    await response(scope, receive, send)
                    return
            except ValueError:
                response = JSONResponse({"detail": "Invalid Content-Length"}, status_code=400)
                await response(scope, receive, send)
                return

        received = 0

        async def limited_receive():
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    raise RequestBodyTooLarge
            return message

        try:
            await self.app(scope, limited_receive, send)
        except RequestBodyTooLarge:
            response = JSONResponse({"detail": "Request body is too large"}, status_code=413)
            await response(scope, receive, send)


def _client_ip(request: Request) -> str:
    if settings.TRUST_PROXY_HEADERS:
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded:
            return forwarded.split(",", 1)[0].strip()
    return request.client.host if request.client else "unknown"


class ProductionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
        started = time.perf_counter()

        if request.url.path in _RATE_LIMITED_PATHS:
            allowed, retry_after = rate_limiter.allow(f"{request.url.path}:{_client_ip(request)}")
            if not allowed:
                return JSONResponse(
                    {"detail": "Too many authentication attempts", "request_id": request_id},
                    status_code=429,
                    headers={"Retry-After": str(retry_after), "X-Request-ID": request_id},
                )

        if (
            request.method in _UNSAFE_METHODS
            and request.url.path not in _CSRF_EXEMPT_PATHS
            and request.cookies.get(settings.AUTH_COOKIE_NAME)
        ):
            cookie_token = request.cookies.get(settings.CSRF_COOKIE_NAME, "")
            header_token = request.headers.get("x-csrf-token", "")
            if not cookie_token or not header_token or not hmac.compare_digest(cookie_token, header_token):
                return JSONResponse(
                    {"detail": "CSRF validation failed", "request_id": request_id},
                    status_code=403,
                    headers={"X-Request-ID": request_id},
                )

        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
        finally:
            logger.info(json.dumps({
                "event": "http_request",
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": status_code,
                "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                "client_ip": _client_ip(request),
            }, separators=(",", ":")))

        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        if settings.IS_PRODUCTION:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response
