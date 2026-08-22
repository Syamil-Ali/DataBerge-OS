from __future__ import annotations

import json
import sqlite3
from typing import Any

from app.storage.database import (
    connect,
    get_dataset,
    get_dataset_for_user,
    get_project,
    new_id,
    now_iso,
    row_to_dict,
)


def _storage_limit() -> int:
    from app.storage import database
    return database.MAX_STORAGE_BYTES
def _report_type_record(row: sqlite3.Row | None) -> dict[str, Any] | None:
    record = row_to_dict(row)
    if record is not None:
        record["is_default"] = bool(record.get("is_default"))
    return record


def list_report_types_for_user(user_id: str, project_id: str, dataset_id: str) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            """
            select * from report_types
            where user_id = ? and project_id = ? and dataset_id = ?
            order by is_default desc, updated_at desc
            """,
            (user_id, project_id, dataset_id),
        ).fetchall()
    return [_report_type_record(row) for row in rows if row is not None]  # type: ignore[list-item]


def get_report_type_for_user(user_id: str, project_id: str, report_type_id: str) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute(
            "select * from report_types where id = ? and user_id = ? and project_id = ?",
            (report_type_id, user_id, project_id),
        ).fetchone()
    return _report_type_record(row)


def create_report_type_for_user(
    user_id: str,
    project_id: str,
    dataset_id: str,
    name: str,
    description: str,
    payload: dict[str, Any],
    is_default: bool = False,
) -> dict[str, Any]:
    report_type_id = new_id()
    ts = now_iso()
    from app.services.profiling import json_safe

    safe_payload = json_safe(payload)
    with connect() as conn:
        if is_default:
            conn.execute(
                "update report_types set is_default = 0 where user_id = ? and project_id = ? and dataset_id = ?",
                (user_id, project_id, dataset_id),
            )
        conn.execute(
            """
            insert into report_types
            (id, user_id, project_id, dataset_id, name, description, payload_json, is_default, created_at, updated_at)
            values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                report_type_id,
                user_id,
                project_id,
                dataset_id,
                name,
                description,
                json.dumps(safe_payload, ensure_ascii=False, allow_nan=False),
                int(is_default),
                ts,
                ts,
            ),
        )
    return get_report_type_for_user(user_id, project_id, report_type_id)  # type: ignore[return-value]


def update_report_type_for_user(
    user_id: str,
    project_id: str,
    report_type_id: str,
    *,
    dataset_id: str,
    name: str,
    description: str,
    payload: dict[str, Any],
    is_default: bool,
) -> dict[str, Any] | None:
    from app.services.profiling import json_safe

    ts = now_iso()
    with connect() as conn:
        if is_default:
            conn.execute(
                "update report_types set is_default = 0 where user_id = ? and project_id = ? and dataset_id = ?",
                (user_id, project_id, dataset_id),
            )
        cursor = conn.execute(
            """
            update report_types
            set dataset_id = ?, name = ?, description = ?, payload_json = ?, is_default = ?, updated_at = ?
            where id = ? and user_id = ? and project_id = ?
            """,
            (
                dataset_id,
                name,
                description,
                json.dumps(json_safe(payload), ensure_ascii=False, allow_nan=False),
                int(is_default),
                ts,
                report_type_id,
                user_id,
                project_id,
            ),
        )
        if cursor.rowcount == 0:
            return None
    return get_report_type_for_user(user_id, project_id, report_type_id)


def delete_report_type_for_user(user_id: str, project_id: str, report_type_id: str) -> bool:
    with connect() as conn:
        cursor = conn.execute(
            "delete from report_types where id = ? and user_id = ? and project_id = ?",
            (report_type_id, user_id, project_id),
        )
    return cursor.rowcount > 0


# ------------------------------------------------------------------
# Chat Sessions
# ------------------------------------------------------------------

def create_chat_session(project_id: str, dataset_id: str, title: str = "New Chat") -> dict[str, Any]:
    session_id = new_id()
    ts = now_iso()
    with connect() as conn:
        conn.execute(
            "insert into chat_sessions (id, project_id, dataset_id, title, created_at, updated_at) values (?, ?, ?, ?, ?, ?)",
            (session_id, project_id, dataset_id, title, ts, ts),
        )
    return get_chat_session(session_id)  # type: ignore[return-value]


def get_chat_session(session_id: str) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute("select * from chat_sessions where id = ?", (session_id,)).fetchone()
    return dict(row) if row else None




def update_chat_session_title(session_id: str, title: str) -> dict[str, Any] | None:
    ts = now_iso()
    with connect() as conn:
        conn.execute("update chat_sessions set title = ?, updated_at = ? where id = ?", (title, ts, session_id))
    return get_chat_session(session_id)






# ------------------------------------------------------------------
# Users
# ------------------------------------------------------------------

def create_user(email: str, name: str, password_hash: str) -> dict[str, Any]:
    user_id = new_id()
    ts = now_iso()
    with connect() as conn:
        conn.execute(
            "insert into users (id, email, name, password_hash, storage_used, created_at) values (?, ?, ?, ?, 0, ?)",
            (user_id, email, name, password_hash, ts),
        )
    return get_user_by_id(user_id)  # type: ignore[return-value]


def get_user_by_id(user_id: str) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute("select * from users where id = ?", (user_id,)).fetchone()
    if row is None:
        return None
    d = dict(row)
    d.pop("password_hash", None)
    return d


def get_user_by_email(email: str) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute("select * from users where email = ?", (email,)).fetchone()
    return dict(row) if row else None


def update_user_storage(user_id: str, delta: int) -> int:
    """Increment storage_used by delta. Returns new storage_used."""
    with connect() as conn:
        conn.execute(
            "update users set storage_used = max(0, storage_used + ?) where id = ?",
            (delta, user_id),
        )
        row = conn.execute("select storage_used from users where id = ?", (user_id,)).fetchone()
    return row["storage_used"] if row else 0


def get_user_storage(user_id: str) -> int:
    with connect() as conn:
        row = conn.execute("select storage_used from users where id = ?", (user_id,)).fetchone()
    return row["storage_used"] if row else 0


def check_storage_limit(user_id: str, additional_bytes: int = 0) -> bool:
    """Return True if user still has room for additional_bytes."""
    current = get_user_storage(user_id)
    return (current + additional_bytes) <= _storage_limit()


def reserve_user_storage(user_id: str, additional_bytes: int) -> bool:
    """Atomically reserve quota so concurrent uploads cannot overcommit it."""
    if additional_bytes < 0:
        raise ValueError("Storage reservation cannot be negative")
    with connect() as conn:
        cursor = conn.execute(
            """
            update users
            set storage_used = storage_used + ?
            where id = ? and storage_used + ? <= ?
            """,
            (additional_bytes, user_id, additional_bytes, _storage_limit()),
        )
    return cursor.rowcount == 1


def list_projects_for_user(user_id: str) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute("select * from projects where user_id = ? order by updated_at desc", (user_id,)).fetchall()
    return [dict(row) for row in rows]


def create_project_for_user(user_id: str, name: str, description: str | None = None) -> dict[str, Any]:
    project_id = new_id()
    ts = now_iso()
    with connect() as conn:
        conn.execute(
            "insert into projects (id, user_id, name, description, created_at, updated_at) values (?, ?, ?, ?, ?, ?)",
            (project_id, user_id, name, description, ts, ts),
        )
    return get_project(project_id)  # type: ignore[return-value]


def list_datasets_for_user(user_id: str, project_id: str) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            "select * from datasets where project_id = ? and user_id = ? order by created_at desc",
            (project_id, user_id),
        ).fetchall()
    return [row_to_dict(row) for row in rows if row is not None]  # type: ignore[list-item]


def create_dataset_for_user(user_id: str, record: dict[str, Any]) -> dict[str, Any]:
    dataset_id = record.get("id") or new_id()
    ts = now_iso()
    profile_json = json.dumps(record["profile"], ensure_ascii=False)
    with connect() as conn:
        conn.execute(
            """
            insert into datasets (
                id, user_id, project_id, name, original_filename, file_type, source_path,
                working_path, row_count, column_count, status, profile_json,
                created_at, updated_at
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                dataset_id,
                user_id,
                record["project_id"],
                record["name"],
                record["original_filename"],
                record["file_type"],
                record["source_path"],
                record["working_path"],
                record["row_count"],
                record["column_count"],
                record.get("status", "profiled"),
                profile_json,
                ts,
                ts,
            ),
        )
        conn.execute("update projects set updated_at = ? where id = ?", (ts, record["project_id"]))
    return get_dataset(dataset_id)  # type: ignore[return-value]


def replace_dataset_for_user(user_id: str, record: dict[str, Any]) -> dict[str, Any]:
    """Atomically replace a materialized dataset and invalidate derived state."""
    dataset_id = record.get("id") or new_id()
    ts = now_iso()
    profile_json = json.dumps(record["profile"], ensure_ascii=False)
    with connect() as conn:
        conn.execute(
            "delete from chat_messages where project_id = ? and dataset_id = ? and user_id = ?",
            (record["project_id"], dataset_id, user_id),
        )
        conn.execute(
            "delete from chat_sessions where project_id = ? and dataset_id = ? and user_id = ?",
            (record["project_id"], dataset_id, user_id),
        )
        conn.execute(
            "delete from artifacts where project_id = ? and dataset_id = ? and user_id = ? and kind <> 'report'",
            (record["project_id"], dataset_id, user_id),
        )
        conn.execute(
            """
            insert into datasets (
                id, user_id, project_id, name, original_filename, file_type, source_path,
                working_path, row_count, column_count, status, profile_json,
                created_at, updated_at
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            on conflict(id) do update set
                user_id = excluded.user_id,
                project_id = excluded.project_id,
                name = excluded.name,
                original_filename = excluded.original_filename,
                file_type = excluded.file_type,
                source_path = excluded.source_path,
                working_path = excluded.working_path,
                row_count = excluded.row_count,
                column_count = excluded.column_count,
                status = excluded.status,
                profile_json = excluded.profile_json,
                updated_at = excluded.updated_at
            """,
            (
                dataset_id,
                user_id,
                record["project_id"],
                record["name"],
                record["original_filename"],
                record["file_type"],
                record["source_path"],
                record["working_path"],
                record["row_count"],
                record["column_count"],
                record.get("status", "profiled"),
                profile_json,
                ts,
                ts,
            ),
        )
        conn.execute(
            "update projects set updated_at = ? where id = ? and user_id = ?",
            (ts, record["project_id"], user_id),
        )
    return get_dataset_for_user(user_id, record["project_id"], dataset_id)  # type: ignore[return-value]


def list_chat_sessions_for_user(user_id: str, project_id: str, dataset_id: str | None = None) -> list[dict[str, Any]]:
    sql = "select * from chat_sessions where project_id = ? and user_id = ?"
    params: tuple[Any, ...] = (project_id, user_id)
    if dataset_id:
        sql += " and dataset_id = ?"
        params = (project_id, user_id, dataset_id)
    sql += " order by updated_at desc"
    with connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(row) for row in rows]


def create_chat_session_for_user(user_id: str, project_id: str, dataset_id: str, title: str = "New Chat") -> dict[str, Any]:
    session_id = new_id()
    ts = now_iso()
    with connect() as conn:
        conn.execute(
            "insert into chat_sessions (id, user_id, project_id, dataset_id, title, created_at, updated_at) values (?, ?, ?, ?, ?, ?, ?)",
            (session_id, user_id, project_id, dataset_id, title, ts, ts),
        )
    return get_chat_session(session_id)  # type: ignore[return-value]


def get_chat_session_for_user(user_id: str, project_id: str, session_id: str) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute(
            "select * from chat_sessions where id = ? and project_id = ? and user_id = ?",
            (session_id, project_id, user_id),
        ).fetchone()
    return dict(row) if row else None


def create_chat_message_for_user(
    user_id: str,
    project_id: str,
    dataset_id: str | None,
    role: str,
    content: str,
    payload: dict[str, Any] | None = None,
    session_id: str | None = None,
) -> dict[str, Any]:
    message_id = new_id()
    ts = now_iso()
    with connect() as conn:
        conn.execute(
            """
            insert into chat_messages (
                id, user_id, project_id, dataset_id, session_id,
                role, content, payload_json, created_at
            )
            values (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                message_id,
                user_id,
                project_id,
                dataset_id,
                session_id,
                role,
                content,
                json.dumps(payload or {}),
                ts,
            ),
        )
        if session_id:
            conn.execute(
                "update chat_sessions set updated_at = ? where id = ? and user_id = ?",
                (ts, session_id, user_id),
            )
    return {
        "id": message_id,
        "user_id": user_id,
        "project_id": project_id,
        "dataset_id": dataset_id,
        "session_id": session_id,
        "role": role,
        "content": content,
        "payload": payload or {},
        "created_at": ts,
    }


def list_chat_messages_for_user(user_id: str, project_id: str, dataset_id: str | None = None, session_id: str | None = None) -> list[dict[str, Any]]:
    sql = "select * from chat_messages where project_id = ? and user_id = ?"
    params: tuple[Any, ...] = (project_id, user_id)
    if dataset_id:
        sql += " and dataset_id = ?"
        params = (project_id, user_id, dataset_id)
    if session_id:
        sql += " and session_id = ?"
        params = params + (session_id,)
    sql += " order by created_at asc"
    with connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [row_to_dict(row) for row in rows if row is not None]  # type: ignore[list-item]


def clear_chat_messages_for_user(user_id: str, project_id: str, dataset_id: str | None = None) -> int:
    sql = "delete from chat_messages where project_id = ? and user_id = ?"
    params: list[Any] = [project_id, user_id]
    if dataset_id:
        sql += " and dataset_id = ?"
        params.append(dataset_id)
    with connect() as conn:
        cursor = conn.execute(sql, params)
    return cursor.rowcount


def delete_chat_message_for_user(user_id: str, project_id: str, message_id: str) -> bool:
    with connect() as conn:
        cursor = conn.execute(
            "delete from chat_messages where id = ? and project_id = ? and user_id = ?",
            (message_id, project_id, user_id),
        )
    return cursor.rowcount > 0


def update_chat_session_title_for_user(user_id: str, project_id: str, session_id: str, title: str) -> dict[str, Any] | None:
    ts = now_iso()
    with connect() as conn:
        cursor = conn.execute(
            "update chat_sessions set title = ?, updated_at = ? where id = ? and project_id = ? and user_id = ?",
            (title, ts, session_id, project_id, user_id),
        )
        if cursor.rowcount == 0:
            return None
    return get_chat_session_for_user(user_id, project_id, session_id)


def delete_chat_session_for_user(user_id: str, project_id: str, session_id: str) -> bool:
    with connect() as conn:
        conn.execute(
            "delete from chat_messages where session_id = ? and project_id = ? and user_id = ?",
            (session_id, project_id, user_id),
        )
        cursor = conn.execute(
            "delete from chat_sessions where id = ? and project_id = ? and user_id = ?",
            (session_id, project_id, user_id),
        )
        return cursor.rowcount > 0


def get_chat_message_count_for_user(user_id: str, session_id: str) -> int:
    with connect() as conn:
        row = conn.execute(
            "select count(*) as cnt from chat_messages where session_id = ? and user_id = ?",
            (session_id, user_id),
        ).fetchone()
    return row["cnt"] if row else 0


# ------------------------------------------------------------------
# Durable background jobs
# ------------------------------------------------------------------
