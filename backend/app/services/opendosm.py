"""OpenDOSM API connector — fetch data from Malaysia's official open data portal.

Base URL: https://api.data.gov.my/data-catalogue
Docs: https://developer.data.gov.my/static-api/data-catalogue
"""
from __future__ import annotations

import json
import re
import time
from typing import Any

import pandas as pd
import requests

BASE_URL = "https://api.data.gov.my/data-catalogue"
CATALOGUE_URL = "https://open.dosm.gov.my/data-catalogue"

# Offline fallback used when the live OpenDOSM catalogue cannot be reached.
DATASET_CATALOGUE: list[dict[str, str]] = [
    {"id": "cpi_core", "name": "Consumer Price Index (Core)", "category": "Prices",
     "desc": "National-level core CPI for 13 main groups of goods and services. Monthly."},
    {"id": "cpi_headline", "name": "CPI Headline", "category": "Prices",
     "desc": "Headline consumer price index covering all items. Monthly."},
    {"id": "population_malaysia", "name": "Population — Malaysia", "category": "Demographics",
     "desc": "National population from 1970 to 2025 by sex, age group and ethnicity. Yearly."},
    {"id": "population_state", "name": "Population — By State", "category": "Demographics",
     "desc": "State-level population breakdowns. Yearly."},
    {"id": "population_district", "name": "Population — By District", "category": "Demographics",
     "desc": "District-level population data. Yearly."},
    {"id": "births_annual", "name": "Births (Annual)", "category": "Demographics",
     "desc": "Annual live births with signs of life upon delivery. Yearly."},
    {"id": "births_annual_state", "name": "Births — By State", "category": "Demographics",
     "desc": "Annual births by state. Yearly."},
    {"id": "deaths", "name": "Deaths (Annual)", "category": "Demographics",
     "desc": "Annual number of deaths registered. Yearly."},
    {"id": "deaths_state", "name": "Deaths — By State", "category": "Demographics",
     "desc": "Annual deaths by state. Yearly."},
    {"id": "marriages", "name": "Marriages", "category": "Demographics",
     "desc": "Annual marriages registered. Yearly."},
    {"id": "marriages_state", "name": "Marriages — By State", "category": "Demographics",
     "desc": "Annual marriages by state. Yearly."},
    {"id": "fertility", "name": "Fertility", "category": "Demographics",
     "desc": "Fertility indicators. Yearly."},
    {"id": "fertility_state", "name": "Fertility — By State", "category": "Demographics",
     "desc": "Fertility indicators by state. Yearly."},
    {"id": "hh_profile", "name": "Household Profile", "category": "Demographics",
     "desc": "Household composition and demographics. Yearly."},
    {"id": "stillbirths", "name": "Stillbirths", "category": "Demographics",
     "desc": "Annual stillbirth registrations. Yearly."},
    {"id": "stillbirths_state", "name": "Stillbirths — By State", "category": "Demographics",
     "desc": "Annual stillbirths by state. Yearly."},
]


_CATALOGUE_CACHE_TTL_SECONDS = 60 * 60
_catalogue_cache: list[dict[str, str]] | None = None
_catalogue_cached_at = 0.0


def _parse_catalogue_page(html: str) -> list[dict[str, str]]:
    """Extract every dataset from the OpenDOSM catalogue's Next.js payload."""
    match = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    if not match:
        raise ValueError("OpenDOSM catalogue payload was not found")

    page_data = json.loads(match.group(1))
    collection = page_data["props"]["pageProps"]["collection"]
    datasets: list[dict[str, str]] = []
    seen_ids: set[str] = set()

    for category, groups in collection.items():
        if not isinstance(groups, dict):
            continue
        for group, entries in groups.items():
            if not isinstance(entries, list):
                continue
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                dataset_id = str(entry.get("id") or "").strip()
                if not dataset_id or dataset_id in seen_ids:
                    continue
                seen_ids.add(dataset_id)
                datasets.append({
                    "id": dataset_id,
                    "name": str(entry.get("title") or dataset_id.replace("_", " ").title()),
                    "category": f"{category}: {group}",
                    "desc": str(entry.get("description") or ""),
                })

    if not datasets:
        raise ValueError("OpenDOSM catalogue did not contain any datasets")
    return datasets


def list_datasets() -> list[dict[str, str]]:
    """Return the complete live OpenDOSM catalogue, with an offline fallback."""
    global _catalogue_cache, _catalogue_cached_at

    now = time.monotonic()
    if _catalogue_cache is not None and now - _catalogue_cached_at < _CATALOGUE_CACHE_TTL_SECONDS:
        return [dict(item) for item in _catalogue_cache]

    try:
        response = requests.get(CATALOGUE_URL, timeout=15)
        response.raise_for_status()
        catalogue = _parse_catalogue_page(response.text)
    except (requests.RequestException, ValueError, KeyError, TypeError, json.JSONDecodeError):
        catalogue = [dict(item) for item in DATASET_CATALOGUE]

    _catalogue_cache = catalogue
    _catalogue_cached_at = now
    return [dict(item) for item in catalogue]




def fetch_dataset(dataset_id: str, limit: int | None = None) -> pd.DataFrame:
    """Fetch data from OpenDOSM API and return as DataFrame."""
    params: dict[str, str | int] = {"id": dataset_id}
    if limit is not None:
        params["limit"] = limit
    resp = requests.get(BASE_URL, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    if isinstance(data, list):
        return pd.DataFrame(data)
    if isinstance(data, dict):
        for key in ("data", "records", "results", "items"):
            if key in data and isinstance(data[key], list):
                return pd.DataFrame(data[key])
        return pd.DataFrame([data])
    raise ValueError(f"Unexpected response type from OpenDOSM: {type(data)}")


def fetch_profile_only(dataset_id: str, limit: int | None = None) -> dict[str, Any]:
    """Fetch the full dataset, save as CSV on disk, and build a profile.

    Downloads the complete dataset from the API, saves it as source + working
    CSV files, then uses the same profile_dataframe() profiler as single-table uploads.
    Returns a profile in the unified tables format.
    """
    from app.services.data_engineering import build_data_engineering_contract
    from app.services.profiling import profile_dataframe
    from app.settings import UPLOAD_DIR

    # Fetch full dataset from API
    df = fetch_dataset(dataset_id, limit=limit)
    if df.empty:
        raise ValueError(f"No data returned for dataset '{dataset_id}'")

    # Save to disk as CSV
    ds_name = dataset_id.replace("_", "-")
    dataset_dir = UPLOAD_DIR / f"opendosm_{dataset_id}"
    dataset_dir.mkdir(parents=True, exist_ok=True)
    source_path = dataset_dir / f"{ds_name}.csv"
    working_path = dataset_dir / f"{ds_name}.working.csv"
    df.to_csv(source_path, index=False)
    df.to_csv(working_path, index=False)

    # Build profile using the same profiler as single-table uploads
    metadata = fetch_metadata(dataset_id)
    field_descs: dict[str, str] = {}
    for f in metadata.get("fields", []):
        if f.get("name") and f.get("description"):
            field_descs[f["name"]] = f["description"]

    table_profile = profile_dataframe(df, column_descriptions=field_descs)
    table_profile["data_engineering"] = build_data_engineering_contract(df, table_profile)

    # Attach OpenDOSM-specific metadata
    table_profile["source"] = "opendosm"
    table_profile["dataset_id"] = dataset_id
    if metadata:
        table_profile["title"] = metadata.get("title", "")
        table_profile["opendosm_description"] = metadata.get("description", "")
        table_profile["frequency"] = metadata.get("frequency", "")
        table_profile["data_source"] = metadata.get("data_source", "")
        table_profile["data_as_of"] = metadata.get("data_as_of", "")
        table_profile["methodology"] = metadata.get("methodology", "")
        table_profile["caveat"] = metadata.get("caveat", "")
        table_profile["context"] = _build_context_string(metadata)

    # Wrap in unified tables format
    return {
        "tables": {ds_name: table_profile},
        "relationships": [],
        "description_map": {},
    }




def fetch_metadata(dataset_id: str) -> dict[str, Any]:
    """Scrape metadata from the OpenDOSM data catalogue page."""
    try:
        resp = requests.get(f"{CATALOGUE_URL}/{dataset_id}", timeout=15)
        if resp.status_code != 200:
            return {}
        match = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', resp.text, re.S)
        if not match:
            return {}
        props = json.loads(match.group(1)).get("props", {}).get("pageProps", {})
        if not props:
            return {}

        raw_fields = props.get("fields", [])
        if isinstance(raw_fields, str):
            try:
                raw_fields = json.loads(raw_fields)
            except (json.JSONDecodeError, TypeError):
                raw_fields = []
        fields: list[dict[str, str]] = []
        for f in raw_fields:
            if isinstance(f, dict):
                fields.append({
                    "name": f.get("name", ""),
                    "title": f.get("title", ""),
                    "description": f.get("description", ""),
                })

        return {
            "title": props.get("title", ""),
            "description": props.get("description", ""),
            "methodology": props.get("methodology", ""),
            "caveat": props.get("caveat", ""),
            "frequency": props.get("frequency", ""),
            "data_source": props.get("data_source", ""),
            "data_as_of": props.get("data_as_of", ""),
            "last_updated": props.get("last_updated", ""),
            "next_update": props.get("next_update", ""),
            "publication": props.get("publication", ""),
            "fields": fields,
        }
    except Exception:
        return {}


def _build_context_string(metadata: dict[str, Any]) -> str:
    """Build a human-readable context string from metadata for agent prompts."""
    parts: list[str] = []
    if metadata.get("title"):
        parts.append(f"# {metadata['title']}")
    if metadata.get("description"):
        parts.append(metadata["description"])
    if metadata.get("frequency"):
        parts.append(f"Frequency: {metadata['frequency']}")
    if metadata.get("data_source"):
        src = metadata["data_source"]
        if isinstance(src, list):
            src = ", ".join(src)
        parts.append(f"Data source: {src}")
    if metadata.get("data_as_of"):
        parts.append(f"Data as of: {metadata['data_as_of']}")
    if metadata.get("methodology"):
        parts.append(f"\n## Methodology\n{metadata['methodology']}")
    if metadata.get("fields"):
        parts.append("\n## Column Definitions")
        for f in metadata["fields"]:
            desc = f.get("description", "")
            parts.append(f"- **{f.get('name', '')}** ({f.get('title', '')}): {desc}")
    if metadata.get("caveat"):
        parts.append(f"\n## Caveats\n{metadata['caveat']}")
    return "\n".join(parts)
