from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

import pandas as pd

from app import settings
from app.connectors import get_federated_connector
from app.connectors.contracts import QueryResult
from app.connectors.secrets import decrypt_connector_secret
from app.services.profiling import profile_dataframe
from app.storage import database


_NUMERIC_TYPES = {
    "smallint", "integer", "bigint", "decimal", "numeric", "real", "double precision",
    "smallserial", "serial", "bigserial", "int2", "int4", "int8", "float4", "float8",
}
_TEMPORAL_TYPES = {
    "date", "timestamp", "timestamp without time zone", "timestamp with time zone", "time",
}


def public_connection(record: dict[str, Any]) -> dict[str, Any]:
    safe = dict(record)
    safe.pop("encrypted_secret", None)
    return safe


def connection_runtime(user_id: str, project_id: str, connection_id: str):
    record = database.get_data_connection(
        user_id,
        project_id,
        connection_id,
        include_secret=True,
    )
    if not record:
        raise ValueError("Connection not found")
    connector = get_federated_connector(str(record["connector_type"]))
    secret = decrypt_connector_secret(str(record["encrypted_secret"]))
    return record, connector, secret


def _json_scalar(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, bytes):
        return value.hex()
    return str(value)


def serialize_query_result(result: QueryResult) -> dict[str, Any]:
    return {
        "columns": result.columns,
        "rows": [
            {str(key): _json_scalar(value) for key, value in row.items()}
            for row in result.rows
        ],
        "row_count": result.row_count,
        "truncated": result.truncated,
        "elapsed_ms": result.elapsed_ms,
        "warnings": result.warnings,
    }


def build_federated_profile(
    connector: Any,
    config: dict[str, Any],
    secret: dict[str, str],
    *,
    connection_id: str,
    provider: str,
    schema: str,
    table: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    inspected = connector.inspect_table(config, secret, schema, table)
    preview = connector.preview(config, secret, schema, table, settings.FEDERATED_PREVIEW_ROWS)
    safe_rows = serialize_query_result(preview)["rows"]
    frame = pd.DataFrame(safe_rows, columns=[column["name"] for column in inspected["columns"]])
    overrides: dict[str, str] = {}
    native_types: dict[str, str] = {}
    for column in inspected["columns"]:
        name = str(column["name"])
        native = str(column.get("data_type") or column.get("native_type") or "").lower()
        native_types[name] = native
        if native in _NUMERIC_TYPES:
            overrides[name] = "numeric"
            frame[name] = pd.to_numeric(frame[name], errors="coerce")
        elif native in _TEMPORAL_TYPES:
            overrides[name] = "datetime"

    table_profile = profile_dataframe(frame, semantic_overrides=overrides)
    for column in table_profile.get("columns", []):
        column["native_type"] = native_types.get(str(column.get("name")), "")
    estimated_rows = int(inspected.get("estimated_rows") or 0)
    table_profile["row_count"] = estimated_rows
    table_profile["profile_scope"] = {
        "mode": "sampled",
        "sample_rows": len(frame),
        "row_count_is_estimate": True,
    }
    table_profile["quality_flags"] = [
        "Federated profile statistics are based on a bounded preview; the row count is a database estimate.",
        *table_profile.get("quality_flags", []),
    ]
    table_profile["source"] = {
        "source_type": provider,
        "file_type": "remote_table",
        "access_mode": "federated",
        "connection_id": connection_id,
        "resource": {"schema": schema, "table": table},
        "lineage": {
            "mode": "federated query",
            "refreshable": True,
            "materialized": False,
        },
    }
    profile = {
        "tables": {table: table_profile},
        "relationships": [],
        "description_map": {},
        "source": table_profile["source"],
    }
    return profile, inspected


def register_federated_dataset(
    user_id: str,
    project_id: str,
    *,
    connection_id: str,
    schema: str,
    table: str,
    name: str | None = None,
) -> dict[str, Any]:
    connection, connector, secret = connection_runtime(user_id, project_id, connection_id)
    profile, inspected = build_federated_profile(
        connector,
        connection["config"],
        secret,
        connection_id=connection_id,
        provider=str(connection["provider"]),
        schema=schema,
        table=table,
    )
    dataset_id = database.new_id()
    uri = f"federated://{connection_id}/{schema}/{table}"
    record = {
        "id": dataset_id,
        "project_id": project_id,
        "name": name or table,
        "original_filename": f"{schema}.{table}",
        "file_type": "remote_table",
        "source_path": uri,
        "working_path": uri,
        "row_count": int(inspected.get("estimated_rows") or 0),
        "column_count": len(inspected.get("columns") or []),
        "status": "federated",
        "profile": profile,
    }
    dataset = database.create_dataset_for_user(user_id, record)
    try:
        database.create_dataset_source(
            user_id,
            project_id,
            dataset_id,
            connection_id,
            {"schema": schema, "table": table},
        )
    except Exception:
        database.delete_dataset_for_user(user_id, project_id, dataset_id)
        raise
    return dataset


def execute_dataset_sql(
    user_id: str,
    project_id: str,
    dataset_id: str,
    sql: str,
    limit: int,
) -> QueryResult:
    source = database.get_dataset_source(user_id, project_id, dataset_id)
    if not source:
        raise ValueError("Federated dataset source not found")
    connection, connector, secret = connection_runtime(
        user_id,
        project_id,
        str(source["connection_id"]),
    )
    resource = source["resource"]
    return connector.execute_logical_sql(
        connection["config"],
        secret,
        str(resource["schema"]),
        str(resource["table"]),
        sql,
        limit,
    )
