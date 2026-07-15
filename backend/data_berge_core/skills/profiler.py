from __future__ import annotations

import pandas as pd
import re
from typing import Any

from data_berge_core.contracts import ArtifactStore, ProfileProvider, QueryRunner
from data_berge_core.runtime import AgentFactory, AgentSpec, ToolkitFactory
from data_berge_core.contracts import get_flat_profile


class ProfilerSkill:
    spec = AgentSpec(
        name="ProfilerSkill",
        role="Generate business-readable dataset profiles.",
        instructions=(
            "Summarize schema, quality, distributions, correlations, and readiness risks. "
            "Translate raw statistics into three lenses: executive risk/opportunity, analyst signal validity, "
            "and engineering/data-prep tasks. Call out imbalance, missingness, outliers, proxy variables, "
            "and whether the profile is enough for decision-making or needs deeper modeling."
        ),
    )

    def __init__(
        self,
        toolkit_factory: ToolkitFactory,
        agent_factory: AgentFactory,
        profile_provider: ProfileProvider | None = None,
        query_runner: QueryRunner | None = None,
        artifact_store: ArtifactStore | None = None,
        profile_fn=None,
    ) -> None:
        self.profile_fn = profile_fn
        self.tools = toolkit_factory(
            include_tools=["get_dataset_profile", "profile_file"],
            profile_provider=profile_provider,
            query_runner=query_runner,
            artifact_store=artifact_store,
        )
        self.agent = agent_factory(self.spec, tools=[self.tools])

    def profile(self, df: pd.DataFrame, column_descriptions: dict[str, str] | None = None) -> dict:
        if self.profile_fn is None:
            raise RuntimeError("ProfilerSkill requires a profile_fn implementation from the host app.")
        return self.profile_fn(df, column_descriptions=column_descriptions)

    def answer(self, dataset: dict[str, Any], message: str) -> dict[str, Any]:
        runtime_profile = dataset.get("profile", {}) or {}
        if runtime_profile.get("relational_schema"):
            profile = runtime_profile
        else:
            payload = self.tools.get_dataset_profile(dataset["project_id"], dataset["id"])
            profile = payload.get("profile", {}) or {}
        normalized = re.sub(r"[^a-z0-9]+", " ", message.lower()).strip()
        tokens = set(normalized.split())

        if tokens & {"column", "columns", "meaning", "meanings", "describe", "description", "schema"}:
            answer = self._column_meaning_answer(profile)
        elif tokens & {"quality", "missing", "null", "nulls", "duplicate", "duplicates", "readiness", "trust"}:
            answer = self._quality_answer(profile)
        elif "important feature" in normalized or tokens & {"relationship", "relationships", "correlation", "correlations", "driver", "drivers", "overview"}:
            answer = self._relationship_answer(profile)
        else:
            answer = self._overview_answer(profile)

        relational_schema = profile.get("relational_schema")
        flat = get_flat_profile(profile)
        profile_evidence = (
            f"Profile is a relational model with {relational_schema.get('table_count', 0)} tables."
            if isinstance(relational_schema, dict)
            else f"Profile includes {flat.get('row_count', 0)} rows and {flat.get('column_count', 0)} columns."
        )
        return {
            "answer": answer,
            "evidence": [
                f"Used the stored profile for dataset '{dataset['name']}'.",
                profile_evidence,
            ],
            "sql": None,
            "data": [],
            "chart": None,
            "confidence": 0.8,
            "mode": "profile",
        }

    def _overview_answer(self, profile: dict[str, Any]) -> str:
        relational_schema = profile.get("relational_schema")
        if isinstance(relational_schema, dict) and relational_schema.get("table_count"):
            return self._relational_overview_answer(profile, relational_schema)

        flat = get_flat_profile(profile)
        metadata = flat.get("metadata", {}) or {}
        quality_flags = flat.get("quality_flags", []) or []
        flags = " ".join(str(item) for item in quality_flags[:3]) or "No major quality flags were recorded."
        return (
            f"The dataset profile has {flat.get('row_count', 0)} rows and {flat.get('column_count', 0)} columns. "
            f"It includes {len(metadata.get('numeric_columns', []) or [])} numeric fields, "
            f"{len(metadata.get('categorical_columns', []) or [])} categorical fields, and "
            f"{len(metadata.get('text_columns', []) or [])} text fields. "
            f"{flags}"
        )

    def _relational_overview_answer(self, profile: dict[str, Any], relational_schema: dict[str, Any]) -> str:
        source_intro = self._relational_source_intro(relational_schema)
        if source_intro:
            return source_intro

        tables = relational_schema.get("tables", []) or []
        relationships = relational_schema.get("relationships", []) or []
        table_count = relational_schema.get("table_count", len(tables))
        table_names = relational_schema.get("table_names", []) or [table.get("name") for table in tables]
        table_bits = []
        for table in tables[:8]:
            table_bits.append(
                f"{table.get('name')} ({table.get('row_count', 0)} rows, {table.get('column_count', 0)} columns)"
            )
        table_summary = "; ".join(table_bits) if table_bits else ", ".join(str(name) for name in table_names)
        relationship_summary = (
            f"It has {len(relationships)} active relationship{'s' if len(relationships) != 1 else ''}."
            if relationships
            else "It does not currently have active relationships."
        )
        working_note = ""
        if profile.get("row_count") is not None and profile.get("column_count") is not None:
            working_note = (
                f" The {profile.get('row_count', 0)} rows and {profile.get('column_count', 0)} columns are the working analysis table, "
                "not the relational model itself."
            )
        return (
            f"This is a relational data model with {table_count} tables: {table_summary}. "
            f"{relationship_summary}{working_note}"
        )

    def _relational_source_intro(self, relational_schema: dict[str, Any]) -> str:
        source = relational_schema.get("source") or {}
        if source.get("source_type") != "opendosm":
            return ""

        title = source.get("title") or relational_schema.get("name") or "this OpenDOSM dataset"
        description = str(source.get("description") or "").strip()
        frequency = source.get("frequency")
        data_source = self._format_source_value(source.get("data_source"))
        data_as_of = source.get("data_as_of") or source.get("last_updated")
        sample_limit = source.get("sample_limit")

        tables = relational_schema.get("tables", []) or []
        table_bits = []
        for table in tables[:4]:
            columns = ", ".join(str(column) for column in (table.get("columns") or [])[:6])
            described = "; ".join(
                f"{item.get('name')}: {item.get('description')}"
                for item in (table.get("described_columns") or [])[:4]
            )
            detail = f"{table.get('name')} has {table.get('row_count', 0)} rows and {table.get('column_count', 0)} columns"
            if columns:
                detail += f" including {columns}"
            if described:
                detail += f". Column meaning: {described}"
            table_bits.append(detail)

        parts = [f"{title} is an OpenDOSM dataset."]
        if description:
            parts.append(description)
        meta = []
        if frequency:
            meta.append(f"frequency: {frequency}")
        if data_source:
            meta.append(f"source: {data_source}")
        if data_as_of:
            meta.append(f"data as of/update: {data_as_of}")
        if meta:
            parts.append("Catalogue metadata: " + "; ".join(str(item) for item in meta) + ".")
        if table_bits:
            sample_detail = " ".join(table_bits).rstrip(".")
            parts.append("In the current workspace sample, " + sample_detail + ".")
        if sample_limit:
            parts.append(f"Note: this connector is currently loading the first {sample_limit} rows, so the workspace is a sample until the download limit is increased.")
        return " ".join(parts)

    def _format_source_value(self, value: Any) -> str:
        if isinstance(value, list):
            return ", ".join(str(item) for item in value if str(item).strip())
        return str(value) if value not in (None, "") else ""

    def _quality_answer(self, profile: dict[str, Any]) -> str:
        metadata = get_flat_profile(profile).get("metadata", {}) or {}
        quality_flags = get_flat_profile(profile).get("quality_flags", []) or []
        missing_cells = metadata.get("missing_cells", 0)
        duplicate_rows = metadata.get("duplicate_rows", 0)
        described = metadata.get("described_columns", 0)
        column_count = get_flat_profile(profile).get("column_count", 0)
        details = " ".join(str(item) for item in quality_flags[:4])
        return (
            f"Quality summary: {missing_cells} missing cells and {duplicate_rows} duplicate rows. "
            f"{described} of {column_count} columns have human descriptions. "
            f"{details}".strip()
        )

    def _relationship_answer(self, profile: dict[str, Any]) -> str:
        bivariate = get_flat_profile(profile).get("bivariate_analysis", {}) or {}
        numeric = sorted(
            [item for item in (bivariate.get("numeric_numeric", []) or get_flat_profile(profile).get("correlations", []) or []) if item.get("correlation") is not None],
            key=lambda item: abs(float(item.get("correlation") or 0)),
            reverse=True,
        )[:2]
        mixed = sorted(
            [item for item in bivariate.get("numeric_categorical", []) or [] if item.get("p_value") is not None],
            key=lambda item: (float(item.get("p_value") or 1), -float(item.get("anova_F") or 0)),
        )[:2]
        parts: list[str] = []
        if numeric:
            parts.append(
                "Top numeric relationships: "
                + "; ".join(
                    f"{item.get('left')} vs {item.get('right')} correlation {self._format_number(item.get('correlation'))}"
                    for item in numeric
                )
                + "."
            )
        if mixed:
            parts.append(
                "Strong group differences: "
                + "; ".join(
                    f"{item.get('numeric')} by {item.get('categorical')} p-value {self._format_number(item.get('p_value'))}"
                    for item in mixed
                )
                + "."
            )
        if not parts:
            return "The stored profile does not show enough paired-field evidence yet to summarize relationships confidently."
        return " ".join(parts)

    def _column_meaning_answer(self, profile: dict[str, Any]) -> str:
        column_parts: list[str] = []
        for column in get_flat_profile(profile).get("columns", [])[:12]:
            name = str(column.get("name") or "")
            if not name:
                continue
            description = str(column.get("description") or "").strip()
            semantic_type = str(column.get("semantic_type") or "unknown")
            if description:
                column_parts.append(f"{name}: {description} [{semantic_type}]")
            else:
                column_parts.append(f"{name}: inferred as {semantic_type}")
        if not column_parts:
            return "I do not have enough profile metadata yet to explain the columns."
        return "Here is the current column meaning map: " + " | ".join(column_parts) + "."

    def _format_number(self, value: Any) -> str:
        if value is None:
            return "n/a"
        if isinstance(value, (int, float)):
            if abs(float(value)) < 0.0001 and float(value) != 0:
                return f"{float(value):.2e}"
            return f"{float(value):.4g}"
        return str(value)
