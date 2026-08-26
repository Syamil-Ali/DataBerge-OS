from __future__ import annotations

import json
from typing import Any

from app.storage.database import connect, new_id, now_iso


def _connection_record(row: Any | None, *, include_secret: bool = False) -> dict[str, Any] | None:
    if row is None:
        return None
    record = dict(row)
    record["config"] = json.loads(record.pop("config_json") or "{}")
    if not include_secret:
        record.pop("encrypted_secret", None)
    return record


def create_data_connection(
    user_id: str,
    project_id: str,
    *,
    name: str,
    provider: str,
    connector_type: str,
    config: dict[str, Any],
    encrypted_secret: str,
) -> dict[str, Any]:
    connection_id = new_id()
    ts = now_iso()
    with connect() as conn:
        conn.execute(
            """
            insert into data_connections (
                id, user_id, project_id, name, provider, connector_type,
                config_json, encrypted_secret, status, created_at, updated_at
            ) values (?, ?, ?, ?, ?, ?, ?, ?, 'untested', ?, ?)
            """,
            (
                connection_id, user_id, project_id, name, provider, connector_type,
                json.dumps(config, ensure_ascii=False), encrypted_secret, ts, ts,
            ),
        )
    return get_data_connection(user_id, project_id, connection_id)  # type: ignore[return-value]


def list_data_connections(user_id: str, project_id: str) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            "select * from data_connections where user_id = ? and project_id = ? order by updated_at desc",
            (user_id, project_id),
        ).fetchall()
    return [_connection_record(row) for row in rows]  # type: ignore[list-item]


def get_data_connection(
    user_id: str,
    project_id: str,
    connection_id: str,
    *,
    include_secret: bool = False,
) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute(
            "select * from data_connections where id = ? and user_id = ? and project_id = ?",
            (connection_id, user_id, project_id),
        ).fetchone()
    return _connection_record(row, include_secret=include_secret)


def update_data_connection_status(
    user_id: str,
    project_id: str,
    connection_id: str,
    *,
    status: str,
    tested: bool = False,
) -> dict[str, Any] | None:
    ts = now_iso()
    with connect() as conn:
        if tested:
            cursor = conn.execute(
                """
                update data_connections set status = ?, last_tested_at = ?, updated_at = ?
                where id = ? and user_id = ? and project_id = ?
                """,
                (status, ts, ts, connection_id, user_id, project_id),
            )
        else:
            cursor = conn.execute(
                """
                update data_connections set status = ?, updated_at = ?
                where id = ? and user_id = ? and project_id = ?
                """,
                (status, ts, connection_id, user_id, project_id),
            )
        if cursor.rowcount == 0:
            return None
    return get_data_connection(user_id, project_id, connection_id)


def delete_data_connection(user_id: str, project_id: str, connection_id: str) -> bool:
    with connect() as conn:
        linked = conn.execute(
            "select 1 from dataset_sources where connection_id = ? and user_id = ? limit 1",
            (connection_id, user_id),
        ).fetchone()
        if linked:
            raise ValueError("Delete the datasets using this connection first.")
        cursor = conn.execute(
            "delete from data_connections where id = ? and user_id = ? and project_id = ?",
            (connection_id, user_id, project_id),
        )
    return cursor.rowcount > 0


def create_dataset_source(
    user_id: str,
    project_id: str,
    dataset_id: str,
    connection_id: str,
    resource: dict[str, Any],
) -> dict[str, Any]:
    ts = now_iso()
    with connect() as conn:
        conn.execute(
            """
            insert into dataset_sources (
                dataset_id, connection_id, user_id, project_id, access_mode,
                resource_json, created_at, updated_at
            ) values (?, ?, ?, ?, 'federated', ?, ?, ?)
            """,
            (dataset_id, connection_id, user_id, project_id, json.dumps(resource), ts, ts),
        )
    return get_dataset_source(user_id, project_id, dataset_id)  # type: ignore[return-value]


def get_dataset_source(user_id: str, project_id: str, dataset_id: str) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute(
            """
            select * from dataset_sources
            where dataset_id = ? and user_id = ? and project_id = ?
            """,
            (dataset_id, user_id, project_id),
        ).fetchone()
    if row is None:
        return None
    record = dict(row)
    record["resource"] = json.loads(record.pop("resource_json") or "{}")
    return record
