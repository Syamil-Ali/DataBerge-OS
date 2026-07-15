from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import BinaryIO

import pandas as pd
import polars as pl
import fastexcel

from app.settings import UPLOAD_DIR
from app.storage.database import new_id


SUPPORTED_EXTENSIONS = {".csv", ".xlsx", ".xls"}


def safe_filename(filename: str) -> str:
    stem = Path(filename).stem.strip() or "dataset"
    suffix = Path(filename).suffix.lower()
    clean_stem = re.sub(r"[^A-Za-z0-9._-]+", "_", stem).strip("._-") or "dataset"
    return f"{clean_stem}{suffix}"


def save_upload(file_obj: BinaryIO, filename: str) -> tuple[str, Path, str]:
    safe_name = safe_filename(filename)
    suffix = Path(safe_name).suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise ValueError("Only CSV and Excel files are supported in V1.")

    dataset_id = new_id()
    dataset_dir = UPLOAD_DIR / dataset_id
    dataset_dir.mkdir(parents=True, exist_ok=True)
    source_path = dataset_dir / safe_name
    with source_path.open("wb") as target:
        shutil.copyfileobj(file_obj, target)
    return dataset_id, source_path, suffix.removeprefix(".")


def load_dataframe(path: str | Path) -> pd.DataFrame:
    file_path = Path(path)
    suffix = file_path.suffix.lower()
    if suffix == ".csv":
        return pl.read_csv(file_path).to_pandas()
    if suffix in {".xlsx", ".xls"}:
        workbook = fastexcel.read_excel(str(file_path))
        if not workbook.sheet_names:
            raise ValueError("Excel workbook is empty.")
        sheet_name = "Data" if "Data" in workbook.sheet_names else workbook.sheet_names[0]
        return pl.read_excel(file_path, sheet_name=sheet_name, engine="calamine").to_pandas()
    raise ValueError("Unsupported file type.")


def load_column_descriptions(path: str | Path) -> dict[str, str]:
    file_path = Path(path)
    suffix = file_path.suffix.lower()
    if suffix not in {".xlsx", ".xls"}:
        return {}

    try:
        workbook = fastexcel.read_excel(str(file_path))
    except Exception:
        return {}
    description_sheet = next((sheet for sheet in workbook.sheet_names if sheet.lower() == "description"), None)
    if not description_sheet:
        return {}

    try:
        descriptions = pl.read_excel(file_path, sheet_name=description_sheet, engine="calamine")
        descriptions = descriptions.with_columns(pl.all().cast(pl.Utf8, strict=False))
    except Exception:
        return {}
    if descriptions.is_empty():
        return {}

    header_lookup = {str(column).strip().lower(): column for column in descriptions.columns}
    column_key = header_lookup.get("column") or header_lookup.get("columns") or header_lookup.get("field")
    description_key = header_lookup.get("description") or header_lookup.get("meaning") or header_lookup.get("definition")
    if not column_key or not description_key:
        return {}

    result: dict[str, str] = {}
    for row in descriptions.select([column_key, description_key]).iter_rows(named=True):
        column_name = str(row.get(column_key) or "").strip()
        description = str(row.get(description_key) or "").strip()
        if column_name and description and description.lower() != "nan":
            result[column_name] = description
    return result
