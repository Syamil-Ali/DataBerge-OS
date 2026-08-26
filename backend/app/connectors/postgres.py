from __future__ import annotations

import ipaddress
import re
import socket
from contextlib import contextmanager
from datetime import date, datetime
from decimal import Decimal
from time import perf_counter
from typing import Any, Iterator

from psycopg import connect
from psycopg.rows import dict_row
from psycopg.sql import Identifier, SQL

from app import settings
from app.connectors.contracts import ConnectorCapabilities, ConnectorError, QueryResult


_IDENTIFIER_RE = re.compile(r"^[^\x00]{1,128}$")
_BLOCKED_SQL_RE = re.compile(
    r"\b(insert|update|delete|drop|alter|create|truncate|copy|call|do|grant|revoke|"
    r"vacuum|analyze|refresh|listen|notify|set|reset|show|attach|detach|pragma|install|load|into)\b",
    re.I,
)
_BLOCKED_FUNCTION_RE = re.compile(
    r"\b(pg_sleep|pg_read_file|pg_read_binary_file|pg_ls_dir|dblink|lo_import|lo_export)\s*\(",
    re.I,
)


def _validate_identifier(value: str, label: str) -> str:
    cleaned = value.strip()
    if not _IDENTIFIER_RE.match(cleaned):
        raise ConnectorError(f"Invalid {label} identifier.")
    return cleaned


def _validate_public_host(host: str) -> str:
    normalized = host.strip().rstrip(".").lower()
    if normalized in {"localhost", "localhost.localdomain"}:
        raise ConnectorError("Local and private database hosts are not allowed.")
    try:
        addresses = {item[4][0] for item in socket.getaddrinfo(normalized, None, type=socket.SOCK_STREAM)}
    except socket.gaierror as exc:
        raise ConnectorError("The database host could not be resolved.") from exc
    if not addresses:
        raise ConnectorError("The database host could not be resolved.")
    for address in addresses:
        ip = ipaddress.ip_address(address)
        if not ip.is_global:
            raise ConnectorError("Local and private database hosts are not allowed.")
    return sorted(addresses)[0]


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


def validate_logical_select(sql: str) -> str:
    cleaned = sql.strip().rstrip(";").strip()
    if not cleaned or not re.match(r"^select\b", cleaned, re.I):
        raise ConnectorError("Only a single SELECT query is allowed for federated datasets.")
    if ";" in cleaned or "--" in cleaned or "/*" in cleaned or "*/" in cleaned:
        raise ConnectorError("SQL comments and multiple statements are not allowed.")
    blocked = _BLOCKED_SQL_RE.search(cleaned)
    if blocked:
        raise ConnectorError(f"Query contains a blocked statement: {blocked.group(1).lower()}.")
    if _BLOCKED_FUNCTION_RE.search(cleaned):
        raise ConnectorError("Query contains a blocked PostgreSQL function.")
    if re.search(r"\bjoin\b", cleaned, re.I):
        raise ConnectorError("Federated dataset queries cannot join additional tables yet.")
    if re.search(r"\b(union|intersect|except)\b|\bfor\s+(update|share)\b", cleaned, re.I):
        raise ConnectorError("Set operations and row-locking clauses are not allowed.")
    sources = re.findall(r"\bfrom\s+([^\s,)]+)", cleaned, re.I)
    if not sources or any(source.strip('"').lower() != "dataset" for source in sources):
        raise ConnectorError("Queries may only read from the active federated dataset.")
    if re.search(r"\b(pg_catalog|information_schema)\b", cleaned, re.I):
        raise ConnectorError("System schemas are not available to dataset queries.")
    return cleaned


class PostgresFederatedConnector:
    connector_type = "postgresql"
    capabilities = ConnectorCapabilities()

    @contextmanager
    def _connection(self, config: dict[str, Any], secret: dict[str, str]) -> Iterator[Any]:
        host = str(config.get("host") or "").strip()
        hostaddr = _validate_public_host(host)
        try:
            with connect(
                host=host,
                hostaddr=hostaddr,
                port=int(config.get("port") or 5432),
                dbname=str(config.get("database") or "postgres"),
                user=str(config.get("username") or ""),
                password=str(secret.get("password") or ""),
                sslmode=str(config.get("sslmode") or "require"),
                connect_timeout=settings.FEDERATED_CONNECT_TIMEOUT_SECONDS,
                application_name="data-berge-federated",
                options=(
                    f"-c default_transaction_read_only=on "
                    f"-c statement_timeout={settings.FEDERATED_QUERY_TIMEOUT_MS} "
                    "-c lock_timeout=3000 -c idle_in_transaction_session_timeout=15000"
                ),
                row_factory=dict_row,
            ) as connection:
                yield connection
        except ConnectorError:
            raise
        except Exception as exc:
            raise ConnectorError("The database operation failed. Check the connection, permissions, and query limits.") from exc

    def test_connection(self, config: dict[str, Any], secret: dict[str, str]) -> dict[str, Any]:
        with self._connection(config, secret) as connection:
            row = connection.execute(
                "select current_database() as database_name, current_user as database_user, version() as version"
            ).fetchone()
        return {
            "ok": True,
            "database": row["database_name"],
            "database_user": row["database_user"],
            "engine": "postgresql",
        }

    def discover_schemas(self, config: dict[str, Any], secret: dict[str, str]) -> list[dict[str, Any]]:
        with self._connection(config, secret) as connection:
            rows = connection.execute(
                """
                select schema_name as name
                from information_schema.schemata
                where schema_name not in (
                    'pg_catalog', 'information_schema',
                    'auth', 'extensions', 'graphql', 'graphql_public', 'pgbouncer',
                    'realtime', 'storage', 'supabase_functions', 'vault'
                )
                  and schema_name not like 'pg_toast%'
                  and has_schema_privilege(current_user, schema_name, 'USAGE')
                  and exists (
                      select 1
                      from pg_catalog.pg_class c
                      join pg_catalog.pg_namespace n on n.oid = c.relnamespace
                      where n.nspname = schema_name
                        and c.relkind in ('r', 'p', 'v', 'm')
                        and has_table_privilege(current_user, c.oid, 'SELECT')
                  )
                order by schema_name
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def discover_tables(
        self,
        config: dict[str, Any],
        secret: dict[str, str],
        schema: str,
    ) -> list[dict[str, Any]]:
        schema = _validate_identifier(schema, "schema")
        with self._connection(config, secret) as connection:
            rows = connection.execute(
                """
                select c.relname as name,
                       case c.relkind when 'v' then 'view' when 'm' then 'materialized_view' else 'table' end as kind,
                       greatest(c.reltuples::bigint, 0) as estimated_rows
                from pg_catalog.pg_class c
                join pg_catalog.pg_namespace n on n.oid = c.relnamespace
                where n.nspname = %s
                  and c.relkind in ('r', 'p', 'v', 'm')
                  and has_table_privilege(current_user, c.oid, 'SELECT')
                order by c.relname
                """,
                (schema,),
            ).fetchall()
        return [dict(row) for row in rows]

    def inspect_table(
        self,
        config: dict[str, Any],
        secret: dict[str, str],
        schema: str,
        table: str,
    ) -> dict[str, Any]:
        schema = _validate_identifier(schema, "schema")
        table = _validate_identifier(table, "table")
        with self._connection(config, secret) as connection:
            columns = connection.execute(
                """
                select c.column_name as name, c.data_type,
                       c.udt_name as native_type, c.is_nullable = 'YES' as nullable,
                       c.ordinal_position
                from information_schema.columns c
                where c.table_schema = %s and c.table_name = %s
                order by c.ordinal_position
                """,
                (schema, table),
            ).fetchall()
            if not columns:
                raise ConnectorError("The selected table was not found or is not accessible.")
            estimate = connection.execute(
                """
                select greatest(c.reltuples::bigint, 0) as estimated_rows
                from pg_catalog.pg_class c
                join pg_catalog.pg_namespace n on n.oid = c.relnamespace
                where n.nspname = %s and c.relname = %s
                """,
                (schema, table),
            ).fetchone()
        return {
            "schema": schema,
            "table": table,
            "estimated_rows": int((estimate or {}).get("estimated_rows") or 0),
            "columns": [dict(column) for column in columns],
        }

    def preview(
        self,
        config: dict[str, Any],
        secret: dict[str, str],
        schema: str,
        table: str,
        limit: int,
    ) -> QueryResult:
        schema = _validate_identifier(schema, "schema")
        table = _validate_identifier(table, "table")
        capped = max(1, min(int(limit), settings.FEDERATED_MAX_RESULT_ROWS))
        query = SQL("select * from {}.{} limit %s").format(Identifier(schema), Identifier(table))
        return self._execute(config, secret, query, (capped + 1,), capped)

    def execute_logical_sql(
        self,
        config: dict[str, Any],
        secret: dict[str, str],
        schema: str,
        table: str,
        sql: str,
        limit: int,
    ) -> QueryResult:
        schema = _validate_identifier(schema, "schema")
        table = _validate_identifier(table, "table")
        cleaned = validate_logical_select(sql)
        physical = re.sub(
            r"\bfrom\s+(?:\"dataset\"|dataset)(?=\s|$)",
            lambda _: "from " + Identifier(schema).as_string() + "." + Identifier(table).as_string(),
            cleaned,
            flags=re.I,
        )
        capped = max(1, min(int(limit), settings.FEDERATED_MAX_RESULT_ROWS))
        limited = SQL("select * from ({}) as data_berge_query limit %s").format(SQL(physical))
        return self._execute(config, secret, limited, (capped + 1,), capped)

    def _execute(
        self,
        config: dict[str, Any],
        secret: dict[str, str],
        query: Any,
        params: tuple[Any, ...],
        limit: int,
    ) -> QueryResult:
        started = perf_counter()
        with self._connection(config, secret) as connection:
            cursor = connection.execute(query, params)
            columns = [
                {"name": item.name, "native_type": str(item.type_code)}
                for item in (cursor.description or [])
            ]
            rows = [
                {str(key): _json_scalar(value) for key, value in dict(row).items()}
                for row in cursor.fetchall()
            ]
        truncated = len(rows) > limit
        if truncated:
            rows = rows[:limit]
        return QueryResult(
            columns=columns,
            rows=rows,
            row_count=len(rows),
            truncated=truncated,
            elapsed_ms=int((perf_counter() - started) * 1000),
            warnings=["Result was truncated to the configured row limit."] if truncated else [],
        )
