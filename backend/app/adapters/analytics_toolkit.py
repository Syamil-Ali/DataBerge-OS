from __future__ import annotations

from pathlib import Path
from typing import Any

from app.adapters.local_runtime import LocalArtifactStore, LocalProfileProvider, LocalQueryRunner
from app.services.files import SUPPORTED_EXTENSIONS, load_column_descriptions, load_dataframe
from app.services.profiling import profile_dataframe
from app.storage import database
from data_berge_core.contracts import ArtifactStore, DatasetContext, ProfileProvider, QueryRunner
from data_berge_core.contracts import get_flat_profile, normalize_top_values

try:
    from agno.tools import Toolkit
except Exception:  # pragma: no cover
    Toolkit = object  # type: ignore[assignment,misc]


class AnalyticsToolkit(Toolkit):
    """App-specific toolkit implementation for Data-Berge OS."""

    def __init__(
        self,
        include_tools: list[str] | None = None,
        profile_provider: ProfileProvider | None = None,
        query_runner: QueryRunner | None = None,
        artifact_store: ArtifactStore | None = None,
        active_project_id: str | None = None,
        active_dataset_id: str | None = None,
    ) -> None:
        self.profile_provider = profile_provider or LocalProfileProvider()
        self.query_runner = query_runner or LocalQueryRunner()
        self.artifact_store = artifact_store or LocalArtifactStore(self.profile_provider)
        self.active_project_id = active_project_id
        self.active_dataset_id = active_dataset_id

        tools = [
            self.validate_filename,
            self.get_dataset_profile,
            self.profile_file,
            self.build_safe_query,
            self.execute_dataset_sql,
            self.answer_dataset_question,
            self.suggest_chart,
            self.draft_report_payload,
            self.create_dashboard_artifact,
            self.create_chart_artifact,
            self.create_report_artifact,
            self.list_artifacts,
        ]
        instructions = (
            "Use these tools as the source of truth for dataset profiles, SQL execution, "
            "chart suggestions, report drafting, and artifact governance. Do not invent "
            "analytics results when a tool can compute them."
        )
        if Toolkit is object:
            self.functions = {}
            return
        super().__init__(
            name="data_berge_analytics_tools",
            tools=tools,
            instructions=instructions,
            add_instructions=True,
            include_tools=include_tools,
        )

    def set_active_context(self, project_id: str, dataset_id: str | None = None) -> None:
        self.active_project_id = project_id
        self.active_dataset_id = dataset_id

    def _trusted_project_id(self, project_id: str) -> str:
        return self.active_project_id or project_id

    def _trusted_dataset_id(self, dataset_id: str | None = None) -> str:
        return self.active_dataset_id or str(dataset_id or "")

    def _trusted_context(self, project_id: str, dataset_id: str) -> tuple[str, str]:
        return self._trusted_project_id(project_id), self._trusted_dataset_id(dataset_id)

    def _require_dataset(self, project_id: str, dataset_id: str) -> DatasetContext:
        project_id, dataset_id = self._trusted_context(project_id, dataset_id)
        dataset = self.profile_provider.get_dataset_context(dataset_id, project_id=project_id)
        if dataset is None:
            raise FileNotFoundError("Dataset not found for this project.")
        return dataset

    def validate_filename(self, filename: str) -> dict[str, Any]:
        suffix = Path(filename).suffix.lower()
        if suffix not in SUPPORTED_EXTENSIONS:
            raise ValueError("Only CSV and Excel files are supported in V1.")
        return {"valid": True, "file_type": suffix.removeprefix(".")}

    def get_dataset_profile(self, project_id: str, dataset_id: str) -> dict[str, Any]:
        project_id, dataset_id = self._trusted_context(project_id, dataset_id)
        dataset = self._require_dataset(project_id, dataset_id)
        profile = dict(dataset.profile or {})
        schema = database.get_relational_schema(dataset_id)
        if schema and schema.get("project_id") == project_id:
            profile["relational_schema"] = _relational_schema_context(schema)
        return {
            "dataset_id": dataset.dataset_id,
            "name": dataset.name,
            "row_count": dataset.row_count,
            "column_count": dataset.column_count,
            "profile": profile,
        }

    def profile_file(self, file_path: str) -> dict[str, Any]:
        path = Path(file_path)
        df = load_dataframe(path)
        return profile_dataframe(df, column_descriptions=load_column_descriptions(path))

    def build_safe_query(self, project_id: str, dataset_id: str, message: str) -> dict[str, str | None]:
        project_id, dataset_id = self._trusted_context(project_id, dataset_id)
        dataset = self._require_dataset(project_id, dataset_id)
        sql, evidence_note = self.query_runner.build_safe_query(dataset, message)
        return {"sql": sql, "evidence_note": evidence_note}

    def execute_dataset_sql(self, project_id: str, dataset_id: str, sql: str, limit: int = 100) -> dict[str, Any]:
        project_id, dataset_id = self._trusted_context(project_id, dataset_id)
        dataset = self._require_dataset(project_id, dataset_id)
        data = self.query_runner.run_sql(dataset, sql, limit=limit)
        return {"data": data, "row_count": len(data)}

    def answer_dataset_question(self, project_id: str, dataset_id: str, message: str) -> dict[str, Any]:
        project_id, dataset_id = self._trusted_context(project_id, dataset_id)
        dataset = self._require_dataset(project_id, dataset_id)
        sql, evidence_note = self.query_runner.build_safe_query(dataset, message)
        if not sql:
            answer = self._clarify_dataset_question(dataset.name)
            return {
                "answer": answer,
                "evidence": [
                    evidence_note,
                    f"No SQL was run against dataset '{dataset.name}' because the request was ambiguous.",
                ],
                "sql": None,
                "data": [],
                "chart": None,
                "confidence": 0.62,
                "mode": "clarify",
            }
        data = self.query_runner.run_sql(dataset, sql)
        chart = self.suggest_chart(data)
        answer = self._summarize_query_result(message, data, evidence_note)
        return {
            "answer": answer,
            "evidence": [evidence_note, f"Used dataset '{dataset.name}' with {dataset.row_count} rows."],
            "sql": sql,
            "data": data,
            "chart": chart,
            "confidence": 0.82 if data else 0.55,
            "mode": "sql",
        }

    def suggest_chart(self, data: list[dict[str, Any]]) -> dict[str, Any] | None:
        if not data:
            return None
        keys = list(data[0].keys())
        if len(keys) < 2:
            return None
        numeric_keys = [
            key
            for key in keys
            if any(isinstance(row.get(key), (int, float)) and row.get(key) is not None for row in data)
        ]
        label_keys = [key for key in keys if key not in numeric_keys]
        if len(keys) > 4 or len(numeric_keys) > 2 or len(label_keys) > 1:
            return {"type": "table", "columns": keys, "title": "Generated result table"}
        if label_keys and numeric_keys:
            chart_type = "line" if any(
                token in label_keys[0].casefold() for token in ("date", "year", "month", "time", "period")
            ) else "bar"
            return {"type": chart_type, "x": label_keys[0], "y": numeric_keys[:2], "title": "Generated analysis chart"}
        if len(numeric_keys) >= 2:
            return {"type": "scatter", "x": numeric_keys[0], "y": [numeric_keys[1]], "title": "Numeric relationship"}
        if keys:
            return {"type": "table", "columns": keys, "title": "Generated result table"}
        return None

    def draft_report_payload(
        self,
        project_id: str,
        dataset_id: str,
        audience: str = "Leadership team",
        goal: str = "Identify risks, opportunities, and next actions",
        horizon: str = "Next quarter",
        tone: str = "Strategic",
        focus_areas: list[str] | None = None,
    ) -> dict[str, Any]:
        project_id, dataset_id = self._trusted_context(project_id, dataset_id)
        dataset = self._require_dataset(project_id, dataset_id)
        context = {
            "audience": audience,
            "goal": goal,
            "horizon": horizon,
            "tone": tone,
            "focus_areas": focus_areas or ["growth", "risk", "quality"],
        }
        profile = dataset.profile
        columns = get_flat_profile(profile).get("columns", [])
        numeric = get_flat_profile(profile).get("metadata", {}).get("numeric_columns", [])
        categorical = get_flat_profile(profile).get("metadata", {}).get("categorical_columns", [])
        quality_flags = get_flat_profile(profile).get("quality_flags", [])
        correlations = get_flat_profile(profile).get("correlations", [])[:3]

        key_findings = [
            f"The dataset contains {profile.get('row_count', 0)} rows and {profile.get('column_count', 0)} columns.",
            f"It includes {len(numeric)} numeric fields and {len(categorical)} categorical fields for analysis.",
        ]
        if correlations:
            top = correlations[0]
            key_findings.append(
                f"The strongest numeric relationship is {top['left']} vs {top['right']} with correlation {top['correlation']}."
            )
        if quality_flags:
            key_findings.append(quality_flags[0])

        return {
            "title": f"Executive Report: {dataset.name}",
            "executive_summary": (
                f"For {context['audience']}, this report frames {dataset.name} around "
                f"{context['goal']} over {context['horizon']}. The current data is ready for exploratory decisions, "
                "with final action depending on domain validation."
            ),
            "key_findings": key_findings,
            "business_implications": [
                "Leadership can use this profile to identify which metrics are ready for recurring monitoring.",
                "Data quality issues should be reviewed before using the dataset for high-stakes decisions.",
            ],
            "recommendations": [
                "Approve a starter dashboard for the most important numeric and categorical fields.",
                "Review top correlations with a domain owner before treating them as decision drivers.",
                "Define one measurable business question for the next analysis sprint.",
            ],
            "next_steps": [
                "Validate field definitions and business meaning.",
                "Run focused questions in the chat explorer.",
                "Approve report artifacts once findings match stakeholder expectations.",
            ],
            "charts": self.starter_charts(columns),
            "context": context,
        }

    def create_dashboard_artifact(self, project_id: str, dataset_id: str, title: str, summary: str, charts: list[dict[str, Any]]) -> dict[str, Any]:
        project_id, dataset_id = self._trusted_context(project_id, dataset_id)
        self._require_dataset(project_id, dataset_id)
        return self.artifact_store.create_artifact(
            project_id,
            "dashboard",
            title,
            {"title": title, "summary": summary, "charts": charts},
            dataset_id=dataset_id,
        )

    def create_chart_artifact(self, project_id: str, dataset_id: str, title: str, chart: dict[str, Any], data: list[dict[str, Any]], question: str) -> dict[str, Any]:
        project_id, dataset_id = self._trusted_context(project_id, dataset_id)
        self._require_dataset(project_id, dataset_id)
        return self.artifact_store.create_artifact(
            project_id,
            "chart",
            title,
            {"chart": chart, "data": data, "question": question},
            dataset_id=dataset_id,
        )

    def create_report_artifact(self, project_id: str, dataset_id: str, report: dict[str, Any]) -> dict[str, Any]:
        project_id, dataset_id = self._trusted_context(project_id, dataset_id)
        self._require_dataset(project_id, dataset_id)
        return self.artifact_store.create_artifact(project_id, "report", report["title"], report, dataset_id=dataset_id, status="draft")

    def list_artifacts(self, project_id: str, dataset_id: str | None = None) -> list[dict[str, Any]]:
        project_id = self._trusted_project_id(project_id)
        dataset_id = self.active_dataset_id or dataset_id
        if not self.profile_provider.project_exists(project_id):
            raise FileNotFoundError("Project not found.")
        return self.artifact_store.list_artifacts(project_id, dataset_id)

    def starter_charts(self, columns: list[dict[str, Any]]) -> list[dict[str, Any]]:
        charts: list[dict[str, Any]] = []
        for col in columns:
            if col.get("semantic_type") == "numeric" and col.get("histogram"):
                bins = col["histogram"].get("bins", [])
                counts = col["histogram"].get("counts", [])
                data = [{"bucket": f"{round(bins[i], 2)}-{round(bins[i + 1], 2)}", "count": counts[i]} for i in range(min(len(counts), max(0, len(bins) - 1)))]
                charts.append({"title": f"Distribution of {col['name']}", "type": "bar", "x": "bucket", "y": ["count"], "data": data})
            if col.get("semantic_type") == "categorical" and col.get("top_values"):
                charts.append({"title": f"Top values: {col['name']}", "type": "bar", "x": "label", "y": ["count"], "data": normalize_top_values(col.get("top_values"))})
            if len(charts) >= 3:
                break
        return charts

    def _summarize_query_result(self, message: str, data: list[dict[str, Any]], evidence_note: str) -> str:
        if not data:
            return "I could not find rows for that request. Try asking for a count, average, top category, or missing values."
        if len(data) == 1 and len(data[0]) == 1:
            key, value = next(iter(data[0].items()))
            return f"{evidence_note} The result is {key}: {value}."
        if len(data) <= 5:
            return f"{evidence_note} I found {len(data)} result rows. The leading result is {data[0]}."
        return f"{evidence_note} I found {len(data)} result rows. The top result is {data[0]}."

    def _clarify_dataset_question(self, dataset_name: str) -> str:
        return (
            f"I need one more detail before analyzing {dataset_name}. "
            "Do you want a count or comparison, an average, a top category, a distribution, "
            "a missing-value check, or a relationship between specific fields?"
        )


def _relational_schema_context(schema_record: dict[str, Any]) -> dict[str, Any]:
    schema = schema_record.get("schema", {}) or {}
    tables = schema.get("tables", {}) or {}
    relationships = [
        relationship
        for relationship in schema.get("relationships", []) or []
        if relationship.get("active") is not False
    ]
    return {
        "schema_id": schema_record.get("id"),
        "name": schema_record.get("name"),
        "status": schema_record.get("status"),
        "table_count": len(tables),
        "table_names": list(tables.keys()),
        "relationship_count": len(relationships),
        "tables": [
            {
                "name": name,
                "row_count": table.get("row_count", 0),
                "column_count": table.get("column_count", len(table.get("columns", []) or [])),
                "columns": [column.get("name") for column in (table.get("columns", []) or [])[:12] if column.get("name")],
            }
            for name, table in tables.items()
        ],
        "relationships": [
            {
                "from_table": relationship.get("from_table"),
                "from_column": relationship.get("from_column"),
                "to_table": relationship.get("to_table"),
                "to_column": relationship.get("to_column"),
                "cardinality": relationship.get("cardinality"),
                "confidence": relationship.get("confidence"),
            }
            for relationship in relationships
        ],
        "analysis_dataset_note": "SQL runs on the confirmed model working dataset. Multi-table columns are prefixed as Table__Column.",
    }
