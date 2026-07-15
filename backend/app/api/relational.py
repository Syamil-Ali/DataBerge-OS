"""API endpoints for relational (multi-table) dataset uploads.

Handles:
- POST   /projects/{id}/relational-schemas          Upload multi-sheet Excel or multi-file
- GET    /projects/{id}/relational-schemas          List schemas
- GET    /projects/{id}/relational-schemas/{id}     Get schema detail
- PUT    /projects/{id}/relational-schemas/{id}     Update relationships
- DELETE /projects/{id}/relational-schemas/{id}     Delete schema
"""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

import pandas as pd
import polars as pl
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.auth.security import get_current_user
from app.schemas.relational import DataDictionaryMappingRequest, RelationshipUpdateRequest
from app.services.data_engineering import NULL_LIKE_MARKERS, build_data_engineering_contract
from app.services.files import safe_filename
from app.services.profiling import profile_dataframe
from app.services.relational import (
    apply_data_dictionary_mapping,
    build_relational_schema,
    detect_data_dictionary,
    inspect_data_dictionary_candidates,
    load_tables_from_excel,
    profile_relational_table,
    preview_data_dictionary_mapping,
    read_csv_table,
)
from app.settings import UPLOAD_DIR
from app.storage import database

router = APIRouter(prefix="/projects/{project_id}/relational-schemas", tags=["relational"])


def _schema_for_user(project_id: str, schema_id: str, user_id: str) -> dict[str, Any] | None:
    schema = database.get_relational_schema(schema_id)
    if not schema or schema.get("project_id") != project_id or schema.get("user_id") != user_id:
        return None
    return schema


def _apply_schema_transformations_pandas(
    tables: dict[str, pd.DataFrame], transformations: list[dict[str, Any]] | None,
) -> dict[str, pd.DataFrame]:
    """Apply approved, reversible working-model steps without touching source files."""
    result = {name: frame.copy() for name, frame in tables.items()}
    for step in transformations or []:
        if step.get("status") != "applied":
            continue
        table_name = str(step.get("table") or "")
        table = result.get(table_name)
        if table is None:
            continue
        columns = [str(column) for column in step.get("columns", []) if str(column) in table.columns]
        operation = step.get("operation")
        if operation == "normalize_null_like":
            target_columns = columns or list(table.select_dtypes(include=["object", "string"]).columns)
            for column in target_columns:
                table[column] = table[column].map(
                    lambda value: pd.NA
                    if isinstance(value, str) and value.strip().lower() in NULL_LIKE_MARKERS
                    else value,
                )
        elif operation == "cast_datetime":
            for column in columns:
                table[column] = pd.to_datetime(table[column], errors="coerce")
        elif operation == "trim_text":
            for column in columns:
                table[column] = table[column].map(lambda value: value.strip() if isinstance(value, str) else value)
        elif operation == "lowercase_text":
            for column in columns:
                table[column] = table[column].map(lambda value: value.lower() if isinstance(value, str) else value)
        elif operation == "replace_value":
            find = str((step.get("params") or {}).get("find", ""))
            replacement = str((step.get("params") or {}).get("replacement", ""))
            for column in columns:
                table[column] = table[column].map(
                    lambda value: replacement if str(value) == find else value,
                )
        elif operation == "fill_missing":
            value = str((step.get("params") or {}).get("value", ""))
            for column in columns:
                table[column] = table[column].fillna(value)
    return result


def _apply_schema_transformations(
    tables: dict[str, pd.DataFrame], transformations: list[dict[str, Any]] | None,
) -> dict[str, pd.DataFrame]:
    """Execute the working-model pipeline with Polars' vectorized column engine."""
    try:
        result: dict[str, pd.DataFrame] = {}
        active_steps = [step for step in transformations or [] if step.get("status") == "applied"]
        for table_name, frame in tables.items():
            working = pl.from_pandas(frame).lazy()
            available_columns = set(frame.columns)
            for step in active_steps:
                if str(step.get("table") or "") != table_name:
                    continue
                columns = [str(column) for column in step.get("columns", []) if str(column) in available_columns]
                operation = step.get("operation")
                if operation == "normalize_null_like":
                    columns = columns or [str(column) for column in frame.select_dtypes(include=["object", "string"]).columns]
                    expressions = [
                        pl.when(pl.col(column).cast(pl.Utf8, strict=False).str.strip_chars().str.to_lowercase().is_in(list(NULL_LIKE_MARKERS)))
                        .then(pl.lit(None))
                        .otherwise(pl.col(column))
                        .alias(column)
                        for column in columns
                    ]
                elif operation == "cast_datetime":
                    expressions = [pl.col(column).cast(pl.Utf8, strict=False).str.to_datetime(strict=False).alias(column) for column in columns]
                elif operation == "trim_text":
                    expressions = [pl.col(column).cast(pl.Utf8, strict=False).str.strip_chars().alias(column) for column in columns]
                elif operation == "lowercase_text":
                    expressions = [pl.col(column).cast(pl.Utf8, strict=False).str.to_lowercase().alias(column) for column in columns]
                elif operation == "replace_value":
                    find = str((step.get("params") or {}).get("find", ""))
                    replacement = str((step.get("params") or {}).get("replacement", ""))
                    expressions = [
                        pl.when(pl.col(column).cast(pl.Utf8, strict=False) == find).then(pl.lit(replacement)).otherwise(pl.col(column)).alias(column)
                        for column in columns
                    ]
                elif operation == "fill_missing":
                    value = str((step.get("params") or {}).get("value", ""))
                    expressions = [pl.col(column).fill_null(value).alias(column) for column in columns]
                else:
                    expressions = []
                if expressions:
                    working = working.with_columns(expressions)
            result[table_name] = working.collect().to_pandas()
        return result
    except Exception:
        # Keep the model usable for unusual mixed-type source columns.
        return _apply_schema_transformations_pandas(tables, transformations)


def _working_table_cache_key(schema_record: dict) -> str:
    source_path = Path(str(schema_record.get("source_path") or ""))
    source_state = "missing"
    if source_path.exists():
        stat = source_path.stat()
        source_state = f"{stat.st_mtime_ns}:{stat.st_size}"
    payload = {
        "engine": "polars-v1",
        "source": source_state,
        "transformations": (schema_record.get("schema") or {}).get("transformations") or [],
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode("utf-8")).hexdigest()


def _materialize_working_tables(schema_record: dict, raw_tables: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """Cache the transformed working model as Parquet; source files remain immutable."""
    transformations = (schema_record.get("schema") or {}).get("transformations") or []
    if not any(step.get("status") == "applied" for step in transformations):
        return raw_tables
    source_path = Path(str(schema_record.get("source_path") or ""))
    cache_dir = source_path.parent / ".working-model" / str(schema_record.get("id") or "default")
    manifest_path = cache_dir / "manifest.json"
    cache_key = _working_table_cache_key(schema_record)
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
        table_files = manifest.get("tables", {})
        if manifest.get("cache_key") == cache_key and all((cache_dir / filename).exists() for filename in table_files.values()):
            return {name: pl.read_parquet(cache_dir / filename).to_pandas() for name, filename in table_files.items()}
    except Exception:
        pass

    transformed = _apply_schema_transformations(raw_tables, transformations)
    cache_dir.mkdir(parents=True, exist_ok=True)
    table_files: dict[str, str] = {}
    for index, (name, frame) in enumerate(transformed.items()):
        filename = f"table_{index}.parquet"
        pl.from_pandas(frame).write_parquet(cache_dir / filename, compression="zstd")
        table_files[name] = filename
    manifest_path.write_text(json.dumps({"cache_key": cache_key, "tables": table_files}), encoding="utf-8")
    return transformed


def _prefixed_table(table_name: str, df: pd.DataFrame) -> pd.DataFrame:
    return df.rename(columns={column: f"{table_name}__{column}" for column in df.columns})


def _schema_table_sources(schema_record: dict) -> list[dict[str, Any]]:
    schema_tables = ((schema_record.get("schema") or {}).get("tables") or {})
    for table in schema_tables.values():
        source = table.get("source") or {}
        sources = source.get("opendosm_tables")
        if isinstance(sources, list) and sources:
            return [item for item in sources if isinstance(item, dict)]
    return []


def _load_source_tables(schema_record: dict) -> dict[str, pd.DataFrame]:
    table_sources = _schema_table_sources(schema_record)
    if table_sources:
        tables: dict[str, pd.DataFrame] = {}
        for item in table_sources:
            table_name = str(item.get("table_name") or "").strip()
            table_path = Path(str(item.get("source_path") or ""))
            if table_name and table_path.exists() and table_path.suffix.lower() == ".csv":
                tables[table_name] = read_csv_table(table_path)
        if tables:
            return _materialize_working_tables(schema_record, tables)

    source_path = Path(str(schema_record.get("source_path") or ""))
    suffix = source_path.suffix.lower()
    if suffix == ".csv":
        tables = {Path(str(schema_record.get("original_filename") or source_path.name)).stem or "Data": read_csv_table(source_path)}
        return _materialize_working_tables(schema_record, tables)
    if suffix in {".xlsx", ".xls"}:
        return _materialize_working_tables(schema_record, load_tables_from_excel(source_path))
    return {}


def _json_safe_preview(value: Any) -> Any:
    if pd.isna(value):
        return None
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except Exception:
            pass
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _preview_rows(df: pd.DataFrame, limit: int = 20) -> list[dict[str, Any]]:
    return [
        {str(key): _json_safe_preview(value) for key, value in row.items()}
        for row in df.head(limit).to_dict(orient="records")
    ]


def _json_safe_payload(value: Any) -> Any:
    """Normalize profiling payloads before they are persisted in SQLite JSON columns."""
    return json.loads(json.dumps(value, default=_json_safe_preview))


def _joined_schema_dataframe(schema_record: dict) -> tuple[pd.DataFrame, dict[str, str], list[str]]:
    schema_body = schema_record.get("schema", {})
    table_profiles = schema_body.get("tables", {})
    source_tables = _load_source_tables(schema_record)
    available_tables = {name: df for name, df in source_tables.items() if name in table_profiles}
    if not available_tables:
        return pd.DataFrame(), {}, []

    if len(available_tables) == 1:
        table_name, df = next(iter(available_tables.items()))
        descriptions = {
            str(column.get("name")): str(column.get("description"))
            for column in table_profiles.get(table_name, {}).get("columns", [])
            if column.get("description")
        }
        return df.copy(), descriptions, [table_name]

    base_table = max(available_tables, key=lambda name: len(available_tables[name]))
    joined = _prefixed_table(base_table, available_tables[base_table])
    joined_tables = {base_table}

    relationships = [
        rel for rel in schema_body.get("relationships", [])
        if rel.get("active") is not False
        and rel.get("from_table") in available_tables
        and rel.get("to_table") in available_tables
    ]

    made_progress = True
    while made_progress:
        made_progress = False
        for rel in relationships:
            from_table = str(rel.get("from_table"))
            to_table = str(rel.get("to_table"))
            from_column = str(rel.get("from_column"))
            to_column = str(rel.get("to_column"))

            if from_table in joined_tables and to_table not in joined_tables:
                left_key = f"{from_table}__{from_column}"
                right = _prefixed_table(to_table, available_tables[to_table])
                right_key = f"{to_table}__{to_column}"
                if left_key in joined.columns and right_key in right.columns:
                    joined = joined.merge(right, how="left", left_on=left_key, right_on=right_key)
                    joined_tables.add(to_table)
                    made_progress = True
            elif to_table in joined_tables and from_table not in joined_tables:
                left_key = f"{to_table}__{to_column}"
                right = _prefixed_table(from_table, available_tables[from_table])
                right_key = f"{from_table}__{from_column}"
                if left_key in joined.columns and right_key in right.columns:
                    joined = joined.merge(right, how="left", left_on=left_key, right_on=right_key)
                    joined_tables.add(from_table)
                    made_progress = True

    descriptions: dict[str, str] = {}
    for table_name in joined_tables:
        for column in table_profiles.get(table_name, {}).get("columns", []):
            description = column.get("description")
            if description:
                descriptions[f"{table_name}__{column.get('name')}"] = str(description)
    return joined, descriptions, list(joined_tables)


def _materialize_schema_dataset(
    project_id: str,
    schema_id: str,
    schema_record: dict,
    user_id: str,
    force: bool = False,
) -> None:
    """Create/update the working dataset that powers Explorer/Report for confirmed schemas."""
    existing_dataset = database.get_dataset(schema_id)
    if existing_dataset and not force:
        working_path = Path(str(existing_dataset.get("working_path") or ""))
        if working_path.exists():
            return

    working_df, column_descriptions, joined_tables = _joined_schema_dataframe(schema_record)
    if working_df.empty:
        return

    source_path = str(schema_record.get("source_path") or "")
    file_type = Path(str(schema_record.get("original_filename") or source_path)).suffix.lower().removeprefix(".") or "file"
    working_path = str(Path(source_path).with_suffix(".model.working.csv"))
    working_df.to_csv(working_path, index=False)
    schema_tables = (schema_record.get("schema", {}) or {}).get("tables", {}) or {}
    if len(joined_tables) > 1:
        semantic_overrides = {
            f"{table_name}__{column.get('name')}": str(column.get("semantic_type"))
            for table_name, table in schema_tables.items()
            for column in table.get("columns", [])
            if table_name in joined_tables and column.get("name") and column.get("semantic_type")
        }
    else:
        semantic_overrides = {
            str(column.get("name")): str(column.get("semantic_type"))
            for table_name, table in schema_tables.items()
            for column in table.get("columns", [])
            if table_name in joined_tables and column.get("name") and column.get("semantic_type")
        }
    profile = profile_dataframe(
        working_df,
        column_descriptions=column_descriptions,
        semantic_overrides=semantic_overrides,
    )
    profile["source"] = {
        "source_type": "relational_model",
        "file_type": file_type,
        "original_name": schema_record.get("original_filename"),
        "source_path": source_path,
        "working_path": working_path,
        "lineage": {
            "read_path": source_path,
            "working_path": working_path,
            "mode": "confirmed data model join" if len(joined_tables) > 1 else "confirmed data model",
            "refreshable": False,
            "joined_tables": joined_tables,
        },
    }
    profile["data_engineering"] = build_data_engineering_contract(working_df, profile)
    profile = _json_safe_payload(profile)

    record = {
        "id": schema_id,
        "project_id": project_id,
        "name": f"{schema_record.get('name')} model",
        "original_filename": schema_record.get("original_filename") or Path(source_path).name,
        "file_type": file_type,
        "source_path": source_path,
        "working_path": working_path,
        "row_count": profile["row_count"],
        "column_count": profile["column_count"],
        "status": "profiled",
        "profile": profile,
    }

    if database.get_dataset_for_user(user_id, project_id, schema_id):
        database.delete_dataset_for_user(user_id, project_id, schema_id)
    database.create_dataset_for_user(user_id, record)


@router.get("")
def list_schemas(project_id: str, user: dict = Depends(get_current_user)):
    if not database.get_project_for_user(user["id"], project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    schemas = database.list_relational_schemas(project_id, user_id=user["id"])
    for schema in schemas:
        if schema.get("status") == "confirmed":
            _materialize_schema_dataset(project_id, schema["id"], schema, user["id"])
    return database.list_relational_schemas(project_id, user_id=user["id"])


@router.post("")
def upload_relational(
    project_id: str,
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user),
):
    """Upload a tabular file into the data-model review flow.

    CSV files become a one-table schema. Excel files use each non-empty data
    sheet as a table, while Description/Data Dictionary sheets are parsed as
    column metadata. Relationships are inferred when there are multiple tables.
    """
    if not database.get_project_for_user(user["id"], project_id):
        raise HTTPException(status_code=404, detail="Project not found")

    filename = file.filename or "data.xlsx"
    safe_name = safe_filename(filename)
    suffix = Path(safe_name).suffix.lower()
    if suffix not in {".csv", ".xlsx", ".xls"}:
        raise HTTPException(status_code=400, detail="Only CSV and Excel files are supported.")

    # Save to disk
    schema_id = database.new_id()
    dataset_dir = UPLOAD_DIR / schema_id
    dataset_dir.mkdir(parents=True, exist_ok=True)
    source_path = dataset_dir / safe_name
    with source_path.open("wb") as target:
        shutil.copyfileobj(file.file, target)

    # Load each real data source as a table. Single-table files still enter
    # Data Model so the user can review and confirm the model before Data Pulse.
    try:
        if suffix == ".csv":
            tables = {Path(filename).stem or "Data": read_csv_table(source_path)}
        else:
            tables = load_tables_from_excel(source_path)
    except Exception as exc:
        shutil.rmtree(dataset_dir, ignore_errors=True)
        raise HTTPException(status_code=400, detail=f"Failed to read file: {exc}") from exc

    if not tables:
        shutil.rmtree(dataset_dir, ignore_errors=True)
        raise HTTPException(status_code=400, detail="File contains no data tables.")

    # Detect data dictionary (per-table descriptions)
    all_descriptions = detect_data_dictionary(source_path) if suffix in {".xlsx", ".xls"} else {}

    # Build relational schema (per-table profiles + inferred relationships)
    try:
        schema = build_relational_schema(
            tables,
            all_descriptions,
            source={
                "source_type": "file_upload",
                "file_type": suffix.removeprefix("."),
                "original_name": filename,
                "source_path": str(source_path),
                "lineage": {
                    "read_path": str(source_path),
                    "working_path": str(source_path),
                    "mode": "uploaded file",
                    "refreshable": False,
                },
            },
        )
    except Exception as exc:
        shutil.rmtree(dataset_dir, ignore_errors=True)
        raise HTTPException(status_code=500, detail=f"Schema build failed: {exc}") from exc

    # Store in database
    record = {
        "project_id": project_id,
        "name": Path(filename).stem,
        "original_filename": filename,
        "source_path": str(source_path),
        "schema": schema,
        "status": "draft",
    }
    result = database.create_relational_schema(record, user_id=user["id"])
    return result


@router.get("/{schema_id}")
def get_schema(project_id: str, schema_id: str, user: dict = Depends(get_current_user)):
    schema = _schema_for_user(project_id, schema_id, user["id"])
    if not schema:
        raise HTTPException(status_code=404, detail="Schema not found")
    if schema.get("status") == "confirmed":
        _materialize_schema_dataset(project_id, schema_id, schema, user["id"])
        schema = database.get_relational_schema(schema_id)
    return schema


@router.get("/{schema_id}/tables/{table_name}/preview")
def table_preview(project_id: str, schema_id: str, table_name: str, user: dict = Depends(get_current_user)):
    schema = _schema_for_user(project_id, schema_id, user["id"])
    if not schema:
        raise HTTPException(status_code=404, detail="Schema not found")
    source_tables = _load_source_tables(schema)
    if table_name not in source_tables:
        raise HTTPException(status_code=404, detail="Table not found")
    table = (schema.get("schema", {}) or {}).get("tables", {}).get(table_name)
    if not table:
        raise HTTPException(status_code=404, detail="Table profile not found")
    return {
        "table_name": table_name,
        "columns": table.get("columns", []),
        "rows": _preview_rows(source_tables[table_name]),
        "row_count": int(len(source_tables[table_name])),
    }


@router.get("/{schema_id}/dictionary-candidates")
def dictionary_candidates(project_id: str, schema_id: str, user: dict = Depends(get_current_user)):
    schema = _schema_for_user(project_id, schema_id, user["id"])
    if not schema:
        raise HTTPException(status_code=404, detail="Schema not found")
    try:
        return inspect_data_dictionary_candidates(schema["source_path"])
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to inspect workbook: {exc}") from exc


@router.post("/{schema_id}/dictionary-preview")
def dictionary_preview(
    project_id: str,
    schema_id: str,
    body: DataDictionaryMappingRequest,
    user: dict = Depends(get_current_user),
):
    schema_record = _schema_for_user(project_id, schema_id, user["id"])
    if not schema_record:
        raise HTTPException(status_code=404, detail="Schema not found")
    try:
        return preview_data_dictionary_mapping(
            schema_record.get("schema", {}),
            schema_record["source_path"],
            body.model_dump(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to preview dictionary mapping: {exc}") from exc


@router.post("/{schema_id}/dictionary-apply")
def dictionary_apply(
    project_id: str,
    schema_id: str,
    body: DataDictionaryMappingRequest,
    user: dict = Depends(get_current_user),
):
    schema_record = _schema_for_user(project_id, schema_id, user["id"])
    if not schema_record:
        raise HTTPException(status_code=404, detail="Schema not found")
    try:
        updated_schema, preview = apply_data_dictionary_mapping(
            schema_record.get("schema", {}),
            schema_record["source_path"],
            body.model_dump(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to apply dictionary mapping: {exc}") from exc

    result = database.update_relational_schema(schema_id, updated_schema)
    return {"schema": result, "preview": preview}


@router.put("/{schema_id}")
def update_relationships(
    project_id: str,
    schema_id: str,
    body: RelationshipUpdateRequest,
    user: dict = Depends(get_current_user),
):
    """Update the confirmed relationships and table metadata."""
    schema = _schema_for_user(project_id, schema_id, user["id"])
    if not schema:
        raise HTTPException(status_code=404, detail="Schema not found")

    current = schema.get("schema", {})
    if body.relationships is not None:
        current["relationships"] = body.relationships
    if body.tables is not None:
        source_tables = _load_source_tables(schema)
        for tname, updates in body.tables.items():
            if tname in current.get("tables", {}):
                if "columns" in updates and tname in source_tables:
                    updated_columns = updates.get("columns") or []
                    semantic_overrides = {
                        str(column.get("name")): str(column.get("semantic_type"))
                        for column in updated_columns
                        if column.get("name") and column.get("semantic_type")
                    }
                    current["tables"][tname] = profile_relational_table(
                        tname,
                        source_tables[tname],
                        description_map=current.get("description_map", {}) or {},
                        source=current.get("tables", {}).get(tname, {}).get("source"),
                        semantic_overrides=semantic_overrides,
                    )
                else:
                    current["tables"][tname].update(updates)
    if body.transformations is not None:
        current["transformations"] = body.transformations
        source_tables = _load_source_tables({**schema, "schema": current})
        for table_name, table in current.get("tables", {}).items():
            if table_name in source_tables:
                semantic_overrides = {
                    str(column.get("name")): str(column.get("semantic_type"))
                    for column in table.get("columns", [])
                    if column.get("name") and column.get("semantic_type")
                }
                for step in current["transformations"]:
                    if (
                        step.get("status") == "applied"
                        and step.get("operation") == "cast_datetime"
                        and step.get("table") == table_name
                    ):
                        semantic_overrides.update({str(column): "datetime" for column in step.get("columns", [])})
                current["tables"][table_name] = _json_safe_payload(profile_relational_table(
                    table_name,
                    source_tables[table_name],
                    description_map=current.get("description_map", {}) or {},
                    source=table.get("source"),
                    semantic_overrides=semantic_overrides,
                ))
    if body.status is not None:
        schema["status"] = body.status

    result = database.update_relational_schema(schema_id, current)
    if result and body.status:
        with database.connect() as conn:
            conn.execute(
                "update relational_schemas set status = ? where id = ?",
                (body.status, schema_id),
            )
        result = database.get_relational_schema(schema_id)
    if result and (
        body.status == "confirmed"
        or ((body.tables is not None or body.transformations is not None) and result.get("status") in {"confirmed", "active"})
    ):
        _materialize_schema_dataset(project_id, schema_id, result, user["id"], force=True)
        result = database.get_relational_schema(schema_id)
    return result


@router.delete("/{schema_id}")
def delete_schema(project_id: str, schema_id: str, user: dict = Depends(get_current_user)):
    schema = _schema_for_user(project_id, schema_id, user["id"])
    if not schema:
        raise HTTPException(status_code=404, detail="Schema not found")
    result = database.delete_relational_schema(project_id, schema_id)
    if database.get_dataset_for_user(user["id"], project_id, schema_id):
        database.delete_dataset_for_user(user["id"], project_id, schema_id)
    # Clean up files
    source_path = Path(str(schema.get("source_path", ""))).resolve()
    upload_root = UPLOAD_DIR.resolve()
    try:
        source_path.relative_to(upload_root)
        dataset_dir = source_path.parent
        if dataset_dir != upload_root:
            shutil.rmtree(dataset_dir, ignore_errors=True)
    except ValueError:
        pass
    return {"deleted": True, "schema_id": schema_id}
