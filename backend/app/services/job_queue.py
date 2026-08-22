from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app import settings
from app.services.redis_runtime import redis_client


def enqueue(
    queue_name: str,
    function: Callable[..., Any],
    *args: Any,
    job_id: str,
    capacity: int,
    timeout_seconds: int = 3600,
) -> None:
    from rq import Queue, Retry

    queue = Queue(queue_name, connection=redis_client(), default_timeout=timeout_seconds)
    if queue.count >= capacity:
        raise RuntimeError(f"{queue_name.title()} queue is full. Please retry shortly.")
    queue.enqueue(
        function,
        *args,
        job_id=job_id,
        retry=Retry(max=2, interval=[10, 30]),
        result_ttl=86400,
        failure_ttl=604800,
        job_timeout=timeout_seconds,
    )


def queue_health() -> None:
    if settings.QUEUE_MODE == "redis":
        redis_client().ping()
