from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from app.settings import DB_PATH


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id() -> str:
    return uuid.uuid4().hex


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _migrate(conn: sqlite3.Connection) -> None:
    """Add missing columns/tables to existing databases."""
    # Users table
    row = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'").fetchone()
    if row is None:
        conn.execute(
            """
            create table if not exists users (
                id text primary key,
                email text not null unique,
                name text not null,
                password_hash text not null,
                storage_used integer not null default 0,
                created_at text not null
            );
            """
        )

    # user_id columns on existing tables
    for table in ("projects", "datasets", "chat_sessions", "chat_messages", "artifacts"):
        cols = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}
        if "user_id" not in cols:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN user_id text")

    # chat_sessions table
    row = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='chat_sessions'").fetchone()
    if row is None:
        conn.execute(
            """
            create table if not exists chat_sessions (
                id text primary key,
                project_id text not null,
                dataset_id text not null,
                title text not null,
                created_at text not null,
                updated_at text not null
            );
            """
        )

    # session_id column in chat_messages
    cols = {row2["name"] for row2 in conn.execute("PRAGMA table_info(chat_messages)").fetchall()}
    if "session_id" not in cols:
        conn.execute("ALTER TABLE chat_messages ADD COLUMN session_id text")

    # relational_schemas table
    row = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='relational_schemas'").fetchone()
    if row is None:
        conn.execute(
            """
            create table if not exists relational_schemas (
                id text primary key,
                project_id text not null references projects(id) on delete cascade,
                user_id text,
                name text not null,
                original_filename text not null,
                source_path text not null,
                schema_json text not null,
                status text not null default 'draft',
                created_at text not null,
                updated_at text not null
            );
            """
        )

    conn.execute(
        """
        delete from chat_sessions
        where dataset_id is not null
          and dataset_id not in (select id from datasets)
        """
    )


def init_db(db_path: Path = DB_PATH) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with connect() as conn:
        conn.executescript(
            """
            create table if not exists projects (
                id text primary key,
                name text not null,
                description text,
                created_at text not null,
                updated_at text not null
            );

            create table if not exists datasets (
                id text primary key,
                project_id text not null references projects(id) on delete cascade,
                name text not null,
                original_filename text not null,
                file_type text not null,
                source_path text not null,
                working_path text not null,
                row_count integer not null,
                column_count integer not null,
                status text not null,
                profile_json text not null,
                created_at text not null,
                updated_at text not null
            );

            create table if not exists chat_sessions (
                id text primary key,
                project_id text not null,
                dataset_id text not null,
                title text not null,
                created_at text not null,
                updated_at text not null
            );

            create table if not exists chat_messages (
                id text primary key,
                project_id text not null,
                dataset_id text,
                session_id text,
                role text not null,
                content text not null,
                payload_json text not null,
                created_at text not null
            );

            create table if not exists artifacts (
                id text primary key,
                project_id text not null,
                dataset_id text,
                kind text not null,
                title text not null,
                status text not null,
                payload_json text not null,
                created_at text not null,
                updated_at text not null
            );

            create table if not exists report_types (
                id text primary key,
                user_id text not null,
                project_id text not null,
                dataset_id text not null,
                name text not null,
                description text not null default '',
                payload_json text not null,
                is_default integer not null default 0,
                created_at text not null,
                updated_at text not null
            );
            """
        )
        _migrate(conn)


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    from app.services.profiling import json_safe

    result = dict(row)
    for key in ("profile_json", "payload_json"):
        if key in result:
            target_key = "profile" if key == "profile_json" else "payload"
            result[target_key] = json_safe(json.loads(result.pop(key) or "{}"))
    return result


def list_projects() -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute("select * from projects order by updated_at desc").fetchall()
    return [dict(row) for row in rows]


def create_project(name: str, description: str | None = None) -> dict[str, Any]:
    project_id = new_id()
    ts = now_iso()
    with connect() as conn:
        conn.execute(
            "insert into projects (id, name, description, created_at, updated_at) values (?, ?, ?, ?, ?)",
            (project_id, name, description, ts, ts),
        )
    return get_project(project_id)  # type: ignore[return-value]


def get_project(project_id: str) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute("select * from projects where id = ?", (project_id,)).fetchone()
    return dict(row) if row else None


def get_project_for_user(user_id: str, project_id: str) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute("select * from projects where id = ? and user_id = ?", (project_id, user_id)).fetchone()
    return dict(row) if row else None


def create_dataset(record: dict[str, Any]) -> dict[str, Any]:
    dataset_id = record.get("id") or new_id()
    ts = now_iso()
    profile_json = json.dumps(record["profile"], ensure_ascii=False)
    with connect() as conn:
        conn.execute(
            """
            insert into datasets (
                id, project_id, name, original_filename, file_type, source_path,
                working_path, row_count, column_count, status, profile_json,
                created_at, updated_at
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                dataset_id,
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


def get_dataset(dataset_id: str) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute("select * from datasets where id = ?", (dataset_id,)).fetchone()
    return row_to_dict(row)


def get_dataset_for_user(user_id: str, project_id: str, dataset_id: str) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute(
            "select * from datasets where id = ? and project_id = ? and user_id = ?",
            (dataset_id, project_id, user_id),
        ).fetchone()
    return row_to_dict(row)


def update_dataset_profile(dataset_id: str, profile: dict[str, Any]) -> dict[str, Any] | None:
    ts = now_iso()
    profile_json = json.dumps(profile, ensure_ascii=False)
    with connect() as conn:
        row = conn.execute("select project_id from datasets where id = ?", (dataset_id,)).fetchone()
        if row is None:
            return None
        project_id = str(row["project_id"])
        conn.execute(
            "update datasets set profile_json = ?, updated_at = ? where id = ?",
            (profile_json, ts, dataset_id),
        )
        conn.execute("update projects set updated_at = ? where id = ?", (ts, project_id))
    return get_dataset(dataset_id)


def list_datasets(project_id: str) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            "select * from datasets where project_id = ? order by created_at desc", (project_id,)
        ).fetchall()
    return [row_to_dict(row) for row in rows if row is not None]  # type: ignore[list-item]


def delete_dataset(project_id: str, dataset_id: str) -> dict[str, Any] | None:
    dataset = get_dataset(dataset_id)
    if not dataset or dataset["project_id"] != project_id:
        return None
    ts = now_iso()
    with connect() as conn:
        conn.execute("delete from chat_messages where project_id = ? and dataset_id = ?", (project_id, dataset_id))
        conn.execute("delete from chat_sessions where project_id = ? and dataset_id = ?", (project_id, dataset_id))
        conn.execute(
            "delete from artifacts where project_id = ? and dataset_id = ? and kind <> 'report'",
            (project_id, dataset_id),
        )
        conn.execute("delete from datasets where project_id = ? and id = ?", (project_id, dataset_id))
        conn.execute("update projects set updated_at = ? where id = ?", (ts, project_id))
    return dataset


def delete_dataset_for_user(user_id: str, project_id: str, dataset_id: str) -> dict[str, Any] | None:
    dataset = get_dataset_for_user(user_id, project_id, dataset_id)
    if not dataset:
        return None
    ts = now_iso()
    with connect() as conn:
        conn.execute(
            "delete from chat_messages where project_id = ? and dataset_id = ? and user_id = ?",
            (project_id, dataset_id, user_id),
        )
        conn.execute(
            "delete from chat_sessions where project_id = ? and dataset_id = ? and user_id = ?",
            (project_id, dataset_id, user_id),
        )
        conn.execute(
            "delete from artifacts where project_id = ? and dataset_id = ? and user_id = ? and kind <> 'report'",
            (project_id, dataset_id, user_id),
        )
        conn.execute(
            "delete from datasets where project_id = ? and id = ? and user_id = ?",
            (project_id, dataset_id, user_id),
        )
        conn.execute("update projects set updated_at = ? where id = ? and user_id = ?", (ts, project_id, user_id))
    return dataset


def create_chat_message(
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
            insert into chat_messages (id, project_id, dataset_id, session_id, role, content, payload_json, created_at)
            values (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (message_id, project_id, dataset_id, session_id, role, content, json.dumps(payload or {}), ts),
        )
        if session_id:
            conn.execute("update chat_sessions set updated_at = ? where id = ?", (ts, session_id))
    return {"id": message_id, "project_id": project_id, "dataset_id": dataset_id, "session_id": session_id, "role": role, "content": content, "payload": payload or {}, "created_at": ts}


def list_chat_messages(project_id: str, dataset_id: str | None = None, session_id: str | None = None) -> list[dict[str, Any]]:
    params: list[Any] = [project_id]
    sql = "select * from chat_messages where project_id = ?"
    if dataset_id:
        sql += " and dataset_id = ?"
        params.append(dataset_id)
    if session_id:
        sql += " and session_id = ?"
        params.append(session_id)
    sql += " order by created_at asc"
    with connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [row_to_dict(row) for row in rows if row is not None]  # type: ignore[list-item]




def create_artifact(
    project_id: str,
    kind: str,
    title: str,
    payload: dict[str, Any],
    dataset_id: str | None = None,
    status: str = "draft",
    user_id: str | None = None,
) -> dict[str, Any]:
    from app.services.profiling import json_safe

    artifact_id = new_id()
    ts = now_iso()
    safe_payload = json_safe(payload)
    with connect() as conn:
        conn.execute(
            """
            insert into artifacts (id, user_id, project_id, dataset_id, kind, title, status, payload_json, created_at, updated_at)
            values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (artifact_id, user_id, project_id, dataset_id, kind, title, status, json.dumps(safe_payload, allow_nan=False), ts, ts),
        )
        conn.execute("update projects set updated_at = ? where id = ?", (ts, project_id))
    return get_artifact(artifact_id)  # type: ignore[return-value]


def get_artifact(artifact_id: str) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute("select * from artifacts where id = ?", (artifact_id,)).fetchone()
    return row_to_dict(row)


def get_artifact_for_user(user_id: str, project_id: str, artifact_id: str) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute(
            "select * from artifacts where id = ? and project_id = ? and user_id = ?",
            (artifact_id, project_id, user_id),
        ).fetchone()
    return row_to_dict(row)


def list_artifacts(project_id: str, dataset_id: str | None = None) -> list[dict[str, Any]]:
    params: tuple[Any, ...]
    sql = "select * from artifacts where project_id = ?"
    params = (project_id,)
    if dataset_id:
        sql += " and dataset_id = ?"
        params = (project_id, dataset_id)
    sql += " order by updated_at desc"
    with connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [row_to_dict(row) for row in rows if row is not None]  # type: ignore[list-item]


def list_artifacts_for_user(user_id: str, project_id: str, dataset_id: str | None = None) -> list[dict[str, Any]]:
    params: tuple[Any, ...] = (project_id, user_id)
    sql = "select * from artifacts where project_id = ? and user_id = ?"
    if dataset_id:
        sql += " and dataset_id = ?"
        params = (project_id, user_id, dataset_id)
    sql += " order by updated_at desc"
    with connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [row_to_dict(row) for row in rows if row is not None]  # type: ignore[list-item]


def update_artifact(
    artifact_id: str,
    *,
    status: str | None = None,
    title: str | None = None,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    from app.services.profiling import json_safe

    updates: list[str] = []
    params: list[Any] = []
    if status is not None:
        updates.append("status = ?")
        params.append(status)
    if title is not None:
        updates.append("title = ?")
        params.append(title)
    if payload is not None:
        updates.append("payload_json = ?")
        params.append(json.dumps(json_safe(payload), ensure_ascii=False, allow_nan=False))
    if not updates:
        return get_artifact(artifact_id)

    ts = now_iso()
    updates.append("updated_at = ?")
    params.append(ts)
    params.append(artifact_id)
    with connect() as conn:
        cursor = conn.execute(
            f"update artifacts set {', '.join(updates)} where id = ?",
            params,
        )
        if cursor.rowcount == 0:
            return None
    return get_artifact(artifact_id)


def delete_artifact_for_user(user_id: str, project_id: str, artifact_id: str) -> bool:
    with connect() as conn:
        cursor = conn.execute(
            "delete from artifacts where id = ? and project_id = ? and user_id = ?",
            (artifact_id, project_id, user_id),
        )
        conn.execute(
            "delete from chat_messages where project_id = ? and user_id = ? and role = 'assistant' and payload_json like ?",
            (project_id, user_id, f'%"artifact"%"id"%{artifact_id}%'),
        )
        return cursor.rowcount > 0


def update_artifact_for_user(
    user_id: str,
    project_id: str,
    artifact_id: str,
    *,
    status: str | None = None,
    title: str | None = None,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    from app.services.profiling import json_safe

    updates: list[str] = []
    params: list[Any] = []
    if status is not None:
        updates.append("status = ?")
        params.append(status)
    if title is not None:
        updates.append("title = ?")
        params.append(title)
    if payload is not None:
        updates.append("payload_json = ?")
        params.append(json.dumps(json_safe(payload), ensure_ascii=False, allow_nan=False))
    if not updates:
        return get_artifact_for_user(user_id, project_id, artifact_id)

    ts = now_iso()
    updates.append("updated_at = ?")
    params.extend([ts, artifact_id, project_id, user_id])
    with connect() as conn:
        cursor = conn.execute(
            f"update artifacts set {', '.join(updates)} where id = ? and project_id = ? and user_id = ?",
            params,
        )
        if cursor.rowcount == 0:
            return None
    return get_artifact_for_user(user_id, project_id, artifact_id)


# ------------------------------------------------------------------
# Custom report types
# ------------------------------------------------------------------

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

MAX_STORAGE_BYTES = 10 * 1024 * 1024  # 10 MB per user


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
        conn.execute("update users set storage_used = storage_used + ? where id = ?", (delta, user_id))
        row = conn.execute("select storage_used from users where id = ?", (user_id,)).fetchone()
    return row["storage_used"] if row else 0


def get_user_storage(user_id: str) -> int:
    with connect() as conn:
        row = conn.execute("select storage_used from users where id = ?", (user_id,)).fetchone()
    return row["storage_used"] if row else 0


def check_storage_limit(user_id: str, additional_bytes: int = 0) -> bool:
    """Return True if user still has room for additional_bytes."""
    current = get_user_storage(user_id)
    return (current + additional_bytes) <= MAX_STORAGE_BYTES


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
# Relational Schemas
# ------------------------------------------------------------------

def create_relational_schema(record: dict[str, Any], user_id: str | None = None) -> dict[str, Any]:
    schema_id = record.get("id") or new_id()
    ts = now_iso()
    schema_json = json.dumps(record["schema"], ensure_ascii=False)
    with connect() as conn:
        conn.execute(
            """
            insert into relational_schemas (
                id, project_id, user_id, name, original_filename, source_path,
                schema_json, status, created_at, updated_at
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                schema_id,
                record["project_id"],
                user_id,
                record["name"],
                record["original_filename"],
                record["source_path"],
                schema_json,
                record.get("status", "draft"),
                ts,
                ts,
            ),
        )
        conn.execute("update projects set updated_at = ? where id = ?", (ts, record["project_id"]))
    return get_relational_schema(schema_id)


def get_relational_schema(schema_id: str) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute("select * from relational_schemas where id = ?", (schema_id,)).fetchone()
    if row is None:
        return None
    result = dict(row)
    if "schema_json" in result:
        result["schema"] = json.loads(result.pop("schema_json") or "{}")
    return result


def list_relational_schemas(project_id: str, user_id: str | None = None) -> list[dict[str, Any]]:
    if user_id:
        with connect() as conn:
            rows = conn.execute(
                "select * from relational_schemas where project_id = ? and user_id = ? order by created_at desc",
                (project_id, user_id),
            ).fetchall()
    else:
        with connect() as conn:
            rows = conn.execute(
                "select * from relational_schemas where project_id = ? order by created_at desc",
                (project_id,),
            ).fetchall()
    result = []
    for row in rows:
        d = dict(row)
        if "schema_json" in d:
            d["schema"] = json.loads(d.pop("schema_json") or "{}")
        result.append(d)
    return result


def update_relational_schema(schema_id: str, schema: dict[str, Any]) -> dict[str, Any] | None:
    """Update the schema (relationships, table metadata, etc.)."""
    ts = now_iso()
    schema_json = json.dumps(schema, ensure_ascii=False)
    with connect() as conn:
        row = conn.execute("select project_id from relational_schemas where id = ?", (schema_id,)).fetchone()
        if row is None:
            return None
        project_id = str(row["project_id"])
        conn.execute(
            "update relational_schemas set schema_json = ?, updated_at = ? where id = ?",
            (schema_json, ts, schema_id),
        )
        conn.execute("update projects set updated_at = ? where id = ?", (ts, project_id))
    return get_relational_schema(schema_id)


def delete_relational_schema(project_id: str, schema_id: str) -> dict[str, Any] | None:
    schema = get_relational_schema(schema_id)
    if not schema or schema["project_id"] != project_id:
        return None
    ts = now_iso()
    with connect() as conn:
        conn.execute("delete from relational_schemas where project_id = ? and id = ?", (project_id, schema_id))
        conn.execute("update projects set updated_at = ? where id = ?", (ts, project_id))
    return schema
