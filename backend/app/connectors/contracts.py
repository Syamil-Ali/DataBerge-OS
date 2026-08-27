from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Protocol


class ConnectorError(RuntimeError):
    """A sanitized connector failure that is safe to return to a client."""


def json_scalar(value: Any) -> Any:
    """Convert connector values to stable JSON-safe scalar representations."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, bytes):
        return value.hex()
    return str(value)


@dataclass(frozen=True)
class ConnectorCapabilities:
    schema_discovery: bool = True
    table_discovery: bool = True
    federated_query: bool = True
    materialization: bool = False
    supports_views: bool = True


@dataclass
class QueryResult:
    columns: list[dict[str, Any]]
    rows: list[dict[str, Any]]
    row_count: int
    truncated: bool
    elapsed_ms: int
    warnings: list[str] = field(default_factory=list)


class FederatedConnector(Protocol):
    connector_type: str
    capabilities: ConnectorCapabilities

    def test_connection(self, config: dict[str, Any], secret: dict[str, str]) -> dict[str, Any]: ...
    def discover_schemas(self, config: dict[str, Any], secret: dict[str, str]) -> list[dict[str, Any]]: ...
    def discover_tables(self, config: dict[str, Any], secret: dict[str, str], schema: str) -> list[dict[str, Any]]: ...
    def inspect_table(self, config: dict[str, Any], secret: dict[str, str], schema: str, table: str) -> dict[str, Any]: ...
    def preview(self, config: dict[str, Any], secret: dict[str, str], schema: str, table: str, limit: int) -> QueryResult: ...
    def execute_logical_sql(
        self,
        config: dict[str, Any],
        secret: dict[str, str],
        schema: str,
        table: str,
        sql: str,
        limit: int,
    ) -> QueryResult: ...
