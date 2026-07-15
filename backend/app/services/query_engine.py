from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

from app.services.files import load_dataframe
from data_berge_core.contracts import get_flat_profile


class UnsafeQueryError(ValueError):
    pass


class AmbiguousQueryError(ValueError):
    pass


def quote_ident(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def quote_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def find_column(message: str, columns: list[str], allowed_types: set[str] | None = None, profile: dict[str, Any] | None = None) -> str | None:
    normalized_message = normalize(message)
    message_tokens = set(normalized_message.split())
    type_lookup = {}
    if profile:
        type_lookup = {col["name"]: col.get("semantic_type") for col in get_flat_profile(profile).get("columns", [])}
    ranked = sorted(columns, key=len, reverse=True)
    for column in ranked:
        if allowed_types and type_lookup.get(column) not in allowed_types:
            continue
        normalized_column = normalize(column)
        column_tokens = set(normalized_column.split())
        if normalized_column in normalized_message:
            return column
        if column_tokens and column_tokens.issubset(message_tokens):
            return column
        if normalized_column == "employment status" and "employ" in normalized_message and "status" in message_tokens:
            return column
    return None


def find_outcome_column(profile: dict[str, Any], preferred_value: str | None = None) -> str | None:
    for col in get_flat_profile(profile).get("columns", []):
        if col.get("semantic_type") != "categorical":
            continue
        name = str(col.get("name", ""))
        top_values = col.get("top_values", []) or []
        labels = {normalize(str(item.get("label", ""))) for item in top_values}
        if "approval" in normalize(name):
            return name
        if preferred_value and normalize(preferred_value) in labels:
            return name
        if {"approved", "rejected"}.issubset(labels):
            return name
    return None


def load_query_dataframe(working_path: str | Path) -> pd.DataFrame:
    return load_dataframe(working_path)


def validate_select(sql: str) -> None:
    cleaned = sql.strip().rstrip(";")
    if not re.match(r"^(select|with)\b", cleaned, flags=re.IGNORECASE):
        raise UnsafeQueryError("Only SELECT queries are allowed.")
    blocked = re.search(
        r"\b(insert|update|delete|drop|alter|create|attach|detach|copy|pragma|call|install|load)\b",
        cleaned,
        flags=re.IGNORECASE,
    )
    if blocked:
        raise UnsafeQueryError(f"Query contains blocked statement: {blocked.group(1)}")


def execute_sql(working_path: str | Path, sql: str, limit: int = 100) -> list[dict[str, Any]]:
    validate_select(sql)
    df = load_query_dataframe(working_path)
    conn = duckdb.connect(database=":memory:")
    conn.register("dataset", df)
    limited = f"select * from ({sql.rstrip(';')}) as q limit {int(limit)}"
    result = conn.execute(limited).fetchdf()
    return result.where(pd.notnull(result), None).to_dict(orient="records")


def build_sql(message: str, profile: dict[str, Any]) -> tuple[str, str]:
    columns = [col["name"] for col in get_flat_profile(profile).get("columns", [])]
    lower = message.lower()
    numeric = set(get_flat_profile(profile).get("metadata", {}).get("numeric_columns", []))
    categorical = set(get_flat_profile(profile).get("metadata", {}).get("categorical_columns", []))

    if any(term in lower for term in ["how many rows", "row count", "number of rows", "records", "observations"]):
        return "select count(*) as row_count from dataset", "Counted total rows."

    if any(term in lower for term in ["missing", "null", "empty"]):
        parts = [
            f"sum(case when {quote_ident(col)} is null then 1 else 0 end) as {quote_ident(col + '_missing')}"
            for col in columns
        ]
        return f"select {', '.join(parts)} from dataset", "Calculated missing values by column."

    metric_map = {
        "average": "avg",
        "avg": "avg",
        "mean": "avg",
        "sum": "sum",
        "total": "sum",
        "minimum": "min",
        "min": "min",
        "maximum": "max",
        "max": "max",
    }
    for word, func in metric_map.items():
        if word in lower:
            column = find_column(message, columns, {"numeric"}, profile) or next(iter(numeric), None)
            if column:
                alias = f"{func}_{column}".replace(" ", "_")
                return f"select {func}({quote_ident(column)}) as {quote_ident(alias)} from dataset", f"Calculated {func.upper()} for {column}."

    if "correlation" in lower or "relationship" in lower:
        categorical_column = find_column(message, columns, {"categorical"}, profile)
        numeric_column = find_column(message, columns, {"numeric"}, profile)
        if categorical_column and numeric_column:
            qcat = quote_ident(categorical_column)
            qnum = quote_ident(numeric_column)
            alias = f"avg_{numeric_column}".replace(" ", "_")
            return (
                f"select {qcat} as category, avg({qnum}) as {quote_ident(alias)}, count(*) as row_count "
                f"from dataset group by {qcat} order by {quote_ident(alias)} desc",
                f"Compared {numeric_column} across {categorical_column}; Pearson correlation is only defined for numeric pairs.",
            )

        mentioned = [col for col in columns if col in numeric and normalize(col) in normalize(message)]
        if len(mentioned) >= 2:
            left, right = mentioned[:2]
        else:
            numeric_cols = list(numeric)
            if len(numeric_cols) < 2:
                return "select count(*) as row_count from dataset", "No numeric pair was available for correlation."
            left, right = numeric_cols[:2]
        return f"select corr({quote_ident(left)}, {quote_ident(right)}) as correlation from dataset", f"Calculated correlation between {left} and {right}."

    outcome_value: str | None = None
    if any(term in lower for term in ["approval", "approvals", "approve", "approved"]):
        outcome_value = "Approved"
    elif any(term in lower for term in ["rejection", "rejections", "reject", "rejected"]):
        outcome_value = "Rejected"

    compares_outcome_values = (
        any(term in lower for term in ["approve", "approved", "approval"])
        and any(term in lower for term in ["reject", "rejected", "rejection"])
    ) or any(term in lower for term in ["highest", "higher", "which is more", "which one is more", "most"])
    if compares_outcome_values:
        outcome_column = find_outcome_column(profile, outcome_value)
        if outcome_column:
            qoutcome = quote_ident(outcome_column)
            return (
                f"select {qoutcome} as category, count(*) as count from dataset group by {qoutcome} order by count desc",
                f"Compared counts by {outcome_column}.",
            )

    if outcome_value and any(term in lower for term in [" by ", "breakdown", "group", "status"]):
        outcome_column = find_outcome_column(profile, outcome_value)
        group_column = find_column(message, [col for col in columns if col != outcome_column], {"categorical", "text"}, profile)
        if not group_column and categorical:
            group_column = next((col for col in categorical if col != outcome_column), None)
        if outcome_column and group_column:
            qgroup = quote_ident(group_column)
            qoutcome = quote_ident(outcome_column)
            alias = f"{normalize(outcome_value).replace(' ', '_')}_count"
            return (
                f"select {qgroup} as category, count(*) as {quote_ident(alias)} "
                f"from dataset where {qoutcome} = {quote_literal(outcome_value)} "
                f"group by {qgroup} order by {quote_ident(alias)} desc",
                f"Counted {outcome_value.lower()} rows by {group_column}.",
            )

    if any(term in lower for term in ["top", "most common", "frequency", "distribution", "breakdown", "by "]):
        column = find_column(message, columns, {"categorical", "text"}, profile)
        if not column and categorical:
            column = next(iter(categorical))
        if column:
            qcol = quote_ident(column)
            return (
                f"select {qcol} as category, count(*) as count from dataset group by {qcol} order by count desc",
                f"Grouped rows by {column}.",
            )

    raise AmbiguousQueryError(
        "The question did not map to a safe focused calculation. Ask a follow-up before running SQL."
    )
