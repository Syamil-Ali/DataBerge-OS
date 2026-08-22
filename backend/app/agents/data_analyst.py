from __future__ import annotations

import json
import re
from typing import Literal
from typing import TYPE_CHECKING, Any

import pandas as pd

from app import settings
from app.adapters.analytics_toolkit import AnalyticsToolkit
from app.agents.base import AgentSpec, make_agno_agent
from app.agents.data_analyst_routing import DataAnalystRoutingMixin
from app.services.profiling import profile_dataframe
from app.services.llm_observability import set_span_outputs, trace_span
from data_berge_core.app_context import APP_CONTEXT
from data_berge_core.contracts import ArtifactStore, ProfileProvider, QueryRunner
from data_berge_core.skills import AggregationGrainSkill, IntakeSkill, ProfilerSkill, QuerySkill, ReportingSkill, VisualizationSkill
from data_berge_core.contracts import get_flat_profile, normalize_top_values

if TYPE_CHECKING:
    from app.agents.data_engineer import DataEngineerAgent


class DataAnalystAgent(DataAnalystRoutingMixin):
    """Role agent focused on insight generation, reasoning, SQL, charts, and reporting."""

    spec = AgentSpec(
        name="DataAnalystAgent",
        role="Lead analytical conversations, interpret evidence, and answer business questions from datasets.",
        instructions=(
            "Use shared skills for intake, profiling, querying, visualization, and reporting. "
            "Lead when the user asks for insights, comparisons, metrics, explanations, trends, or decisions. "
            "Hand off to the DataEngineerAgent when the conversation shifts to cleaning, typing, schema trust, "
            "joins, or data readiness."
        ),
    )

    def __init__(
        self,
        profile_provider: ProfileProvider | None = None,
        query_runner: QueryRunner | None = None,
        artifact_store: ArtifactStore | None = None,
    ) -> None:
        toolkit_factory = AnalyticsToolkit
        agent_factory = make_agno_agent

        prompt_registry_config = {
            "tracking_enabled": settings.MLFLOW_TRACKING_ENABLED,
            "tracking_uri": settings.MLFLOW_TRACKING_URI,
            "prompt_name": settings.MLFLOW_QUERY_ANALYST_PROMPT_NAME,
            "prompt_version": settings.MLFLOW_QUERY_ANALYST_PROMPT_VERSION,
        }

        self.intake_skill = IntakeSkill(toolkit_factory, agent_factory, profile_provider, query_runner, artifact_store)
        self.profiler_skill = ProfilerSkill(
            toolkit_factory,
            agent_factory,
            profile_provider,
            query_runner,
            artifact_store,
            profile_fn=profile_dataframe,
        )
        self.query_skill = QuerySkill(
            toolkit_factory,
            agent_factory,
            profile_provider,
            query_runner,
            artifact_store,
            prompt_registry_config=prompt_registry_config,
        )
        self.viz_skill = VisualizationSkill(toolkit_factory, agent_factory, profile_provider, query_runner, artifact_store)
        self.report_skill = ReportingSkill(toolkit_factory, agent_factory, profile_provider, query_runner, artifact_store)
        self.aggregation_skill = AggregationGrainSkill()

        self.tools = self.query_skill.tools

        self.agent = agent_factory(
            self.spec,
            tools=[
                self.intake_skill.tools,
                self.profiler_skill.tools,
                self.query_skill.tools,
                self.viz_skill.tools,
                self.report_skill.tools,
            ],
        )

        # LLM planner for intent routing (no tools — pure reasoning)
        self.planner_agent = agent_factory(self.spec, None)

        self.skill_names = ["intake", "profiling", "query", "visualization", "reporting"]

    def profile_dataset(self, df: pd.DataFrame, column_descriptions: dict[str, str] | None = None) -> dict[str, Any]:
        return self.profiler_skill.profile(df, column_descriptions=column_descriptions)

    def investigate_for_report(
        self,
        dataset: dict[str, Any],
        readiness_brief: dict[str, Any],
        report_plan: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Use LLM to plan investigation queries, execute them, and return findings."""
        project_id = str(dataset.get("project_id", ""))
        dataset_id = str(dataset.get("id", ""))
        profile = dataset.get("profile", {}) or {}
        columns = get_flat_profile(profile).get("columns", [])

        # Build a list of available columns with their types
        column_info: list[dict[str, str]] = []
        for col in columns:
            column_info.append({
                "name": str(col.get("name")),
                "type": str(col.get("semantic_type", "unknown")),
                "role": str(col.get("engineering_role", "unknown")),
            })

        with trace_span(
            "investigation.grain_discovery",
            span_type="CHAIN",
            inputs={"profile_columns": columns},
        ) as grain_span:
            observed_values = self._load_dimension_values(dataset, columns)
            grain_contract = self.aggregation_skill.analyze(dataset, observed_values)
            set_span_outputs(grain_span, {
                "observed_dimension_values": observed_values,
                "aggregation_grain_contract": grain_contract,
            })

        with trace_span(
            "investigation.query_planning",
            span_type="AGENT",
            inputs={
                "readiness_brief": readiness_brief,
                "columns": column_info,
                "approved_report_plan": report_plan,
                "aggregation_grain_contract": grain_contract,
            },
        ) as planning_span:
            plan = self._plan_investigation(
                readiness_brief,
                column_info,
                dataset,
                report_plan=report_plan,
                grain_contract=grain_contract,
            )
            set_span_outputs(planning_span, {
                "decision": "execute_validated_queries",
                "query_count": len(plan.get("queries", [])),
                "query_plan": plan,
            })
        findings: list[dict[str, Any]] = []

        for index, query_spec in enumerate(plan.get("queries", []), 1):
            sql = query_spec.get("sql", "")
            description = query_spec.get("description", "")
            if not sql:
                continue
            with trace_span(
                f"investigation.query_{index}",
                span_type="TOOL",
                inputs={
                    "query_index": index,
                    "description": description,
                    "sql": sql,
                    "proposed_confidence": query_spec.get("confidence", "medium"),
                    "columns_used": query_spec.get("columns_used", []),
                    "aggregation_grain_contract": grain_contract,
                },
            ) as query_span:
                safe, reason = self.aggregation_skill.validate_query(sql, grain_contract)
                if not safe:
                    set_span_outputs(query_span, {
                        "decision": "rejected",
                        "validation": {"safe": False, "reason": reason},
                    })
                    continue
                try:
                    data = self.query_skill.tools.execute_dataset_sql(project_id, dataset_id, sql, limit=100)
                    rows = data.get("data", [])
                    chart = self.query_skill.tools.suggest_chart(rows) if rows else None
                    if chart and rows:
                        chart["data"] = rows
                        chart["title"] = description
                    conclusion, evidence = self._summarize_investigation_result(description, rows)
                    confidence = query_spec.get("confidence", "medium")
                    caution = readiness_brief.get("caution_columns", [])
                    downgraded_for: list[str] = []
                    for col_name in (query_spec.get("columns_used") or []):
                        if col_name in caution and confidence == "high":
                            confidence = "medium"
                            downgraded_for.append(str(col_name))
                    finding = {
                        "finding": conclusion,
                        "investigation": description,
                        "evidence": evidence,
                        "sql": sql,
                        "data_preview": rows[:10],
                        "chart": chart,
                        "confidence": confidence,
                        "columns_used": query_spec.get("columns_used", []),
                    }
                    findings.append(finding)
                    set_span_outputs(query_span, {
                        "decision": "accepted_as_verified_finding",
                        "validation": {"safe": True, "reason": reason or "passed"},
                        "row_count": len(rows),
                        "rows": rows,
                        "chart_decision": chart,
                        "confidence_decision": {
                            "final": confidence,
                            "downgraded_for_caution_columns": downgraded_for,
                        },
                        "derived_finding": finding,
                    })
                except Exception as exc:
                    set_span_outputs(query_span, {
                        "decision": "execution_failed",
                        "validation": {"safe": True, "reason": reason or "passed"},
                        "error": str(exc),
                    })
                    continue

        return findings

    @classmethod
    def _summarize_investigation_result(
        cls,
        description: str,
        rows: list[dict[str, Any]],
    ) -> tuple[str, str]:
        """Turn executed rows into a compact conclusion; never expose the plan as the finding."""
        if not rows:
            return "No rows were returned for this investigation.", f"The executed query returned 0 rows. Purpose: {description}"
        keys = list(rows[0].keys())
        numeric_keys = [
            key for key in keys
            if any(isinstance(row.get(key), (int, float)) and not isinstance(row.get(key), bool) for row in rows)
        ]
        label_keys = [key for key in keys if key not in numeric_keys]
        if not numeric_keys:
            preview = ", ".join(f"{key}={rows[0].get(key)}" for key in keys[:3])
            return f"The query returned {len(rows)} rows; the first result is {preview}.", f"Executed result: {preview}."

        measure = numeric_keys[0]
        if len(rows) >= 2 and label_keys and cls._looks_temporal(label_keys[0], rows):
            time_key = label_keys[0]
            first, last = rows[0], rows[-1]
            first_value = first.get(measure)
            last_value = last.get(measure)
            direction = "changed"
            change_text = ""
            if isinstance(first_value, (int, float)) and isinstance(last_value, (int, float)):
                direction = "increased" if last_value > first_value else "decreased" if last_value < first_value else "remained unchanged"
                if first_value:
                    change_text = f" ({((last_value - first_value) / abs(first_value)) * 100:+.1f}%)"
            conclusion = (
                f"{measure.replace('_', ' ').title()} {direction} from {cls._format_result_value(first_value)} "
                f"in {first.get(time_key)} to {cls._format_result_value(last_value)} in {last.get(time_key)}{change_text}."
            )
            evidence = (
                f"Executed query returned {len(rows)} periods: "
                f"{time_key}={first.get(time_key)}, {measure}={cls._format_result_value(first_value)}; "
                f"{time_key}={last.get(time_key)}, {measure}={cls._format_result_value(last_value)}."
            )
            return conclusion, evidence

        comparable = [row for row in rows if isinstance(row.get(measure), (int, float))]
        if comparable:
            highest = max(comparable, key=lambda row: float(row[measure]))
            labels = ", ".join(f"{key}={highest.get(key)}" for key in label_keys) or "the returned result"
            conclusion = (
                f"{labels} has the highest returned {measure.replace('_', ' ')} at "
                f"{cls._format_result_value(highest.get(measure))} across {len(comparable)} results."
            )
            evidence = (
                f"Highest executed-query row: {labels}, "
                f"{measure}={cls._format_result_value(highest.get(measure))}; {len(comparable)} rows compared."
            )
            return conclusion, evidence
        return f"The executed query returned {len(rows)} rows.", f"Executed query returned {len(rows)} rows."

    @staticmethod
    def _looks_temporal(key: str, rows: list[dict[str, Any]]) -> bool:
        if any(token in key.casefold() for token in ("date", "year", "month", "time", "period")):
            return True
        values = [str(row.get(key, "")) for row in rows[:3]]
        return bool(values and all(re.match(r"^\d{4}(?:-|$)", value) for value in values))

    @staticmethod
    def _format_result_value(value: Any) -> str:
        if isinstance(value, float):
            return f"{value:,.2f}".rstrip("0").rstrip(".")
        if isinstance(value, int):
            return f"{value:,}"
        return str(value)

    def _load_dimension_values(
        self,
        dataset: dict[str, Any],
        columns: list[dict[str, Any]],
    ) -> dict[str, list[Any]]:
        """Inspect low-cardinality dimensions so grain analysis is not limited by profile top-N values."""
        project_id = str(dataset.get("project_id", ""))
        dataset_id = str(dataset.get("id", ""))
        observed: dict[str, list[Any]] = {}
        for column in columns:
            name = str(column.get("name", ""))
            semantic_type = str(column.get("semantic_type", "")).casefold()
            role = str(column.get("engineering_role", "")).casefold()
            unique_count = column.get("unique_count")
            if not name or semantic_type not in {"categorical", "text", "string"}:
                if role not in {"dimension", "category", "segment"}:
                    continue
            if isinstance(unique_count, (int, float)) and unique_count > 500:
                continue
            ident = '"' + name.replace('"', '""') + '"'
            sql = f"SELECT DISTINCT {ident} AS member FROM dataset WHERE {ident} IS NOT NULL LIMIT 501"
            try:
                result = self.query_skill.tools.execute_dataset_sql(project_id, dataset_id, sql, limit=501)
                values = [row.get("member") for row in result.get("data", []) if isinstance(row, dict)]
                if len(values) <= 500:
                    observed[name] = values
            except Exception:
                continue
        return observed

    def _plan_investigation(
        self,
        readiness_brief: dict[str, Any],
        column_info: list[dict[str, str]],
        dataset: dict[str, Any],
        report_plan: dict[str, Any] | None = None,
        grain_contract: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Use LLM to plan which SQL queries to run for the report."""
        prompt = self._investigation_planning_prompt(
            readiness_brief,
            column_info,
            dataset,
            report_plan=report_plan,
            grain_contract=grain_contract,
        )
        if not hasattr(self.planner_agent, "run"):
            return self._fallback_investigation_plan(readiness_brief, column_info, dataset)
        try:
            run_output = self.planner_agent.run(prompt, stream=False)
            content = getattr(run_output, "content", None)
            parsed = self._parse_json_content(content)
            if parsed and isinstance(parsed.get("queries"), list):
                if grain_contract and grain_contract.get("is_preaggregated_cube"):
                    proposed_queries = list(parsed["queries"])
                    validation_audit = []
                    accepted_queries = []
                    for index, query in enumerate(proposed_queries, 1):
                        safe, reason = self.aggregation_skill.validate_query(
                            str(query.get("sql", "")), grain_contract
                        )
                        validation_audit.append({
                            "query_index": index,
                            "description": query.get("description"),
                            "sql": query.get("sql"),
                            "decision": "accepted" if safe else "rejected",
                            "reason": reason or "passed aggregation-grain validation",
                        })
                        if safe:
                            accepted_queries.append(query)
                    parsed["queries"] = accepted_queries
                    if len(parsed["queries"]) < 3:
                        existing = {str(query.get("sql", "")).strip() for query in parsed["queries"]}
                        for query in self.aggregation_skill.fallback_plan(grain_contract)["queries"]:
                            if str(query.get("sql", "")).strip() not in existing:
                                parsed["queries"].append(query)
                                validation_audit.append({
                                    "description": query.get("description"),
                                    "sql": query.get("sql"),
                                    "decision": "added_safe_fallback",
                                    "reason": "Fewer than three safe model-planned queries remained.",
                                })
                    parsed["validation_audit"] = validation_audit
                return parsed
        except Exception:
            pass
        if grain_contract and grain_contract.get("is_preaggregated_cube"):
            safe_plan = self.aggregation_skill.fallback_plan(grain_contract)
            if safe_plan.get("queries"):
                return safe_plan
        return self._fallback_investigation_plan(readiness_brief, column_info, dataset)

    def _investigation_planning_prompt(
        self,
        readiness_brief: dict[str, str | list[str] | dict[str, Any]],
        column_info: list[dict[str, str]],
        dataset: dict[str, Any],
        report_plan: dict[str, Any] | None = None,
        grain_contract: dict[str, Any] | None = None,
    ) -> str:
        domain = readiness_brief.get("domain_context", {})
        measures = ", ".join(readiness_brief.get("trustable_measures", []))
        segments = ", ".join(readiness_brief.get("segment_dimensions", []))
        outcomes = ", ".join(readiness_brief.get("outcome_columns", []))
        focus = "\n".join(f"- {f}" for f in readiness_brief.get("recommended_focus", []))
        limitations = "\n".join(f"- {l}" for l in readiness_brief.get("data_limitations", []))
        caution = ", ".join(readiness_brief.get("caution_columns", []))

        columns_text = "\n".join(
            f"  {c['name']}: type={c['type']}, role={c['role']}" for c in column_info
        )
        approved_plan_text = json.dumps(report_plan, ensure_ascii=False) if report_plan else "None"
        grain_context = self.aggregation_skill.prompt_context(grain_contract or {})

        return (
            "You are the DataAnalystAgent planning an investigation for an executive report.\n"
            "Generate a JSON list of SQL queries to investigate this dataset.\n\n"
            f"Dataset: {dataset.get('name', 'unknown')} ({dataset.get('row_count', 0)} rows)\n"
            f"Readiness: {readiness_brief.get('readiness_score', '?')}/10 ({readiness_brief.get('readiness_label', '?')})\n\n"
            f"Columns:\n{columns_text}\n\n"
            f"Trustable numeric measures: {measures}\n"
            f"Segment dimensions: {segments}\n"
            f"Outcome/target columns: {outcomes}\n"
            f"Caution columns (quality issues): {caution}\n\n"
            f"Recommended focus areas:\n{focus}\n\n"
            f"Data limitations:\n{limitations}\n\n"
            f"Approved report plan JSON:\n{approved_plan_text}\n\n"
            f"Aggregation grain analysis:\n{grain_context}\n\n"
            "Generate 5-8 SQL queries that investigate the most important patterns.\n"
            "Use DuckDB SQL syntax. The table name is 'dataset'.\n"
            "Each query should have:\n"
            "- sql: the SQL query\n"
            "- description: a clear description of what this query investigates\n"
            "- confidence: high, medium, or low (based on data quality)\n"
            "- columns_used: list of column names used in this query\n\n"
            "Prioritize:\n"
            "0. Evidence explicitly required by the approved report sections and their data_fields\n"
            "1. Distribution of the outcome/target variable\n"
            "2. Segment comparisons (group by key categories)\n"
            "3. Numeric relationships (correlations, averages by group)\n"
            "4. Top/bottom performers\n"
            "5. Anomaly detection\n\n"
            "Aggregation safety:\n"
            "- Some public datasets are pre-aggregated cubes containing overall/all/both rows alongside detail rows.\n"
            "- Never sum an aggregate member together with its child categories. Pin unused dimensions to one aggregate member.\n"
            "- For a time trend, filter every non-time dimension to its aggregate member before grouping by date.\n"
            "- For a category breakdown, select one date, exclude the aggregate member, and use mutually exclusive categories only.\n\n"
            "Return JSON only, no markdown.\n"
            '{"queries": [{"sql": "...", "description": "...", "confidence": "high", "columns_used": [...]}]}'
        )

    def _fallback_investigation_plan(
        self,
        readiness_brief: dict[str, str | list[str] | dict[str, Any]],
        column_info: list[dict[str, str]],
        dataset: dict[str, Any],
    ) -> dict[str, Any]:
        """Deterministic fallback when LLM is unavailable."""
        measures = readiness_brief.get("trustable_measures", [])
        segments = readiness_brief.get("segment_dimensions", [])
        outcomes = readiness_brief.get("outcome_columns", [])
        queries: list[dict[str, Any]] = []

        # Query 1: Outcome distribution
        if outcomes:
            target = outcomes[0]
            queries.append({
                "sql": f'SELECT "{target}", COUNT(*) AS count FROM dataset GROUP BY "{target}" ORDER BY count DESC',
                "description": f"Distribution of {target}",
                "confidence": "high",
                "columns_used": [target],
            })

        # Query 2: Average measures by outcome
        if measures and outcomes:
            target = outcomes[0]
            agg_parts = ", ".join(f'AVG("{m}") AS avg_{m}' for m in measures[:3])
            queries.append({
                "sql": f'SELECT "{target}", {agg_parts} FROM dataset GROUP BY "{target}"',
                "description": f"Average measures by {target}",
                "confidence": "high",
                "columns_used": [target] + measures[:3],
            })

        # Query 3: Segment comparison
        if segments and measures:
            seg = segments[0]
            measure = measures[0]
            queries.append({
                "sql": f'SELECT "{seg}", AVG("{measure}") AS avg_{measure}, COUNT(*) AS count FROM dataset GROUP BY "{seg}" ORDER BY avg_{measure} DESC',
                "description": f"Average {measure} by {seg}",
                "confidence": "high",
                "columns_used": [seg, measure],
            })

        # Query 4: Top values
        if measures:
            measure = measures[0]
            queries.append({
                "sql": f'SELECT * FROM dataset ORDER BY "{measure}" DESC LIMIT 5',
                "description": f"Top 5 records by {measure}",
                "confidence": "high",
                "columns_used": [measure],
            })

        return {"queries": queries}

    def answer(
        self,
        message: str,
        dataset: dict[str, Any],
        history: list[dict[str, Any]] | None = None,
        data_engineer: "DataEngineerAgent | None" = None,
        allow_handoff: bool = True,
        assigned_skill: Literal["intake", "profiling", "query", "visualization"] | None = None,
    ) -> dict[str, Any]:
        history = history or []

        routing = (
            {
                "skill": assigned_skill,
                "rationale": "Assigned by the TeamManagerAgent.",
                "source": "team_manager",
            }
            if assigned_skill
            else self._route_intent(message, dataset, history)
        )
        active_skill = routing["skill"]

        if active_skill == "intake":
            response = self.intake_skill.answer(dataset, message)
        elif active_skill == "profiling":
            response = self.profiler_skill.answer(dataset, message)
        elif active_skill == "visualization":
            response = self.viz_skill.answer(dataset, message, history)
        elif active_skill == "reporting":
            response = self.report_skill.answer(dataset, message, history)
        else:
            response = self.query_skill.answer(
                message,
                dataset,
                history,
                data_engineer=data_engineer,
                allow_handoff=allow_handoff,
            )

        response["active_skill"] = active_skill
        response["routing"] = {
            "source": routing.get("source", "analyst"),
            "rationale": routing.get("rationale", ""),
        }
        return response
