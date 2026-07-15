"""API routes for OpenDOSM data connector.

Flow:
  1. POST /opendosm/connect  → starts background download, returns task_id
  2. GET  /opendosm/status/{task_id}  → poll until done
  3. GET  /opendosm/datasets  → list available datasets
"""
from __future__ import annotations

import threading
import time
import uuid
import hashlib
import re
import shutil
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth.security import get_current_user
from app.services import opendosm
from app.services.relational import build_relational_schema
from app.settings import UPLOAD_DIR
from app.storage import database

router = APIRouter(prefix="/opendosm", tags=["opendosm"])

# ── In-memory task store ────────────────────────────────────────────────
_tasks: dict[str, dict[str, Any]] = {}
_tasks_lock = threading.Lock()

_LOOKUP_URL_RE = re.compile(r"open\.dosm\.gov\.my/data-catalogue/([A-Za-z0-9_-]+)")
_MATCHED_COLUMN_RE = re.compile(r"matched\s+using\s+the\s+['\"]([^'\"]+)['\"]\s+column", re.I)


def _table_name(dataset_id: str) -> str:
    return dataset_id.replace("_", "-")


def _field_descriptions(metadata: dict[str, Any]) -> dict[str, str]:
    return {
        str(field["name"]): str(field["description"])
        for field in metadata.get("fields", [])
        if field.get("name") and field.get("description")
    }


def _relationship_id(from_table: str, from_column: str, to_table: str, to_column: str) -> str:
    raw = f"{from_table}.{from_column}->{to_table}.{to_column}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]


def _lookup_specs_from_metadata(metadata: dict[str, Any]) -> list[dict[str, str]]:
    specs: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()

    for field in metadata.get("fields", []) or []:
        if not isinstance(field, dict):
            continue
        source_column = str(field.get("name") or "").strip()
        description = str(field.get("description") or "")
        if not source_column or not description:
            continue

        target_match = _MATCHED_COLUMN_RE.search(description)
        target_column = target_match.group(1).strip() if target_match else source_column
        for dataset_match in _LOOKUP_URL_RE.finditer(description):
            lookup_id = dataset_match.group(1).strip()
            if not lookup_id:
                continue
            key = (source_column, lookup_id, target_column)
            if key in seen:
                continue
            seen.add(key)
            specs.append({
                "source_column": source_column,
                "lookup_dataset_id": lookup_id,
                "target_column": target_column,
            })

    return specs


def _metadata_relationship(
    from_table: str,
    from_column: str,
    to_table: str,
    to_column: str,
    cardinality: str,
    coverage: float | None = None,
) -> dict[str, Any]:
    rel: dict[str, Any] = {
        "id": _relationship_id(from_table, from_column, to_table, to_column),
        "from_table": from_table,
        "from_column": from_column,
        "to_table": to_table,
        "to_column": to_column,
        "confidence": 0.98,
        "method": "opendosm_metadata_lookup",
        "cardinality": cardinality,
        "active": True,
    }
    if coverage is not None:
        rel["coverage"] = round(float(coverage), 2)
    return rel


def _relationship_coverage(left: Any, right: Any) -> float:
    left_values = set(left.dropna().astype(str))
    if not left_values:
        return 0.0
    right_values = set(right.dropna().astype(str))
    return len(left_values.intersection(right_values)) / len(left_values)


def _is_unique(values: Any) -> bool:
    non_null = values.dropna()
    return bool(len(non_null) > 0 and non_null.nunique(dropna=True) == len(non_null))


def _relationship_cardinality(left: Any, right: Any) -> str:
    from_unique = _is_unique(left)
    to_unique = _is_unique(right)
    if from_unique and to_unique:
        return "one_to_one"
    if to_unique:
        return "many_to_one"
    if from_unique:
        return "one_to_many"
    return "many_to_many"


def _merge_metadata_relationships(schema: dict[str, Any], metadata_relationships: list[dict[str, Any]]) -> None:
    existing = {
        (
            rel.get("from_table"),
            rel.get("from_column"),
            rel.get("to_table"),
            rel.get("to_column"),
        )
        for rel in schema.get("relationships", []) or []
    }
    merged: list[dict[str, Any]] = []
    for rel in metadata_relationships:
        key = (rel["from_table"], rel["from_column"], rel["to_table"], rel["to_column"])
        if key not in existing:
            merged.append(rel)
            existing.add(key)
    schema["relationships"] = merged + list(schema.get("relationships", []) or [])


def _run_connect_task(
    task_id: str,
    user_id: str,
    dataset_id: str,
    project_id: str | None,
    limit: int | None,
) -> None:
    """Background worker: download from API → save CSV → profile → store."""
    try:
        with _tasks_lock:
            _tasks[task_id]["status"] = "downloading"
            _tasks[task_id]["message"] = "Fetching data from OpenDOSM API..."

        df = opendosm.fetch_dataset(dataset_id, limit=limit)
        if df.empty:
            raise ValueError(f"No data returned for dataset '{dataset_id}'")

        # Resolve project
        if not project_id:
            projects = database.list_projects_for_user(user_id)
            if projects:
                project_id = projects[0]["id"]
            else:
                project = database.create_project_for_user(user_id, "OpenDOSM Data")
                project_id = project["id"]

        schema_id = database.new_id()
        ds_name = _table_name(dataset_id)
        dataset_dir = UPLOAD_DIR / schema_id
        dataset_dir.mkdir(parents=True, exist_ok=True)
        source_path = dataset_dir / f"{ds_name}.csv"
        df.to_csv(source_path, index=False)

        total_file_size = source_path.stat().st_size if source_path.exists() else 0
        if not database.check_storage_limit(user_id, total_file_size):
            shutil.rmtree(dataset_dir, ignore_errors=True)
            raise ValueError("Storage limit exceeded. Delete some datasets first (10 MB per user).")

        catalogue_item = next((item for item in opendosm.list_datasets() if item["id"] == dataset_id), None)
        display_name = catalogue_item["name"] if catalogue_item else dataset_id.replace("_", " ").title()
        metadata = opendosm.fetch_metadata(dataset_id)
        tables: dict[str, Any] = {ds_name: df}
        descriptions: dict[str, dict[str, str]] = {ds_name: _field_descriptions(metadata)}
        table_sources: list[dict[str, Any]] = [{
            "table_name": ds_name,
            "dataset_id": dataset_id,
            "title": display_name,
            "description": metadata.get("description", ""),
            "frequency": metadata.get("frequency", ""),
            "data_source": metadata.get("data_source", ""),
            "data_as_of": metadata.get("data_as_of", ""),
            "last_updated": metadata.get("last_updated", ""),
            "source_path": str(source_path),
            "original_filename": f"{ds_name}.csv",
            "role": "primary",
        }]
        metadata_relationships: list[dict[str, Any]] = []
        queued = [(ds_name, dataset_id, df, metadata)]
        visited = {dataset_id}
        while queued:
            source_table, _source_dataset_id, source_df, source_metadata = queued.pop(0)
            for lookup_spec in _lookup_specs_from_metadata(source_metadata):
                lookup_id = lookup_spec["lookup_dataset_id"]
                lookup_table = _table_name(lookup_id)
                source_column = lookup_spec["source_column"]
                target_column = lookup_spec["target_column"]

                if source_column not in source_df.columns:
                    continue
                if lookup_id not in visited:
                    with _tasks_lock:
                        _tasks[task_id]["message"] = f"Fetching lookup table {lookup_id} from OpenDOSM API..."
                    lookup_df = opendosm.fetch_dataset(lookup_id, limit=limit)
                    if lookup_df.empty:
                        visited.add(lookup_id)
                        continue
                    lookup_path = dataset_dir / f"{lookup_table}.csv"
                    lookup_df.to_csv(lookup_path, index=False)
                    lookup_metadata = opendosm.fetch_metadata(lookup_id)
                    tables[lookup_table] = lookup_df
                    descriptions[lookup_table] = _field_descriptions(lookup_metadata)
                    table_sources.append({
                        "table_name": lookup_table,
                        "dataset_id": lookup_id,
                        "title": lookup_metadata.get("title") or lookup_id.replace("_", " ").title(),
                        "description": lookup_metadata.get("description", ""),
                        "frequency": lookup_metadata.get("frequency", ""),
                        "data_source": lookup_metadata.get("data_source", ""),
                        "data_as_of": lookup_metadata.get("data_as_of", ""),
                        "last_updated": lookup_metadata.get("last_updated", ""),
                        "source_path": str(lookup_path),
                        "original_filename": f"{lookup_table}.csv",
                        "role": "lookup",
                    })
                    total_file_size += lookup_path.stat().st_size if lookup_path.exists() else 0
                    if not database.check_storage_limit(user_id, total_file_size):
                        shutil.rmtree(dataset_dir, ignore_errors=True)
                        raise ValueError("Storage limit exceeded. Delete some datasets first (10 MB per user).")
                    visited.add(lookup_id)
                    queued.append((lookup_table, lookup_id, lookup_df, lookup_metadata))

                target_df = tables.get(lookup_table)
                if target_df is None or target_column not in target_df.columns:
                    continue
                metadata_relationships.append(_metadata_relationship(
                    source_table,
                    source_column,
                    lookup_table,
                    target_column,
                    _relationship_cardinality(source_df[source_column], target_df[target_column]),
                    _relationship_coverage(source_df[source_column], target_df[target_column]),
                ))

        root_source = {
            "source_type": "opendosm",
            "file_type": "csv",
            "original_name": f"{ds_name}.csv",
            "source_path": str(source_path),
            "opendosm_dataset_id": dataset_id,
            "opendosm_title": display_name,
            "opendosm_description": metadata.get("description", ""),
            "opendosm_frequency": metadata.get("frequency", ""),
            "opendosm_data_source": metadata.get("data_source", ""),
            "opendosm_data_as_of": metadata.get("data_as_of", ""),
            "opendosm_last_updated": metadata.get("last_updated", ""),
            "opendosm_tables": table_sources,
            "sample_limit": limit,
            "lineage": {
                "read_path": str(source_path),
                "working_path": str(source_path),
                "mode": "opendosm sample" if limit is not None else "opendosm full",
                "refreshable": True,
                "row_limit": limit,
                "lookup_tables": [
                    item["table_name"]
                    for item in table_sources
                    if item.get("role") == "lookup"
                ],
            },
        }
        schema = build_relational_schema(
            tables,
            descriptions,
            source=root_source,
        )
        _merge_metadata_relationships(schema, metadata_relationships)

        record = {
            "id": schema_id,
            "project_id": project_id,
            "name": f"OpenDOSM: {display_name}",
            "original_filename": f"{ds_name}.csv",
            "source_path": str(source_path),
            "schema": schema,
            "status": "draft",
        }
        schema_record = database.create_relational_schema(record, user_id=user_id)
        database.update_user_storage(user_id, total_file_size)

        with _tasks_lock:
            _tasks[task_id]["status"] = "completed"
            _tasks[task_id]["message"] = "Done"
            _tasks[task_id]["schema"] = schema_record

    except Exception as exc:
        with _tasks_lock:
            _tasks[task_id]["status"] = "failed"
            _tasks[task_id]["message"] = str(exc)


# ── Endpoints ───────────────────────────────────────────────────────────


@router.get("/datasets")
def list_datasets(user: dict = Depends(get_current_user)):
    """Return curated list of available OpenDOSM datasets."""
    return opendosm.list_datasets()


class ConnectRequest(BaseModel):
    dataset_id: str
    project_id: str | None = None
    limit: int | None = None


@router.post("/connect")
def connect_dataset(req: ConnectRequest, user: dict = Depends(get_current_user)):
    """Start background download + profile. Returns task_id for polling."""
    user_id = user["id"]

    if not database.check_storage_limit(user_id):
        raise HTTPException(
            status_code=413,
            detail="Storage limit exceeded. Delete some datasets first (10 MB per user).",
        )

    task_id = uuid.uuid4().hex
    with _tasks_lock:
        _tasks[task_id] = {
            "user_id": user_id,
            "status": "pending",
            "message": "Queued",
            "schema": None,
            "created_at": time.time(),
        }

    thread = threading.Thread(
        target=_run_connect_task,
        args=(task_id, user_id, req.dataset_id, req.project_id, req.limit),
        daemon=True,
    )
    thread.start()

    return {"task_id": task_id, "status": "pending"}


@router.get("/status/{task_id}")
def task_status(task_id: str, user: dict = Depends(get_current_user)):
    """Poll to check whether the connect task is done."""
    with _tasks_lock:
        task = _tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.get("user_id") != user["id"]:
        raise HTTPException(status_code=404, detail="Task not found")

    resp: dict[str, Any] = {
        "task_id": task_id,
        "status": task["status"],
        "message": task["message"],
    }
    if task["status"] == "completed" and task.get("schema"):
        resp["schema"] = task["schema"]
    return resp
