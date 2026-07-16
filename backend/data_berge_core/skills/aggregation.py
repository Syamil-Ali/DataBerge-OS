from __future__ import annotations

import json
import re
from typing import Any

from data_berge_core.contracts import get_flat_profile, normalize_top_values


AGGREGATE_LABELS = {"all", "overall", "total", "both", "combined", "any"}


class AggregationGrainSkill:
    """Teach analytical agents to preserve grain in pre-aggregated data cubes."""

    def analyze(
        self,
        dataset: dict[str, Any],
        observed_values: dict[str, list[Any]] | None = None,
    ) -> dict[str, Any]:
        columns = get_flat_profile(dataset.get("profile", {})).get("columns", [])
        dimensions: list[dict[str, Any]] = []
        measures: list[str] = []
        time_columns: list[str] = []

        for column in columns:
            if not isinstance(column, dict) or not column.get("name"):
                continue
            name = str(column["name"])
            semantic_type = str(column.get("semantic_type", "")).casefold()
            role = str(column.get("engineering_role", "")).casefold()
            if observed_values is not None and name in observed_values:
                values = [str(value) for value in observed_values[name] if value is not None]
            else:
                values = [str(item.get("label", "")) for item in normalize_top_values(column.get("top_values"))]

            if semantic_type in {"numeric", "integer", "float"} or role in {"measure", "metric"}:
                measures.append(name)
            if semantic_type in {"date", "datetime", "timestamp", "temporal"} or role in {"date", "time"}:
                time_columns.append(name)

            aggregate_members = [value for value in values if value.strip().casefold() in AGGREGATE_LABELS]
            ordinal_overlaps, ordinal_members = self._ordinal_members(values)
            hierarchy_overlaps = self._hierarchy_members(values)
            overlapping_members = list(dict.fromkeys(ordinal_overlaps + hierarchy_overlaps))
            if aggregate_members or overlapping_members:
                dimensions.append({
                    "name": name,
                    "aggregate_members": aggregate_members,
                    "overlapping_members": overlapping_members,
                    "ordinal_members": ordinal_members,
                    "preferred_total_member": aggregate_members[0] if aggregate_members else None,
                })

        return {
            "is_preaggregated_cube": bool(dimensions and measures),
            "dimensions": dimensions,
            "measures": list(dict.fromkeys(measures)),
            "time_columns": list(dict.fromkeys(time_columns)),
        }

    def prompt_context(self, contract: dict[str, Any]) -> str:
        if not contract.get("is_preaggregated_cube"):
            return "No aggregate members were detected in the profile."
        return (
            "Detected aggregation-grain contract (derived from profile values, not dataset identity):\n"
            + json.dumps(contract, ensure_ascii=False)
            + "\nRules: never combine an aggregate member with its children; pin every unused cube dimension "
            "to exactly one aggregate member; when breaking down a dimension, exclude its aggregate and "
            "overlapping members; use a single date for snapshot comparisons."
        )

    def validate_query(self, sql: str, contract: dict[str, Any]) -> tuple[bool, str]:
        if not contract.get("is_preaggregated_cube") or not re.search(r"\b(sum|avg)\s*\(", sql, re.I):
            return True, ""
        normalized = re.sub(r"\s+", " ", sql.casefold())
        group_clause = normalized.split(" group by ", 1)[1].split(" order by ", 1)[0] if " group by " in normalized else ""

        for dimension in contract.get("dimensions", []):
            name = str(dimension.get("name", "")).casefold()
            aggregates = [str(value).casefold() for value in dimension.get("aggregate_members", [])]
            overlaps = [str(value).casefold() for value in dimension.get("overlapping_members", [])]
            ordinal = [str(value).casefold() for value in dimension.get("ordinal_members", [])]
            grouped = bool(re.search(rf'(?<![a-z0-9_])"?{re.escape(name)}"?(?![a-z0-9_])', group_clause))
            if grouped:
                excluded = all(value in normalized for value in aggregates + overlaps)
                has_exclusion = any(token in normalized for token in (" not in ", "<>", "!=", " not regexp", "regexp_matches"))
                safe_whitelist = bool(ordinal and " in " in normalized and all(value in normalized for value in ordinal))
                if (aggregates or overlaps) and not ((excluded and has_exclusion) or safe_whitelist):
                    return False, f'Grouped dimension "{name}" must exclude aggregate/overlapping members.'
            elif aggregates:
                pinned = any(
                    re.search(
                        rf'"?{re.escape(name)}"?[^\n]{{0,80}}=\s*[\'\"]{re.escape(value)}[\'\"]',
                        normalized,
                    )
                    for value in aggregates
                )
                if not pinned:
                    return False, f'Unused cube dimension "{name}" must be pinned to one aggregate member.'
        return True, ""

    def fallback_plan(self, contract: dict[str, Any]) -> dict[str, Any]:
        """Build a safe, schema-agnostic investigation when model SQL violates grain."""
        if not contract.get("is_preaggregated_cube") or not contract.get("measures"):
            return {"queries": []}
        measure = str(contract["measures"][0])
        time_column = str((contract.get("time_columns") or [""])[0])
        dimensions = contract.get("dimensions", [])
        total_dimensions = [item for item in dimensions if item.get("preferred_total_member")]
        if not total_dimensions:
            return {"queries": []}

        total_filters = " AND ".join(
            f'lower(trim(CAST({self._ident(item["name"])} AS VARCHAR))) = {self._literal(str(item["preferred_total_member"]).casefold())}'
            for item in total_dimensions
        )
        queries: list[dict[str, Any]] = []
        if time_column:
            queries.append({
                "sql": (
                    f"SELECT {self._ident(time_column)}, SUM({self._ident(measure)}) AS {self._ident(measure)} "
                    f"FROM dataset WHERE {total_filters} GROUP BY {self._ident(time_column)} "
                    f"ORDER BY {self._ident(time_column)}"
                ),
                "description": f"Verified {measure} trend at the dataset's aggregate grain",
                "confidence": "high",
                "columns_used": [time_column, measure] + [str(item["name"]) for item in total_dimensions],
            })

        for target in total_dimensions[:4]:
            target_name = str(target["name"])
            other_filters = [
                f'lower(trim(CAST({self._ident(item["name"])} AS VARCHAR))) = {self._literal(str(item["preferred_total_member"]).casefold())}'
                for item in total_dimensions
                if item["name"] != target_name
            ]
            ordinal = [str(value) for value in target.get("ordinal_members", [])]
            excluded = [
                str(value).casefold()
                for value in target.get("aggregate_members", []) + target.get("overlapping_members", [])
            ]
            if ordinal:
                target_filter = (
                    f'CAST({self._ident(target_name)} AS VARCHAR) IN '
                    f"({', '.join(self._literal(value) for value in ordinal)})"
                )
            else:
                target_filter = (
                    f'lower(trim(CAST({self._ident(target_name)} AS VARCHAR))) NOT IN '
                    f"({', '.join(self._literal(value) for value in excluded)})"
                )
            filters = other_filters + [target_filter]
            if time_column:
                filters.append(
                    f'{self._ident(time_column)} = (SELECT MAX({self._ident(time_column)}) FROM dataset)'
                )
            queries.append({
                "sql": (
                    f"SELECT {self._ident(target_name)}, SUM({self._ident(measure)}) AS {self._ident(measure)} "
                    f"FROM dataset WHERE {' AND '.join(filters)} GROUP BY {self._ident(target_name)}"
                    + (
                        f" ORDER BY TRY_CAST(regexp_extract(CAST({self._ident(target_name)} AS VARCHAR), '^[0-9]+') AS INTEGER)"
                        if ordinal else ""
                    )
                ),
                "description": f"Latest {measure} breakdown by mutually exclusive {target_name} members",
                "confidence": "high",
                "columns_used": ([time_column] if time_column else []) + [target_name, measure]
                    + [str(item["name"]) for item in total_dimensions if item["name"] != target_name],
            })
        return {"queries": queries}

    @staticmethod
    def _ident(value: str) -> str:
        return '"' + str(value).replace('"', '""') + '"'

    @staticmethod
    def _literal(value: str) -> str:
        return "'" + str(value).replace("'", "''") + "'"

    @staticmethod
    def _ordinal_members(values: list[str]) -> tuple[list[str], list[str]]:
        parsed: list[tuple[str, int, int | None]] = []
        for value in values:
            bounded = re.fullmatch(r"\s*(\d+)\s*-\s*(\d+)\s*", value)
            opened = re.fullmatch(r"\s*(\d+)\s*\+\s*", value)
            if bounded:
                parsed.append((value, int(bounded.group(1)), int(bounded.group(2))))
            elif opened:
                parsed.append((value, int(opened.group(1)), None))
        bounded_ends = [upper for _, _, upper in parsed if upper is not None]
        if len(bounded_ends) < 2:
            return [], []
        max_upper = max(bounded_ends)
        overlaps = [value for value, lower, upper in parsed if upper is None and lower <= max_upper]
        ordinal = [value for value, _, upper in parsed if upper is not None]
        ordinal.extend(value for value, lower, upper in parsed if upper is None and lower > max_upper)
        ordinal.sort(key=lambda value: int(re.match(r"\s*(\d+)", value).group(1)))
        return overlaps, ordinal

    @staticmethod
    def _hierarchy_members(values: list[str]) -> list[str]:
        """Detect parent labels such as `region` beside `region_a` and `region_b`."""
        overlaps: list[str] = []
        for candidate in values:
            normalized = candidate.strip().casefold()
            if len(normalized) < 3 or normalized in AGGREGATE_LABELS:
                continue
            children = [
                value for value in values
                if re.match(rf"^{re.escape(normalized)}[\s_:/-]+.+", value.strip().casefold())
            ]
            if len(children) >= 2:
                overlaps.append(candidate)
        return overlaps
