from __future__ import annotations

import math
import re
from collections import Counter
from itertools import combinations
from typing import Any

import numpy as np
import pandas as pd

try:
    import polars as pl
except Exception:  # pragma: no cover - lets old environments fall back to pandas
    pl = None  # type: ignore[assignment]

try:
    from scipy import stats
except Exception:  # pragma: no cover - scipy is optional until installed
    stats = None  # type: ignore[assignment]


STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "because",
    "but",
    "by",
    "for",
    "from",
    "has",
    "have",
    "i",
    "in",
    "is",
    "it",
    "my",
    "of",
    "on",
    "or",
    "that",
    "the",
    "this",
    "to",
    "was",
    "with",
}


def json_safe(value: Any) -> Any:
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        if math.isnan(float(value)) or math.isinf(float(value)):
            return None
        return float(value)
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    if isinstance(value, (np.ndarray,)):
        return [json_safe(item) for item in value.tolist()]
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_safe(item) for item in value]
    if pd.isna(value) and not isinstance(value, (list, dict, tuple)):
        return None
    return value


def semantic_type(series: pd.Series) -> str:
    if pd.api.types.is_numeric_dtype(series):
        return "numeric"
    if pd.api.types.is_datetime64_any_dtype(series):
        return "datetime"
    non_null = series.dropna().astype(str)
    if non_null.empty:
        return "categorical"
    avg_len = non_null.str.len().mean()
    unique_ratio = non_null.nunique() / max(len(non_null), 1)
    if avg_len >= 35 or unique_ratio >= 0.55:
        return "text"
    return "categorical"


def histogram(series: pd.Series, bins: int = 10) -> dict[str, Any]:
    clean = pd.to_numeric(series, errors="coerce").dropna()
    if clean.empty:
        return {"bins": [], "counts": []}
    counts, edges = np.histogram(clean, bins=min(bins, max(1, clean.nunique())))
    return {"bins": [float(edge) for edge in edges], "counts": [int(count) for count in counts]}


def top_values(series: pd.Series, limit: int = 12) -> list[dict[str, Any]]:
    clean = series.dropna().astype(str)
    counts = clean.value_counts().head(limit)
    return [{"label": str(label), "count": int(count)} for label, count in counts.items()]


def to_polars(df: pd.DataFrame):
    if pl is None:
        return None
    try:
        return pl.from_pandas(df)
    except Exception:
        return None


def polars_missing_count(series) -> int:
    try:
        missing = int(series.null_count())
        if series.dtype in {pl.Float32, pl.Float64}:  # type: ignore[union-attr]
            missing += int(series.is_nan().sum())
        return missing
    except Exception:
        return 0


def polars_sample_values(series, limit: int = 5) -> list[Any]:
    try:
        return [json_safe(value) for value in series.drop_nulls().head(limit).to_list()]
    except Exception:
        return []


def polars_numeric_stats(series) -> dict[str, Any] | None:
    try:
        clean = series.drop_nulls()
        if clean.dtype in {pl.Float32, pl.Float64}:  # type: ignore[union-attr]
            clean = clean.filter(~clean.is_nan())
        if clean.len() == 0:
            return None
        return {
            "count": int(clean.len()),
            "mean": json_safe(clean.mean()),
            "median": json_safe(clean.median()),
            "std": json_safe(clean.std()),
            "min": json_safe(clean.min()),
            "q1": json_safe(clean.quantile(0.25)),
            "q3": json_safe(clean.quantile(0.75)),
            "max": json_safe(clean.max()),
        }
    except Exception:
        return None


def polars_top_values(series, limit: int = 12) -> list[dict[str, Any]] | None:
    try:
        counts = series.drop_nulls().cast(pl.Utf8).value_counts(sort=True).head(limit)  # type: ignore[union-attr]
        label_column = series.name
        return [
            {"label": str(row[label_column]), "count": int(row["count"])}
            for row in counts.to_dicts()
        ]
    except Exception:
        return None


def word_frequencies(series: pd.Series, limit: int = 50) -> list[dict[str, Any]]:
    text = " ".join(series.dropna().astype(str).tolist()).lower()
    words = [
        word
        for word in re.findall(r"\b[a-zA-Z][a-zA-Z']+\b", text)
        if len(word) > 2 and word not in STOP_WORDS
    ]
    return [{"word": word, "count": int(count)} for word, count in Counter(words).most_common(limit)]


def interpret_correlation(r: float | None, p: float | None) -> str:
    if r is None:
        return "Test failed."
    if p is None:
        if abs(r) < 0.1:
            return "No meaningful linear correlation."
        if abs(r) < 0.3:
            return "Weak linear correlation."
        if abs(r) < 0.7:
            return "Moderate linear correlation."
        return "Strong linear correlation."
    if p >= 0.05:
        return "No statistically significant correlation."
    if abs(r) < 0.1:
        return "No meaningful correlation (statistically significant but very weak)."
    if abs(r) < 0.3:
        return "Weak correlation, statistically significant."
    if abs(r) < 0.7:
        return "Moderate correlation, statistically significant."
    return "Strong correlation, statistically significant."


def interpret_chi2(p: float | None) -> str:
    if p is None:
        return "Test failed."
    return "Association detected (p < 0.05)." if p < 0.05 else "No significant association."


def interpret_anova(p: float | None) -> str:
    if p is None:
        return "Test failed."
    return "Group means differ significantly (p < 0.05)." if p < 0.05 else "No significant difference in group means."


def bivariate_analysis(
    df: pd.DataFrame, numeric_columns: list[str], categorical_columns: list[str], max_pairs: int = 80
) -> dict[str, list[dict[str, Any]]]:
    numeric_numeric: list[dict[str, Any]] = []
    categorical_categorical: list[dict[str, Any]] = []
    numeric_categorical: list[dict[str, Any]] = []

    for left, right in list(combinations(numeric_columns, 2))[:max_pairs]:
        paired = df[[left, right]].apply(pd.to_numeric, errors="coerce").dropna()
        if len(paired) < 3:
            numeric_numeric.append(
                {
                    "left": left,
                    "right": right,
                    "test": "Pearson Correlation",
                    "correlation": None,
                    "p_value": None,
                    "sample_size": int(len(paired)),
                    "interpretation": "Not enough paired non-null values for correlation.",
                }
            )
            continue
        try:
            if stats is not None:
                r, p = stats.pearsonr(paired[left], paired[right])
                p_value = float(p)
            else:
                r = paired[left].corr(paired[right])
                p_value = None
            correlation = round(float(r), 4) if pd.notna(r) else None
            numeric_numeric.append(
                {
                    "left": left,
                    "right": right,
                    "test": "Pearson Correlation",
                    "correlation": correlation,
                    "p_value": p_value,
                    "sample_size": int(len(paired)),
                    "interpretation": interpret_correlation(correlation, p_value),
                }
            )
        except Exception as exc:
            numeric_numeric.append(
                {
                    "left": left,
                    "right": right,
                    "test": "Pearson Correlation",
                    "correlation": None,
                    "p_value": None,
                    "sample_size": int(len(paired)),
                    "interpretation": "Test failed.",
                    "error": str(exc),
                }
            )

    for left, right in list(combinations(categorical_columns, 2))[:max_pairs]:
        contingency = pd.crosstab(df[left], df[right])
        if contingency.empty or contingency.shape[0] < 2 or contingency.shape[1] < 2:
            continue
        try:
            chi2 = p_value = None
            if stats is not None:
                chi2_raw, p_raw, _, _ = stats.chi2_contingency(contingency)
                chi2 = round(float(chi2_raw), 4)
                p_value = float(p_raw)
            categorical_categorical.append(
                {
                    "left": left,
                    "right": right,
                    "test": "Chi-square",
                    "chi2": chi2,
                    "p_value": p_value,
                    "levels_left": int(contingency.shape[0]),
                    "levels_right": int(contingency.shape[1]),
                    "interpretation": interpret_chi2(p_value),
                }
            )
        except Exception as exc:
            categorical_categorical.append(
                {
                    "left": left,
                    "right": right,
                    "test": "Chi-square",
                    "chi2": None,
                    "p_value": None,
                    "interpretation": "Test failed.",
                    "error": str(exc),
                }
            )

    mixed_pairs = [(num, cat) for num in numeric_columns for cat in categorical_columns][:max_pairs]
    for numeric, categorical in mixed_pairs:
        grouped = df[[numeric, categorical]].copy()
        grouped[numeric] = pd.to_numeric(grouped[numeric], errors="coerce")
        grouped = grouped.dropna()
        group_stats = (
            grouped.groupby(categorical)[numeric]
            .agg(["count", "mean", "median", "min", "max"])
            .reset_index()
            .sort_values("mean", ascending=False)
        )
        groups = [group[numeric].dropna() for _, group in grouped.groupby(categorical) if len(group[numeric].dropna()) >= 2]
        anova_f = p_value = None
        interpretation = "Not enough group data for ANOVA."
        try:
            if stats is not None and len(groups) >= 2:
                f_raw, p_raw = stats.f_oneway(*groups)
                anova_f = round(float(f_raw), 4)
                p_value = float(p_raw)
                interpretation = interpret_anova(p_value)
        except Exception as exc:
            interpretation = f"Test failed: {exc}"
        numeric_categorical.append(
            {
                "numeric": numeric,
                "categorical": categorical,
                "test": "ANOVA",
                "anova_F": anova_f,
                "p_value": p_value,
                "group_count": int(group_stats.shape[0]),
                "groups": json_safe(group_stats.head(12).to_dict(orient="records")),
                "interpretation": interpretation,
            }
        )

    return {
        "numeric_numeric": numeric_numeric,
        "categorical_categorical": categorical_categorical,
        "numeric_categorical": numeric_categorical,
    }


def profile_dataframe(
    df: pd.DataFrame,
    column_descriptions: dict[str, str] | None = None,
    semantic_overrides: dict[str, str] | None = None,
) -> dict[str, Any]:
    total_rows = int(len(df))
    descriptions = {str(key): str(value) for key, value in (column_descriptions or {}).items() if str(value).strip()}
    overrides = {
        str(key): str(value)
        for key, value in (semantic_overrides or {}).items()
        if str(value) in {"numeric", "categorical", "text", "datetime"}
    }
    pl_df = to_polars(df)
    columns: list[dict[str, Any]] = []
    numeric_columns: list[str] = []
    categorical_columns: list[str] = []
    text_columns: list[str] = []

    for name in df.columns:
        series = df[name]
        pl_series = pl_df[str(name)] if pl_df is not None and str(name) in pl_df.columns else None
        stype = overrides.get(str(name)) or semantic_type(series)
        if stype == "numeric":
            numeric_columns.append(str(name))
        elif stype == "categorical":
            categorical_columns.append(str(name))
        elif stype == "text":
            text_columns.append(str(name))

        missing = polars_missing_count(pl_series) if pl_series is not None else int(series.isna().sum())
        column: dict[str, Any] = {
            "name": str(name),
            "dtype": str(series.dtype),
            "semantic_type": stype,
            "description": descriptions.get(str(name)),
            "missing_count": missing,
            "missing_pct": round((missing / total_rows) * 100, 2) if total_rows else 0,
            "unique_count": int(pl_series.drop_nulls().n_unique()) if pl_series is not None else int(series.nunique(dropna=True)),
            "sample_values": polars_sample_values(pl_series) if pl_series is not None else [json_safe(v) for v in series.dropna().head(5).tolist()],
        }

        if stype == "numeric":
            numeric = pd.to_numeric(series, errors="coerce").dropna()
            stats_payload = polars_numeric_stats(pl_series) if pl_series is not None else None
            column["stats"] = stats_payload or {
                "count": int(numeric.count()),
                "mean": json_safe(numeric.mean()),
                "median": json_safe(numeric.median()),
                "std": json_safe(numeric.std()),
                "min": json_safe(numeric.min()),
                "q1": json_safe(numeric.quantile(0.25)),
                "q3": json_safe(numeric.quantile(0.75)),
                "max": json_safe(numeric.max()),
            }
            column["histogram"] = histogram(series)
        elif stype in {"categorical", "text"}:
            column["top_values"] = (
                polars_top_values(pl_series) if pl_series is not None else None
            ) or top_values(series)
            if stype == "text":
                column["word_frequencies"] = word_frequencies(series)

        columns.append(json_safe(column))

    correlations: list[dict[str, Any]] = []
    if len(numeric_columns) >= 2:
        corr = df[numeric_columns].corr(numeric_only=True)
        for idx, left in enumerate(numeric_columns):
            for right in numeric_columns[idx + 1 :]:
                value = corr.loc[left, right]
                if pd.notna(value):
                    correlations.append({"left": left, "right": right, "correlation": round(float(value), 4)})

    quality_flags: list[str] = []
    missing_total = int(df.isna().sum().sum())
    if missing_total:
        quality_flags.append(f"{missing_total} missing cells detected across the dataset.")
    if total_rows == 0:
        quality_flags.append("Dataset has no rows.")
    duplicate_rows = int(df.duplicated().sum())
    if duplicate_rows:
        quality_flags.append(f"{duplicate_rows} duplicate rows detected.")
    described_columns = [column for column in df.columns if descriptions.get(str(column))]
    if descriptions and len(described_columns) < len(df.columns):
        missing_descriptions = [str(column) for column in df.columns if not descriptions.get(str(column))]
        quality_flags.append(f"Human column descriptions are missing for: {', '.join(missing_descriptions[:8])}.")
    if not descriptions:
        quality_flags.append("No human column descriptions were supplied; semantic understanding relies on names, types, and samples.")
    return json_safe(
        {
            "row_count": total_rows,
            "column_count": int(df.shape[1]),
            "columns": columns,
            "metadata": {
                "numeric_columns": numeric_columns,
                "categorical_columns": categorical_columns,
                "text_columns": text_columns,
                "described_columns": len(described_columns),
                "description_coverage_pct": round((len(described_columns) / len(df.columns)) * 100, 2) if len(df.columns) else 0,
                "duplicate_rows": duplicate_rows,
                "missing_cells": missing_total,
            },
            "correlations": sorted(correlations, key=lambda item: abs(item["correlation"]), reverse=True),
            "bivariate_analysis": bivariate_analysis(df, numeric_columns, categorical_columns),
            "quality_flags": quality_flags,
        }
    )
