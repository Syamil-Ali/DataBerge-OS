from __future__ import annotations

import re
from collections import Counter
from typing import Any

import pandas as pd


NULL_LIKE_MARKERS = {"", "-", "--", "na", "n/a", "nan", "none", "null", "unknown", "missing"}
DATA_ENGINEERING_CONTRACT_VERSION = 2


def normalize_text(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def infer_engineering_role(column: dict[str, Any], series: pd.Series, row_count: int) -> str:
    name = normalize_text(str(column.get("name", "")))
    description = normalize_text(str(column.get("description") or ""))
    semantic_type = str(column.get("semantic_type") or "")
    combined = f"{name} {description}".strip()
    name_tokens = set(name.split())
    combined_tokens = set(combined.split())
    declared_match = re.match(r"\s*\[([^\]]+)\]", str(column.get("description") or ""))
    declared_type = normalize_text(declared_match.group(1)) if declared_match else ""
    top_values = {normalize_text(str(item.get("label", ""))) for item in (column.get("top_values") or [])}

    if (
        semantic_type == "datetime"
        or declared_type in {"date", "datetime", "timestamp", "time"}
        or bool(name_tokens & {"date", "datetime", "timestamp", "time", "month", "year"})
    ):
        return "time"
    if "employment status" in combined:
        return "category"
    if combined_tokens & {"approval", "approved", "rejected", "outcome", "label", "target"}:
        return "outcome"
    if name_tokens & {"id", "uuid", "identifier", "key", "code"} or combined_tokens & {"identifier", "uuid"}:
        return "identifier"
    if declared_type == "categorical":
        return "category"
    if semantic_type == "text" or combined_tokens & {
        "reason", "narrative", "comment", "description", "purpose", "story", "note",
    }:
        return "narrative"
    if semantic_type == "numeric":
        return "measure"
    if {"approved", "rejected"}.issubset(top_values):
        return "outcome"
    return "category"


def detect_null_like_markers(series: pd.Series) -> list[str]:
    if pd.api.types.is_numeric_dtype(series):
        return []
    values = [normalize_text(str(value)) for value in series.dropna().astype(str).tolist()]
    counts = Counter(value for value in values if value in NULL_LIKE_MARKERS)
    return [value for value, _ in counts.most_common(4)]


def detect_datetime_candidate(series: pd.Series) -> float:
    if pd.api.types.is_datetime64_any_dtype(series) or pd.api.types.is_numeric_dtype(series):
        return 0.0
    non_null = series.dropna()
    if non_null.empty:
        return 0.0
    sample = non_null.astype(str).head(25)
    looks_temporal = sample.str.contains(r"(?:\d{4}[-/]\d{1,2}[-/]\d{1,2})|(?:\d{1,2}[-/]\d{1,2}[-/]\d{2,4})|(?::)", regex=True).any()
    if not looks_temporal:
        return 0.0
    parsed = pd.to_datetime(non_null, errors="coerce")
    return round(float(parsed.notna().mean() * 100), 2)


def build_data_engineering_contract(df: pd.DataFrame, profile: dict[str, Any]) -> dict[str, Any]:
    row_count = int(profile.get("row_count", len(df)))
    described_columns = int(profile.get("metadata", {}).get("described_columns", 0))
    source = profile.get("source", {}) or {}
    lineage = source.get("lineage", {}) or {}
    lineage_label = (
        str(lineage.get("mode") or "").strip()
        or str(source.get("source_type") or "").strip()
        or "unknown source"
    )
    role_map: dict[str, list[str]] = {
        "identifier": [],
        "measure": [],
        "category": [],
        "outcome": [],
        "narrative": [],
        "time": [],
    }
    warnings: list[str] = []
    preparation_notes: list[str] = []
    recommended_actions: list[str] = []

    for column in profile.get("columns", []):
        name = str(column.get("name"))
        series = df[name] if name in df.columns else pd.Series(dtype="object")
        role = infer_engineering_role(column, series, row_count)
        null_like_markers = detect_null_like_markers(series)
        datetime_candidate_pct = detect_datetime_candidate(series)
        quality_notes: list[str] = []
        column_preparation_notes: list[str] = []
        suggested_actions: list[str] = []

        if null_like_markers:
            quality_notes.append(f"Found null-like markers: {', '.join(null_like_markers)}.")
            suggested_actions.append("Normalize null-like text markers before downstream analysis.")
        if role == "identifier":
            suggested_actions.append("Exclude from aggregates and modeling features unless needed for joins or traceability.")
        if role == "narrative":
            suggested_actions.append("Use as narrative evidence; summarize or cluster instead of treating as a simple category.")
        if role == "time" and str(column.get("semantic_type")) != "datetime" and datetime_candidate_pct >= 80:
            column_preparation_notes.append(
                "Valid date values are stored as text; cast to datetime only when ordered time analysis is required."
            )
            suggested_actions.append("Cast to datetime in the working dataset before time-based analysis.")
        elif role == "time" and str(column.get("semantic_type")) != "datetime":
            quality_notes.append("Declared time field is not consistently parseable as datetime values.")
            suggested_actions.append("Validate the time values before time-based analysis.")
        if datetime_candidate_pct >= 80 and role != "time":
            column_preparation_notes.append(f"{datetime_candidate_pct}% of non-null values are parseable as dates.")
            suggested_actions.append("Review whether this column should be promoted to a time field.")
        if float(column.get("missing_pct") or 0) > 15:
            quality_notes.append("High missingness may affect joins, aggregates, or model quality.")
            suggested_actions.append("Decide an explicit missing-value policy for this column.")

        description_source = "human" if column.get("description") else "inferred"
        column["engineering_role"] = role
        column["description_source"] = description_source
        column["null_like_markers"] = null_like_markers
        column["datetime_candidate_pct"] = datetime_candidate_pct
        column["quality_notes"] = quality_notes
        column["preparation_notes"] = column_preparation_notes
        column["suggested_actions"] = suggested_actions
        role_map.setdefault(role, []).append(name)

        warnings.extend(quality_notes)
        preparation_notes.extend(column_preparation_notes)
        recommended_actions.extend(suggested_actions)

    duplicate_rows = int(profile.get("metadata", {}).get("duplicate_rows", 0))
    missing_cells = int(profile.get("metadata", {}).get("missing_cells", 0))
    score = 10.0
    if row_count == 0:
        score = 0.0
    score -= min(2.0, missing_cells / max(row_count, 1))
    score -= min(1.5, duplicate_rows / max(row_count, 1) * 10)
    score -= 1.5 if described_columns == 0 else 0.0
    score -= 0.5 if described_columns and described_columns < len(df.columns) else 0.0
    score -= min(2.0, len(warnings) * 0.15)
    readiness_score = round(max(0.0, min(10.0, score)), 1)

    summary_parts = [
        f"Prepared a working contract for {len(df.columns)} columns and {row_count} rows.",
        f"Readiness is {readiness_score}/10 for downstream analyst and reporting workflows.",
    ]
    if role_map["narrative"]:
        summary_parts.append(f"Detected narrative evidence fields: {', '.join(role_map['narrative'][:3])}.")
    if role_map["outcome"]:
        summary_parts.append(f"Detected outcome/status fields: {', '.join(role_map['outcome'][:3])}.")
    if described_columns == len(df.columns) and len(df.columns) > 0:
        summary_parts.append("Every column has a human description, which improves semantic routing.")

    deduped_actions = list(dict.fromkeys(recommended_actions))
    deduped_warnings = list(dict.fromkeys(warnings))
    deduped_preparation_notes = list(dict.fromkeys(preparation_notes))
    return {
        "version": DATA_ENGINEERING_CONTRACT_VERSION,
        "readiness_score": readiness_score,
        "summary": " ".join(summary_parts),
        "warnings": deduped_warnings[:8],
        "preparation_notes": deduped_preparation_notes[:8],
        "recommended_actions": deduped_actions[:8],
        "semantic_roles": role_map,
        "working_dataset_policy": {
            "mutates_source_data": False,
            "approval_required_for_cleaning": True,
            "lineage": f"{lineage_label} -> working dataset -> profile -> analyst workflows",
            "source_type": source.get("source_type", "unknown"),
            "refreshable": bool(lineage.get("refreshable", False)),
        },
    }
