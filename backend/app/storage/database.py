from __future__ import annotations

import json
import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from app import settings
from app.settings import ARTIFACT_DIR, DB_PATH, MAX_STORAGE_BYTES, UPLOAD_DIR
from app.storage.connections import connect as connect_backend, uses_postgres
from app.storage.object_store import get_object_store
from app.storage.postgres_schema import initialize_postgres


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id() -> str:
    return uuid.uuid4().hex


@contextmanager
def connect(db_path: Path | None = None) -> Iterator[Any]:
    target = None if uses_postgres(db_path) else (db_path or DB_PATH)
    with connect_backend(target) as connection:
        yield connection


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


def init_db(db_path: Path | None = None) -> None:
    if uses_postgres(db_path):
        with connect() as conn:
            initialize_postgres(conn)
            _apply_versioned_migrations(conn)
        return
    target = db_path or DB_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    with connect(target) as conn:
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
        _apply_versioned_migrations(conn)


def assert_schema_current() -> None:
    with connect() as conn:
        row = conn.execute("select max(version) as version from schema_migrations").fetchone()
    version = int((row or {}).get("version") or 0) if isinstance(row, dict) else int(row["version"] or 0)
    if version < 3:
        raise RuntimeError("Database schema is not current; run the migration command before starting the API")


def _apply_versioned_migrations(conn: Any) -> None:
    """Apply idempotent, numbered schema changes and retain an audit trail."""
    conn.execute(
        """
        create table if not exists schema_migrations (
            version integer primary key,
            name text not null,
            applied_at text not null
        )
        """
    )
    migrations = [
        (1, "baseline_existing_schema", []),
        (2, "production_query_indexes", [
            "create index if not exists idx_projects_user_updated on projects(user_id, updated_at desc)",
            "create index if not exists idx_datasets_user_project on datasets(user_id, project_id)",
            "create index if not exists idx_sessions_user_project on chat_sessions(user_id, project_id, updated_at desc)",
            "create index if not exists idx_messages_user_session on chat_messages(user_id, session_id, created_at)",
            "create index if not exists idx_artifacts_user_project on artifacts(user_id, project_id, updated_at desc)",
            "create index if not exists idx_schemas_user_project on relational_schemas(user_id, project_id)",
        ]),
        (3, "durable_background_jobs", [
            """
            create table if not exists background_jobs (
                id text primary key,
                user_id text not null references users(id) on delete cascade,
                queue text not null,
                kind text not null,
                status text not null,
                message text not null default '',
                payload_json text not null default '{}',
                result_json text not null default '{}',
                created_at text not null,
                updated_at text not null
            )
            """,
            "create index if not exists idx_jobs_user_updated on background_jobs(user_id, updated_at desc)",
            "create index if not exists idx_jobs_queue_status on background_jobs(queue, status, created_at)",
        ]),
    ]
    applied = {row["version"] for row in conn.execute("select version from schema_migrations").fetchall()}
    for version, name, statements in migrations:
        if version in applied:
            continue
        for statement in statements:
            conn.execute(statement)
        conn.execute(
            "insert into schema_migrations(version, name, applied_at) values (?, ?, ?)",
            (version, name, now_iso()),
        )


def recover_interrupted_jobs() -> int:
    """Fail report jobs that cannot survive a process restart."""
    if settings.QUEUE_MODE == "redis":
        return 0
    with connect() as conn:
        rows = conn.execute(
            "select id, payload_json from artifacts where kind = 'report' and status = 'generating'"
        ).fetchall()
        for row in rows:
            payload = json.loads(row["payload_json"] or "{}")
            progress = payload.get("report_progress") or {}
            payload["report_progress"] = {
                **progress,
                "status": "failed",
                "message": "Generation was interrupted by a service restart. Please retry.",
                "current_step": "failed",
            }
            conn.execute(
                "update artifacts set status = 'failed', title = ?, payload_json = ?, updated_at = ? where id = ?",
                ("Report generation interrupted", json.dumps(payload), now_iso(), row["id"]),
            )
    return len(rows)


def reconcile_storage_usage() -> None:
    """Recompute quota counters from owned upload directories after restart."""
    with connect() as conn:
        users = [str(row["id"]) for row in conn.execute("select id from users").fetchall()]
        if settings.OBJECT_STORAGE_BACKEND == "s3":
            store = get_object_store()
            for user_id in users:
                conn.execute("update users set storage_used = ? where id = ?", (store.usage(user_id), user_id))
            return
        upload_root = UPLOAD_DIR.resolve()
        for user_id in users:
            rows = conn.execute(
                """
                select source_path from datasets where user_id = ?
                union
                select source_path from relational_schemas where user_id = ?
                """,
                (user_id, user_id),
            ).fetchall()
            directories: set[Path] = set()
            for row in rows:
                source = Path(str(row["source_path"] or "")).resolve()
                try:
                    source.relative_to(upload_root)
                except ValueError:
                    continue
                if source.parent != upload_root:
                    directories.add(source.parent)
            total = sum(
                item.stat().st_size
                for directory in directories
                if directory.exists()
                for item in directory.rglob("*")
                if item.is_file()
            )
            conn.execute("update users set storage_used = ? where id = ?", (total, user_id))


def health_check() -> dict[str, Any]:
    """Verify database access and writable persistent-storage directories."""
    with connect() as conn:
        conn.execute("select 1").fetchone()
        migration = conn.execute("select max(version) as version from schema_migrations").fetchone()
        journal_mode = "postgresql" if uses_postgres() else conn.execute("pragma journal_mode").fetchone()[0]
    get_object_store().health_check()
    if settings.REDIS_URL:
        from app.services.redis_runtime import redis_health_check
        redis_health_check()
    writable = {
        "object_storage": True,
        "cache": settings.CACHE_DIR.exists() and os.access(settings.CACHE_DIR, os.W_OK),
    }
    if not uses_postgres():
        writable["database"] = DB_PATH.parent.exists() and os.access(DB_PATH.parent, os.W_OK)
    if not all(writable.values()):
        raise RuntimeError("Persistent storage is not writable")
    return {
        "status": "ready",
        "database": "ok",
        "journal_mode": journal_mode,
        "schema_version": int(migration["version"] or 0),
        "storage": writable,
        "redis": "ok" if settings.REDIS_URL else "disabled",
    }


def row_to_dict(row: Any | None) -> dict[str, Any] | None:
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
# Compatibility facade: feature repositories own these domains while existing
# call sites retain the stable app.storage.database API.
from app.storage import account_repository as _accounts
from app.storage import job_repository as _jobs
from app.storage import relational_repository as _relational
_report_type_record = _accounts._report_type_record
list_report_types_for_user = _accounts.list_report_types_for_user
get_report_type_for_user = _accounts.get_report_type_for_user
create_report_type_for_user = _accounts.create_report_type_for_user
update_report_type_for_user = _accounts.update_report_type_for_user
delete_report_type_for_user = _accounts.delete_report_type_for_user
create_chat_session = _accounts.create_chat_session
get_chat_session = _accounts.get_chat_session
update_chat_session_title = _accounts.update_chat_session_title
create_user = _accounts.create_user
get_user_by_id = _accounts.get_user_by_id
get_user_by_email = _accounts.get_user_by_email
update_user_storage = _accounts.update_user_storage
get_user_storage = _accounts.get_user_storage
check_storage_limit = _accounts.check_storage_limit
reserve_user_storage = _accounts.reserve_user_storage
list_projects_for_user = _accounts.list_projects_for_user
create_project_for_user = _accounts.create_project_for_user
list_datasets_for_user = _accounts.list_datasets_for_user
create_dataset_for_user = _accounts.create_dataset_for_user
replace_dataset_for_user = _accounts.replace_dataset_for_user
list_chat_sessions_for_user = _accounts.list_chat_sessions_for_user
create_chat_session_for_user = _accounts.create_chat_session_for_user
get_chat_session_for_user = _accounts.get_chat_session_for_user
create_chat_message_for_user = _accounts.create_chat_message_for_user
list_chat_messages_for_user = _accounts.list_chat_messages_for_user
clear_chat_messages_for_user = _accounts.clear_chat_messages_for_user
delete_chat_message_for_user = _accounts.delete_chat_message_for_user
update_chat_session_title_for_user = _accounts.update_chat_session_title_for_user
delete_chat_session_for_user = _accounts.delete_chat_session_for_user
get_chat_message_count_for_user = _accounts.get_chat_message_count_for_user
create_background_job = _jobs.create_background_job
get_background_job = _jobs.get_background_job
update_background_job = _jobs.update_background_job
create_relational_schema = _relational.create_relational_schema
get_relational_schema = _relational.get_relational_schema
list_relational_schemas = _relational.list_relational_schemas
update_relational_schema = _relational.update_relational_schema
delete_relational_schema = _relational.delete_relational_schema
