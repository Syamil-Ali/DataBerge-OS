from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


def get_flat_profile(profile: dict[str, Any]) -> dict[str, Any]:
    """Extract a flat single-table profile from either format.

    Unified format: profile = {"tables": {"name": {columns, metadata, ...}}, "relationships": [...]}
    Legacy format:  profile = {"columns": [...], "metadata": {...}, ...}

    Returns the flat profile dict for the first (or only) table.
    """
    tables = profile.get("tables")
    if tables and isinstance(tables, dict):
        first_key = next(iter(tables), None)
        if first_key is not None:
            return tables[first_key]
    return profile


def normalize_top_values(value: Any) -> list[dict[str, Any]]:
    """Return profile top values in the canonical [{label, count}] shape."""
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if isinstance(value, dict):
        return [
            {"label": str(label), "count": count}
            for label, count in value.items()
        ]
    return []


@dataclass
class DatasetContext:
    dataset_id: str
    project_id: str
    name: str
    original_filename: str
    file_type: str
    source_path: str
    working_path: str
    row_count: int
    column_count: int
    status: str
    profile: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""

    @classmethod
    def from_record(cls, record: dict[str, Any]) -> "DatasetContext":
        return cls(
            dataset_id=str(record.get("id") or record.get("dataset_id") or ""),
            project_id=str(record.get("project_id") or ""),
            name=str(record.get("name") or ""),
            original_filename=str(record.get("original_filename") or ""),
            file_type=str(record.get("file_type") or ""),
            source_path=str(record.get("source_path") or ""),
            working_path=str(record.get("working_path") or ""),
            row_count=int(record.get("row_count") or 0),
            column_count=int(record.get("column_count") or 0),
            status=str(record.get("status") or ""),
            profile=dict(record.get("profile") or {}),
            created_at=str(record.get("created_at") or ""),
            updated_at=str(record.get("updated_at") or ""),
        )

    def to_record(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["id"] = payload.pop("dataset_id")
        return payload
