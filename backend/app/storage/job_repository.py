from __future__ import annotations

import json
from typing import Any

from app.storage.database import connect, new_id, now_iso
def create_background_job(
    user_id: str,
    *,
    queue: str,
    kind: str,
    payload: dict[str, Any] | None = None,
    job_id: str | None = None,
) -> dict[str, Any]:
    identifier = job_id or new_id()
    ts = now_iso()
    with connect() as conn:
        conn.execute(
            """
            insert into background_jobs
            (id, user_id, queue, kind, status, message, payload_json, result_json, created_at, updated_at)
            values (?, ?, ?, ?, 'queued', 'Queued', ?, '{}', ?, ?)
            """,
            (identifier, user_id, queue, kind, json.dumps(payload or {}), ts, ts),
        )
    return get_background_job(user_id, identifier)  # type: ignore[return-value]


def get_background_job(user_id: str, job_id: str) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute(
            "select * from background_jobs where id = ? and user_id = ?",
            (job_id, user_id),
        ).fetchone()
    if row is None:
        return None
    result = dict(row)
    result["payload"] = json.loads(result.pop("payload_json") or "{}")
    result["result"] = json.loads(result.pop("result_json") or "{}")
    return result


def update_background_job(
    user_id: str,
    job_id: str,
    *,
    status: str,
    message: str,
    result: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    ts = now_iso()
    with connect() as conn:
        cursor = conn.execute(
            """
            update background_jobs
            set status = ?, message = ?, result_json = ?, updated_at = ?
            where id = ? and user_id = ?
            """,
            (status, message, json.dumps(result or {}), ts, job_id, user_id),
        )
        if cursor.rowcount == 0:
            return None
    return get_background_job(user_id, job_id)


# ------------------------------------------------------------------
# Relational Schemas
# ------------------------------------------------------------------
