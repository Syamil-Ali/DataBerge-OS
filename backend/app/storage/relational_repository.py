from __future__ import annotations

import json
from typing import Any

from app import settings
from app.storage.database import connect, new_id, now_iso
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
    if settings.OBJECT_STORAGE_BACKEND == "s3":
        from app.storage.object_store import materialize_record_paths
        result = materialize_record_paths(result)
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
