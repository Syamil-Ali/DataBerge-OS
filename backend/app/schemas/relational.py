"""Pydantic models for the relational schema API."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class RelationshipUpdateRequest(BaseModel):
    """Request body for updating a relational schema's relationships."""

    relationships: list[dict[str, Any]] | None = None
    tables: dict[str, dict[str, Any]] | None = None
    transformations: list[dict[str, Any]] | None = None
    status: str | None = None


class DataDictionaryMappingRequest(BaseModel):
    """Mapping from a workbook sheet into table/column descriptions."""

    sheet_name: str
    column_column: str
    description_column: str
    table_column: str | None = None
    default_table: str | None = None
    manual_targets: dict[str, dict[str, str]] | None = None
