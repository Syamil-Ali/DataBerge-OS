from __future__ import annotations

import re
import shutil
import zipfile
from pathlib import Path
from typing import BinaryIO

import pandas as pd
import polars as pl
import fastexcel

from app.settings import MAX_UPLOAD_BYTES, MAX_WORKBOOK_UNCOMPRESSED_BYTES, UPLOAD_DIR
from app.storage.database import new_id


SUPPORTED_EXTENSIONS = {".csv", ".xlsx", ".xls"}
_COPY_CHUNK_BYTES = 1024 * 1024


class UploadTooLarge(ValueError):
    pass


def safe_filename(filename: str) -> str:
    stem = Path(filename).stem.strip() or "dataset"
    suffix = Path(filename).suffix.lower()
    clean_stem = re.sub(r"[^A-Za-z0-9._-]+", "_", stem).strip("._-") or "dataset"
    return f"{clean_stem}{suffix}"


def copy_upload_limited(file_obj: BinaryIO, target_path: Path, max_bytes: int = MAX_UPLOAD_BYTES) -> int:
    """Stream an upload to disk and abort before it can exceed the configured cap."""
    written = 0
    try:
        with target_path.open("wb") as target:
            while chunk := file_obj.read(_COPY_CHUNK_BYTES):
                written += len(chunk)
                if written > max_bytes:
                    raise UploadTooLarge(f"Upload exceeds the {max_bytes // (1024 * 1024)} MB limit.")
                target.write(chunk)
    except Exception:
        target_path.unlink(missing_ok=True)
        raise
    return written


def validate_workbook_archive(path: Path) -> None:
    """Reject XLSX archives whose expanded contents are unreasonably large."""
    if path.suffix.lower() != ".xlsx":
        return
    try:
        with zipfile.ZipFile(path) as workbook:
            expanded = sum(entry.file_size for entry in workbook.infolist())
    except zipfile.BadZipFile as exc:
        raise ValueError("The uploaded XLSX file is not a valid workbook.") from exc
    if expanded > MAX_WORKBOOK_UNCOMPRESSED_BYTES:
        raise UploadTooLarge(
            f"Workbook expands beyond the {MAX_WORKBOOK_UNCOMPRESSED_BYTES // (1024 * 1024)} MB safety limit."
        )


def directory_size(path: Path) -> int:
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


def save_upload(file_obj: BinaryIO, filename: str) -> tuple[str, Path, str]:
    safe_name = safe_filename(filename)
    suffix = Path(safe_name).suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise ValueError("Only CSV and Excel files are supported in V1.")

    dataset_id = new_id()
    dataset_dir = UPLOAD_DIR / dataset_id
    dataset_dir.mkdir(parents=True, exist_ok=True)
    source_path = dataset_dir / safe_name
    try:
        copy_upload_limited(file_obj, source_path)
        validate_workbook_archive(source_path)
    except Exception:
        shutil.rmtree(dataset_dir, ignore_errors=True)
        raise
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
