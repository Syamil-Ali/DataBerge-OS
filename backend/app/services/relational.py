"""Multi-table dataset ingestion and relationship inference.

Handles:
- Multi-sheet Excel files, where each sheet becomes a table.
- Automatic relationship inference from PK/FK labels, names, and value coverage.
- Data dictionary / description sheet detection.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

import pandas as pd
import polars as pl
import fastexcel

from app.services.data_engineering import build_data_engineering_contract
from app.services.profiling import profile_dataframe


_NUMERIC_TYPES = {"BIGINT", "INTEGER", "DOUBLE", "FLOAT", "SMALLINT", "TINYINT", "HUGEINT", "DECIMAL", "NUMERIC"}
_DESCRIPTION_SHEET_NAMES = {"data dictionary", "description", "metadata", "dictionary", "schema"}
_ID_COLUMN_NAMES = {"id", "key", "pk"}
_TABLE_COLUMN_CANDIDATES = {"sheet", "table", "table name", "worksheet", "entity", "dataset"}
_FIELD_COLUMN_CANDIDATES = {"column", "columns", "field", "field name", "column name", "attribute"}
_DESCRIPTION_COLUMN_CANDIDATES = {"description", "meaning", "definition", "comment", "desc", "business definition"}


def _polars_to_pandas(df: pl.DataFrame) -> pd.DataFrame:
    return df.to_pandas()


def read_csv_table(path: str | Path) -> pd.DataFrame:
    return _polars_to_pandas(pl.read_csv(path))


def _read_excel_sheet(path: str | Path, sheet_name: str, n_rows: int | None = None) -> pl.DataFrame:
    read_options = {"n_rows": n_rows} if n_rows is not None else None
    return pl.read_excel(
        path,
        sheet_name=sheet_name,
        engine="calamine",
        read_options=read_options,
    )


def _read_excel_sheet_text(path: str | Path, sheet_name: str, n_rows: int | None = None) -> pl.DataFrame:
    df = _read_excel_sheet(path, sheet_name, n_rows=n_rows)
    if df.is_empty():
        return df
    return df.with_columns(pl.all().cast(pl.Utf8, strict=False))


def _excel_reader(path: str | Path) -> fastexcel.ExcelReader:
    return fastexcel.read_excel(str(path))


def _strip_key_suffix(name: str) -> tuple[str, str]:
    """Return (clean_name, key_type) from names like 'CustomerID (PK)'."""
    match = re.match(r"^(.+?)\s*\(?(PK|FK|pk|fk)\)?$", name.strip())
    if match:
        return match.group(1), match.group(2).upper()
    return name.strip(), ""


def _normalise_col_name(name: str) -> str:
    clean, _ = _strip_key_suffix(name)
    clean = clean.lower().replace(" ", "_")
    for suffix in ("_id", "_key", "id", "key"):
        if clean.endswith(suffix) and len(clean) > len(suffix):
            return clean[: -len(suffix)]
    return clean


def _normalise_identifier(name: str) -> str:
    clean = re.sub(r"[^a-zA-Z0-9]+", "_", str(name).lower()).strip("_")
    for suffix in ("_table", "_sheet", "s"):
        if clean.endswith(suffix) and len(clean) > len(suffix):
            clean = clean[: -len(suffix)]
    return clean


def _normalise_header(name: str) -> str:
    return re.sub(r"\s+", " ", str(name).strip().lower())


def _guess_column(columns: list[str], candidates: set[str]) -> str | None:
    lookup = {_normalise_header(column): column for column in columns}
    for candidate in candidates:
        if candidate in lookup:
            return lookup[candidate]
    for normalised, original in lookup.items():
        if any(candidate in normalised for candidate in candidates):
            return original
    return None


def _json_safe(value: Any) -> Any:
    if pd.isna(value):
        return None
    return str(value)


def _relationship_id(from_table: str, from_column: str, to_table: str, to_column: str) -> str:
    raw = f"{from_table}.{from_column}->{to_table}.{to_column}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]


def _is_unique(df: pd.DataFrame, column: str) -> bool:
    values = df[column].dropna()
    return bool(len(values) > 0 and values.nunique(dropna=True) == len(values))


def _value_coverage(left: pd.Series, right: pd.Series) -> float:
    left_values = set(left.dropna().astype(str))
    if not left_values:
        return 0.0
    right_values = set(right.dropna().astype(str))
    return len(left_values.intersection(right_values)) / len(left_values)


def _cardinality(from_unique: bool, to_unique: bool) -> str:
    if from_unique and to_unique:
        return "one_to_one"
    if to_unique:
        return "many_to_one"
    if from_unique:
        return "one_to_many"
    return "many_to_many"


def _relationship(
    from_table: str,
    from_column: str,
    to_table: str,
    to_column: str,
    confidence: float,
    method: str,
    cardinality: str,
) -> dict[str, Any]:
    return {
        "id": _relationship_id(from_table, from_column, to_table, to_column),
        "from_table": from_table,
        "from_column": from_column,
        "to_table": to_table,
        "to_column": to_column,
        "confidence": round(float(confidence), 2),
        "method": method,
        "cardinality": cardinality,
        "active": True,
    }


def _add_relationship(
    relationships: list[dict[str, Any]],
    seen: set[tuple[str, str, str, str]],
    rel: dict[str, Any],
) -> None:
    key = (rel["from_table"], rel["from_column"], rel["to_table"], rel["to_column"])
    reverse = (rel["to_table"], rel["to_column"], rel["from_table"], rel["from_column"])
    if key in seen or reverse in seen:
        return
    seen.add(key)
    relationships.append(rel)


def infer_relationships(tables: dict[str, pd.DataFrame]) -> list[dict[str, Any]]:
    """Infer foreign-key relationships between tables."""
    relationships: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()
    col_index: dict[str, list[tuple[str, str]]] = {}
    table_names = {_normalise_identifier(tname): tname for tname in tables}
    column_uniqueness: dict[tuple[str, str], bool] = {}
    column_key_types: dict[tuple[str, str], str] = {}

    for tname, df in tables.items():
        for col in df.columns:
            _clean, key_type = _strip_key_suffix(col)
            col_index.setdefault(_normalise_col_name(col), []).append((tname, col))
            column_uniqueness[(tname, col)] = _is_unique(df, col)
            column_key_types[(tname, col)] = key_type

    # Explicit labels such as CustomerID (PK) and CustomerID (FK).
    for tname, df in tables.items():
        for col in df.columns:
            clean, key_type = _strip_key_suffix(col)
            if key_type != "FK":
                continue
            pk_norm = _normalise_col_name(clean)
            for candidate_table, candidate_col in col_index.get(pk_norm, []):
                if candidate_table == tname:
                    continue
                _add_relationship(
                    relationships,
                    seen,
                    _relationship(
                        tname,
                        col,
                        candidate_table,
                        candidate_col,
                        0.95,
                        "explicit_pk_fk_annotation",
                        "many_to_one" if column_key_types[(candidate_table, candidate_col)] == "PK" else _cardinality(
                            column_uniqueness[(tname, col)],
                            column_uniqueness[(candidate_table, candidate_col)],
                        ),
                    ),
                )

    # Same normalized column names across tables, with direction based on uniqueness.
    for _norm_name, entries in col_index.items():
        if len({table for table, _ in entries}) < 2:
            continue
        for i, (t1, c1) in enumerate(entries):
            for t2, c2 in entries[i + 1 :]:
                if t1 == t2:
                    continue
                c1_unique = column_uniqueness[(t1, c1)]
                c2_unique = column_uniqueness[(t2, c2)]
                c1_key = column_key_types[(t1, c1)]
                c2_key = column_key_types[(t2, c2)]
                if c1_key == "FK" and c2_key == "PK":
                    from_table, from_col, to_table, to_col = t1, c1, t2, c2
                elif c2_key == "FK" and c1_key == "PK":
                    from_table, from_col, to_table, to_col = t2, c2, t1, c1
                elif c1_unique and not c2_unique:
                    from_table, from_col, to_table, to_col = t2, c2, t1, c1
                else:
                    from_table, from_col, to_table, to_col = t1, c1, t2, c2
                from_key = column_key_types[(from_table, from_col)]
                to_key = column_key_types[(to_table, to_col)]
                confidence = 0.75 if "id" in c1.lower() or "id" in c2.lower() else 0.55
                _add_relationship(
                    relationships,
                    seen,
                    _relationship(
                        from_table,
                        from_col,
                        to_table,
                        to_col,
                        confidence,
                        "name_match_id" if confidence >= 0.75 else "name_match",
                        "many_to_one" if from_key == "FK" and to_key == "PK" else _cardinality(
                            column_uniqueness[(from_table, from_col)],
                            column_uniqueness[(to_table, to_col)],
                        ),
                    ),
                )

    # Table-name FK pattern, e.g. Order.CustomerID -> Customer.CustomerID.
    for source_table, source_df in tables.items():
        for source_col in source_df.columns:
            source_norm = _normalise_col_name(source_col)
            for target_norm, target_table in table_names.items():
                if target_table == source_table or source_norm != target_norm:
                    continue
                target_df = tables[target_table]
                for target_col in target_df.columns:
                    target_col_norm = _normalise_col_name(target_col)
                    target_col_clean, target_key_type = _strip_key_suffix(target_col)
                    target_is_id = (
                        target_col_norm in {target_norm, "id"}
                        or target_col_clean.lower() in _ID_COLUMN_NAMES
                        or target_key_type == "PK"
                    )
                    if not target_is_id:
                        continue
                    coverage = _value_coverage(source_df[source_col], target_df[target_col])
                    if coverage < 0.5:
                        continue
                    _add_relationship(
                        relationships,
                        seen,
                        _relationship(
                            source_table,
                            source_col,
                            target_table,
                            target_col,
                            0.9 if coverage >= 0.9 else 0.7,
                            "table_name_value_coverage",
                            "many_to_one" if target_key_type == "PK" else _cardinality(
                                column_uniqueness[(source_table, source_col)],
                                column_uniqueness[(target_table, target_col)],
                            ),
                        ),
                    )

    # Refine every candidate with actual value coverage.
    for rel in relationships:
        left = tables[rel["from_table"]][rel["from_column"]]
        right = tables[rel["to_table"]][rel["to_column"]]
        coverage = _value_coverage(left, right)
        rel["coverage"] = round(coverage, 2)
        if coverage >= 0.9:
            rel["confidence"] = max(rel["confidence"], 0.9 if rel["method"].startswith("explicit") else 0.85)
            if not rel["method"].startswith("explicit"):
                rel["method"] = "value_coverage"
        elif coverage < 0.5 and rel["confidence"] < 0.9:
            rel["confidence"] = min(rel["confidence"], 0.35)

    relationships = [rel for rel in relationships if rel["confidence"] >= 0.5]
    relationships.sort(key=lambda r: r["confidence"], reverse=True)
    return relationships


def load_tables_from_excel(file_path: str | Path) -> dict[str, pd.DataFrame]:
    """Load every non-empty data sheet from an Excel file as a table."""
    path = Path(file_path)
    workbook = _excel_reader(path)
    result: dict[str, pd.DataFrame] = {}
    for name in workbook.sheet_names:
        if name.lower().strip() in _DESCRIPTION_SHEET_NAMES:
            continue
        sheet = workbook.load_sheet_by_name(name, schema_sample_rows=1000)
        if sheet.height == 0:
            continue
        df = sheet.to_polars()
        if not df.is_empty():
            result[name] = _polars_to_pandas(df)
    return result




def detect_data_dictionary(file_path: str | Path) -> dict[str, dict[str, str]]:
    """Detect and parse a Data Dictionary / Description sheet.

    Returns table_name -> column_name -> description. If the sheet does not
    include a table/sheet column, descriptions are stored under "__all__".
    """
    path = Path(file_path)
    try:
        workbook = _excel_reader(path)
    except Exception:
        return {}

    description_sheet = None
    for sheet in workbook.sheet_names:
        if sheet.lower().strip() in _DESCRIPTION_SHEET_NAMES:
            description_sheet = sheet
            break
    if not description_sheet:
        return {}

    try:
        df = _read_excel_sheet_text(path, description_sheet)
    except Exception:
        return {}
    if df.is_empty():
        return {}

    header_lookup = {str(c).strip().lower(): c for c in df.columns}
    table_key = header_lookup.get("sheet") or header_lookup.get("table") or header_lookup.get("table name")
    column_key = (
        header_lookup.get("column")
        or header_lookup.get("columns")
        or header_lookup.get("field")
        or header_lookup.get("column name")
    )
    description_key = (
        header_lookup.get("description")
        or header_lookup.get("meaning")
        or header_lookup.get("definition")
        or header_lookup.get("comment")
    )
    if not column_key or not description_key:
        return {}

    result: dict[str, dict[str, str]] = {}
    required_cols = [column_key, description_key] + ([table_key] if table_key else [])
    for row in df.select(required_cols).iter_rows(named=True):
        col_name = str(row.get(column_key) or "").strip()
        desc = str(row.get(description_key) or "").strip()
        if not col_name or not desc or desc.lower() == "nan":
            continue
        table_name = str(row.get(table_key) or "").strip() if table_key else "__all__"
        if not table_name or table_name.lower() == "nan":
            table_name = "__all__"
        result.setdefault(table_name, {})[col_name] = desc
    return result


def inspect_data_dictionary_candidates(file_path: str | Path) -> dict[str, Any]:
    """Return workbook sheets, columns, samples, and best-guess dictionary mappings."""
    path = Path(file_path)
    if path.suffix.lower() not in {".xlsx", ".xls"}:
        return {"sheets": [], "preferred_sheet": None}

    workbook = _excel_reader(path)
    sheets: list[dict[str, Any]] = []

    for sheet_name in workbook.sheet_names:
        try:
            sheet = workbook.load_sheet_by_name(sheet_name, n_rows=8, schema_sample_rows=8)
            df = sheet.to_polars().with_columns(pl.all().cast(pl.Utf8, strict=False))
        except Exception:
            continue
        columns = [str(column) for column in df.columns]
        table_guess = _guess_column(columns, _TABLE_COLUMN_CANDIDATES)
        field_guess = _guess_column(columns, _FIELD_COLUMN_CANDIDATES)
        description_guess = _guess_column(columns, _DESCRIPTION_COLUMN_CANDIDATES)
        is_dictionary_like = bool(field_guess and description_guess)
        sample_rows = [
            {str(column): _json_safe(value) for column, value in row.items()}
            for row in df.head(8).to_dicts()
        ]
        sheets.append(
            {
                "name": sheet_name,
                "columns": columns,
                "row_count": _excel_sheet_row_count(workbook, sheet_name) or int(df.height),
                "sample_rows": sample_rows,
                "guesses": {
                    "table_column": table_guess,
                    "column_column": field_guess,
                    "description_column": description_guess,
                },
                "is_dictionary_like": is_dictionary_like,
            }
        )

    preferred = next((sheet for sheet in sheets if sheet["is_dictionary_like"]), sheets[0] if sheets else None)
    return {"sheets": sheets, "preferred_sheet": preferred["name"] if preferred else None}


def _excel_sheet_row_count(workbook: fastexcel.ExcelReader, sheet_name: str) -> int | None:
    """Return an approximate data-row count from workbook metadata without reading the full sheet."""
    try:
        sheet = workbook.load_sheet_by_name(sheet_name, n_rows=0)
        return max(0, int(sheet.total_height))
    except Exception:
        return None


def _schema_table_lookup(schema: dict[str, Any]) -> dict[str, str]:
    return {_normalise_identifier(name): name for name in schema.get("tables", {})}


def _schema_column_lookup(schema: dict[str, Any], table_name: str) -> dict[str, str]:
    table = schema.get("tables", {}).get(table_name, {})
    result: dict[str, str] = {}
    for column in table.get("columns", []):
        name = str(column.get("name", ""))
        clean_name = str(column.get("clean_name") or name)
        result[_normalise_identifier(name)] = name
        result[_normalise_identifier(clean_name)] = name
    return result


def _resolve_description_target(
    schema: dict[str, Any],
    raw_table: str | None,
    raw_column: str,
    default_table: str | None = None,
) -> tuple[str | None, str | None, str, str]:
    tables = schema.get("tables", {})
    table_lookup = _schema_table_lookup(schema)
    table_name: str | None = None

    if raw_table:
        table_name = table_lookup.get(_normalise_identifier(raw_table))
        if not table_name:
            return None, None, "unmatched", f'Table "{raw_table}" was not found.'
    elif default_table:
        table_name = table_lookup.get(_normalise_identifier(default_table))
        if not table_name:
            return None, None, "unmatched", f'Default table "{default_table}" was not found.'
    elif len(tables) == 1:
        table_name = next(iter(tables))

    if table_name:
        column_lookup = _schema_column_lookup(schema, table_name)
        column_name = column_lookup.get(_normalise_identifier(raw_column))
        if column_name:
            return table_name, column_name, "matched", ""
        return table_name, None, "unmatched", f'Column "{raw_column}" was not found in {table_name}.'

    matches: list[tuple[str, str]] = []
    for candidate_table in tables:
        column_lookup = _schema_column_lookup(schema, candidate_table)
        column_name = column_lookup.get(_normalise_identifier(raw_column))
        if column_name:
            matches.append((candidate_table, column_name))

    if len(matches) == 1:
        return matches[0][0], matches[0][1], "matched", ""
    if len(matches) > 1:
        return None, None, "ambiguous", f'Column "{raw_column}" appears in {len(matches)} tables. Choose a table column.'
    return None, None, "unmatched", f'Column "{raw_column}" was not found.'


def _resolve_manual_target(
    schema: dict[str, Any],
    target: dict[str, str] | None,
) -> tuple[str | None, str | None, str, str]:
    if not target:
        return None, None, "unmatched", ""
    raw_table = target.get("table")
    raw_column = target.get("column")
    if not raw_table or not raw_column:
        return None, None, "unmatched", ""

    table_lookup = _schema_table_lookup(schema)
    table_name = table_lookup.get(_normalise_identifier(raw_table))
    if not table_name:
        return None, None, "unmatched", f'Manual table "{raw_table}" was not found.'
    column_lookup = _schema_column_lookup(schema, table_name)
    column_name = column_lookup.get(_normalise_identifier(raw_column))
    if not column_name:
        return table_name, None, "unmatched", f'Manual column "{raw_column}" was not found in {table_name}.'
    return table_name, column_name, "matched", "Manually mapped."


def preview_data_dictionary_mapping(
    schema: dict[str, Any],
    file_path: str | Path,
    mapping: dict[str, Any],
    limit: int = 100,
) -> dict[str, Any]:
    """Preview how a dictionary mapping will attach descriptions to schema columns."""
    path = Path(file_path)
    sheet_name = str(mapping["sheet_name"])
    table_column = mapping.get("table_column")
    column_column = str(mapping["column_column"])
    description_column = str(mapping["description_column"])
    default_table = mapping.get("default_table")
    manual_targets: dict[str, dict[str, str]] = mapping.get("manual_targets") or {}

    df = _read_excel_sheet_text(path, sheet_name)
    missing = [column for column in (column_column, description_column) if column not in df.columns]
    if table_column and table_column not in df.columns:
        missing.append(table_column)
    if missing:
        raise ValueError(f"Missing dictionary columns: {', '.join(missing)}")

    rows: list[dict[str, Any]] = []
    counts = {"matched": 0, "ambiguous": 0, "unmatched": 0, "skipped": 0}

    for row_number, row in enumerate(df.iter_rows(named=True)):
        row_id = str(row_number)
        raw_column = str(row.get(column_column) or "").strip()
        description = str(row.get(description_column) or "").strip()
        raw_table = str(row.get(table_column) or "").strip() if table_column else None
        if not raw_column or not description or description.lower() == "nan":
            counts["skipped"] += 1
            continue

        manual_table, manual_column, manual_status, manual_reason = _resolve_manual_target(schema, manual_targets.get(row_id))
        if manual_table and manual_column:
            table_name, column_name, status, reason = manual_table, manual_column, manual_status, manual_reason
        else:
            table_name, column_name, status, reason = _resolve_description_target(
                schema,
                raw_table if raw_table and raw_table.lower() != "nan" else None,
                raw_column,
                default_table,
            )
        counts[status] += 1
        if len(rows) < limit:
            rows.append(
                {
                    "row_id": row_id,
                    "source_table": raw_table,
                    "source_column": raw_column,
                    "source_description": description,
                    "table": table_name,
                    "column": column_name,
                    "description": description,
                    "status": status,
                    "reason": reason,
                }
            )

    return {"rows": rows, "counts": counts}


def apply_data_dictionary_mapping(
    schema: dict[str, Any],
    file_path: str | Path,
    mapping: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Apply matched dictionary rows into schema.description_map and column metadata."""
    preview = preview_data_dictionary_mapping(schema, file_path, mapping, limit=5000)
    description_map: dict[str, dict[str, str]] = schema.setdefault("description_map", {})

    for item in preview["rows"]:
        if item["status"] != "matched" or not item["table"] or not item["column"]:
            continue
        table_name = str(item["table"])
        column_name = str(item["column"])
        description = str(item["description"])
        description_map.setdefault(table_name, {})[column_name] = description

        table = schema.get("tables", {}).get(table_name, {})
        for column in table.get("columns", []):
            if column.get("name") == column_name:
                column["description"] = description
                column["description_source"] = "dictionary"
                break

    return schema, preview


def profile_relational_table(
    table_name: str,
    df: pd.DataFrame,
    description_map: dict[str, dict[str, str]] | None = None,
    source: dict[str, Any] | None = None,
    semantic_overrides: dict[str, str] | None = None,
) -> dict[str, Any]:
    table_descriptions = (description_map or {}).get(table_name, {})

    col_descs: dict[str, str] = {}
    for col in df.columns:
      clean_col, _ = _strip_key_suffix(col)
      desc = (
          table_descriptions.get(col)
          or table_descriptions.get(clean_col)
          or (description_map or {}).get("__all__", {}).get(col)
          or (description_map or {}).get("__all__", {}).get(clean_col)
      )
      if desc:
          col_descs[col] = desc

    profile = profile_dataframe(df, column_descriptions=col_descs, semantic_overrides=semantic_overrides)

    for col_info in profile.get("columns", []):
        raw_name = col_info.get("name", "")
        clean_name, key_type = _strip_key_suffix(raw_name)
        col_info["clean_name"] = clean_name
        col_info["key_type"] = key_type or None
        col_info["duckdb_type"] = "VARCHAR"

    profile["data_engineering"] = build_data_engineering_contract(df, profile)
    if source:
        profile["source"] = source
    return profile


def build_relational_schema(
    tables: dict[str, pd.DataFrame],
    descriptions: dict[str, dict[str, str]] | None = None,
    source: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a complete relational schema using profile_dataframe() per table."""
    schema_tables: dict[str, Any] = {}
    description_map: dict[str, dict[str, str]] = descriptions or {}

    for tname, df in tables.items():
        schema_tables[tname] = profile_relational_table(
            tname,
            df,
            description_map=description_map,
            source=source,
        )

    relationships = infer_relationships(tables)

    return {
        "tables": schema_tables,
        "relationships": relationships,
        "description_map": description_map,
    }

