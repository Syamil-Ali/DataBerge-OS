from __future__ import annotations

from threading import Lock
from typing import Any

from app import settings

_client: Any = None
_lock = Lock()


def redis_client():
    global _client
    if not settings.REDIS_URL:
        raise RuntimeError("REDIS_URL is not configured")
    with _lock:
        if _client is None:
            import redis

            _client = redis.Redis.from_url(
                settings.REDIS_URL,
                decode_responses=False,
                socket_connect_timeout=3,
                socket_timeout=5,
                health_check_interval=30,
            )
    return _client


def redis_health_check() -> None:
    redis_client().ping()


def close_redis() -> None:
    global _client
    with _lock:
        client, _client = _client, None
    if client is not None:
        client.close()
