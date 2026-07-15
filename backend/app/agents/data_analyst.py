from __future__ import annotations

import json
import re
from typing import Literal
from typing import TYPE_CHECKING, Any

import pandas as pd

from app import settings
from app.adapters.analytics_toolkit import AnalyticsToolkit
from app.agents.base import AgentSpec, make_agno_agent
from app.services.profiling import profile_dataframe
from data_berge_core.app_context import APP_CONTEXT
from data_berge_core.contracts import ArtifactStore, ProfileProvider, QueryRunner
from data_berge_core.skills import IntakeSkill, ProfilerSkill, QuerySkill, ReportingSkill, VisualizationSkill
from data_berge_core.contracts import get_flat_profile

if TYPE_CHECKING:
    from app.agents.data_engineer import DataEngineerAgent


class DataAnalystAgent:
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

        plan = self._plan_investigation(readiness_brief, column_info, dataset, report_plan=report_plan)
        findings: list[dict[str, Any]] = []

        for query_spec in plan.get("queries", []):
            sql = query_spec.get("sql", "")
            description = query_spec.get("description", "")
            if not sql:
                continue
            try:
                data = self.query_skill.tools.execute_dataset_sql(project_id, dataset_id, sql, limit=100)
                rows = data.get("data", [])
                chart = self.query_skill.tools.suggest_chart(rows) if rows else None
                if chart and rows:
                    chart["data"] = rows
                confidence = query_spec.get("confidence", "medium")
                # Downgrade confidence if columns are in caution list
                caution = readiness_brief.get("caution_columns", [])
                for col_name in (query_spec.get("columns_used") or []):
                    if col_name in caution and confidence == "high":
                        confidence = "medium"
                findings.append({
                    "finding": description,
                    "sql": sql,
                    "data_preview": rows[:10],
                    "chart": chart,
                    "confidence": confidence,
                    "columns_used": query_spec.get("columns_used", []),
                })
            except Exception:
                continue

        return findings

    def _plan_investigation(
        self,
        readiness_brief: dict[str, Any],
        column_info: list[dict[str, str]],
        dataset: dict[str, Any],
        report_plan: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Use LLM to plan which SQL queries to run for the report."""
        prompt = self._investigation_planning_prompt(
            readiness_brief,
            column_info,
            dataset,
            report_plan=report_plan,
        )
        if not hasattr(self.planner_agent, "run"):
            return self._fallback_investigation_plan(readiness_brief, column_info, dataset)
        try:
            run_output = self.planner_agent.run(prompt, stream=False)
            content = getattr(run_output, "content", None)
            parsed = self._parse_json_content(content)
            if parsed and isinstance(parsed.get("queries"), list):
                return parsed
        except Exception:
            pass
        return self._fallback_investigation_plan(readiness_brief, column_info, dataset)

    def _investigation_planning_prompt(
        self,
        readiness_brief: dict[str, str | list[str] | dict[str, Any]],
        column_info: list[dict[str, str]],
        dataset: dict[str, Any],
        report_plan: dict[str, Any] | None = None,
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

    def should_lead(
        self,
        message: str,
        dataset: dict[str, Any],
        previous_lead: str | None = None,
        history: list[dict[str, Any]] | None = None,
    ) -> bool:
        if self.query_skill._looks_like_data_engineering_question(message, dataset):
            return False
        normalized = re.sub(r"[^a-z0-9]+", " ", message.lower()).strip()
        follow_ups = {"why", "how", "what about that", "what does that mean", "so what", "and then"}
        if previous_lead == "data_analyst" and normalized in follow_ups:
            return True
        return True

    # ------------------------------------------------------------------
    # LLM intent routing
    # ------------------------------------------------------------------

    def _route_intent(
        self,
        message: str,
        dataset: dict[str, Any],
        history: list[dict[str, Any]],
    ) -> dict[str, Any]:
        if "[ANALYST_PARALLEL_SLICE]" in message:
            return {
                "skill": "query",
                "rationale": "Parallel coordinator assigned the analytical slice to the Analyst.",
            }
        normalized = re.sub(r"[^a-z0-9]+", " ", message.lower()).strip()
        if self._looks_like_existing_report_explanation(normalized, history):
            return {
                "skill": "query",
                "rationale": "The user is asking for an explanation of an existing report, not requesting a new report.",
            }
        fallback_skill = self._select_skill(message, dataset, history)
        if fallback_skill == "reporting":
            return {
                "skill": "reporting",
                "rationale": "The user asked for a written report or brief.",
            }
        if self.query_skill.can_answer_without_model(message, dataset):
            return {
                "skill": "query",
                "rationale": "The request can be answered directly without an LLM planning call.",
            }
        plan = self._plan_with_llm(message, dataset, history)
        if plan:
            skill = str(plan.get("skill", "")).strip().lower()
            valid_skills = {"intake", "profiling", "query", "visualization", "reporting"}
            if skill in valid_skills:
                return {"skill": skill, "rationale": plan.get("rationale", "")}
        return {"skill": fallback_skill, "rationale": ""}

    def _plan_with_llm(
        self,
        message: str,
        dataset: dict[str, Any],
        history: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        if not hasattr(self.planner_agent, "run"):
            return None
        prompt = self._intent_routing_prompt(message, dataset, history)
        try:
            run_output = self.planner_agent.run(prompt, stream=False)
            content = getattr(run_output, "content", None)
            return self._parse_json_content(content)
        except Exception:
            return None

    def _intent_routing_prompt(
        self,
        message: str,
        dataset: dict[str, Any],
        history: list[dict[str, Any]],
    ) -> str:
        recent_history = self._compact_history(history)
        profile_summary = self._compact_profile_summary(dataset.get("profile", {}))

        skills_desc = (
            '- "intake": File upload, validation, ingestion, data loading. '
            "Use when user wants to upload or validate a file.\n"
            '- "profiling": Dataset overview, column meanings, data quality, relationships, what stands out. '
            "Use when user wants to understand the dataset structure or quality.\n"
            '- "query": Analytical questions needing calculations, counts, averages, comparisons, SQL, feature importance. '
            "Use for specific data-driven questions and interpretation of existing profile or Data Pulse charts.\n"
            '- "visualization": New charts, plots, or visual representations. '
            "Use when user asks to create a chart, graph, or change chart type.\n"
            '- "reporting": Written reports, summaries, executive briefs, recommendations. '
            "Use when user wants a document or summary.\n"
        )

        rules = (
            "- If the user asks to upload a file or validate data, use intake.\n"
            "- If the user wants to understand dataset structure, quality, columns, or relationships, use profiling.\n"
            "- If the user asks a specific analytical question, use query.\n"
            "- If the user asks to explain or interpret an existing Data Pulse chart or column chart, use query.\n"
            "- If the user asks to create a new chart, plot, or visual representation, use visualization.\n"
            "- If the user wants a written report or summary document, use reporting.\n"
            "- If the user asks to change a chart type (e.g. give me bar chart, make it a donut), use visualization.\n"
            "- If the user asks about UI elements (Data Pulse, column chart, engineering summary), "
            "map them to the correct skill using the app context below.\n"
            "- For ambiguous requests, consider the most recent conversation context.\n"
            "- If the message is a greeting, small talk, or off-topic, use query.\n"
        )

        return (
            "You are the intent router for the DataAnalystAgent in Data-Berge OS.\n"
            "Your job is to understand the user's request and assign it to the correct skill.\n\n"
            "Available skills:\n"
            + skills_desc
            + "\nDecision rules:\n"
            + rules
            + "\nRecent conversation:\n"
            + json.dumps(recent_history, ensure_ascii=False)
            + "\n\nDataset: "
            + str(dataset.get("name", "unknown"))
            + " ("
            + str(dataset.get("row_count", 0))
            + " rows)\nProfile summary: "
            + json.dumps(profile_summary, ensure_ascii=False)
            + "\n\n"
            + APP_CONTEXT
            + "\n\nUser message: "
            + message
            + "\n\nReturn JSON only, no markdown.\n"
            + 'JSON schema:\n{"skill":"intake|profiling|query|visualization|reporting",'
            + '"rationale":"short reason for this choice"}'
        )

    def _compact_history(self, history: list[dict[str, Any]]) -> list[dict[str, str]]:
        compact: list[dict[str, str]] = []
        for item in history[-6:]:
            role = str(item.get("role", ""))
            content = str(item.get("content", "")).strip()
            if not content:
                continue
            compact.append({"role": role, "content": content[:500]})
        return compact

    def _compact_profile_summary(self, profile: dict[str, Any]) -> dict[str, Any]:
        flat = get_flat_profile(profile)
        metadata = flat.get("metadata", {})
        relational_schema = profile.get("relational_schema", {}) or {}
        columns: list[dict[str, Any]] = []
        for col in flat.get("columns", [])[:30]:
            entry: dict[str, Any] = {
                "name": col.get("name"),
                "semantic_type": col.get("semantic_type"),
            }
            for key in ("description", "dtype", "missing_pct", "unique_count"):
                if col.get(key) not in (None, "", []):
                    entry[key] = col.get(key)
            stats = col.get("stats") if isinstance(col.get("stats"), dict) else {}
            if stats:
                entry["stats"] = {
                    key: stats.get(key)
                    for key in ("min", "median", "max", "mean", "std")
                    if stats.get(key) not in (None, "")
                }
            if col.get("top_values"):
                entry["top_values"] = [
                    {
                        "label": value.get("label"),
                        "count": value.get("count"),
                    }
                    for value in col["top_values"][:5]
                    if isinstance(value, dict)
                ]
            columns.append(entry)
        return {
            "row_count": flat.get("row_count"),
            "column_count": flat.get("column_count"),
            "numeric_columns": metadata.get("numeric_columns", [])[:10],
            "categorical_columns": metadata.get("categorical_columns", [])[:10],
            "text_columns": metadata.get("text_columns", [])[:5],
            "quality_flags": flat.get("quality_flags", [])[:3],
            "columns": columns,
            "relational_schema": {
                "name": relational_schema.get("name"),
                "status": relational_schema.get("status"),
                "table_count": relational_schema.get("table_count"),
                "table_names": relational_schema.get("table_names", [])[:20],
                "relationship_count": relational_schema.get("relationship_count"),
                "relationships": relational_schema.get("relationships", [])[:10],
                "analysis_dataset_note": relational_schema.get("analysis_dataset_note"),
            } if relational_schema else None,
        }

    def _parse_json_content(self, content: Any) -> dict[str, Any] | None:
        if isinstance(content, dict):
            return content
        if not isinstance(content, str):
            return None
        text = content.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
            text = re.sub(r"\s*```$", "", text)
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None
        try:
            return json.loads(text[start : end + 1])
        except (json.JSONDecodeError, ValueError):
            return None

    # ------------------------------------------------------------------
    # Keyword-based skill selection (fallback when no LLM)
    # ------------------------------------------------------------------

    def _select_skill(
        self,
        message: str,
        dataset: dict[str, Any],
        history: list[dict[str, Any]],
    ) -> Literal["intake", "profiling", "query", "visualization", "reporting"]:
        normalized = re.sub(r"[^a-z0-9]+", " ", message.lower()).strip()

        if self._looks_like_existing_report_explanation(normalized, history):
            return "query"
        if self._looks_like_report_request(normalized):
            return "reporting"
        if self._looks_like_existing_chart_explanation(normalized):
            return "query"
        if self._looks_like_visualization_request(normalized, history, dataset):
            return "visualization"
        if self._looks_like_intake_request(normalized):
            return "intake"
        if self._looks_like_profiling_request(normalized):
            return "profiling"
        return "query"

    def _looks_like_existing_report_explanation(
        self,
        normalized: str,
        history: list[dict[str, Any]],
    ) -> bool:
        tokens = set(normalized.split())
        explanation_terms = {
            "explain", "explaining", "interpret", "interpretation", "meaning",
            "understand", "describe", "clarify", "why", "how",
        }
        report_terms = {"report", "brief", "document", "artifact"}
        has_attached_report = "attached report" in normalized
        if not tokens.intersection(explanation_terms) or (
            not tokens.intersection(report_terms) and not has_attached_report
        ):
            return False
        if has_attached_report:
            return True
        return any(
            isinstance(item.get("payload"), dict)
            and (
                (
                    isinstance(item["payload"].get("artifact"), dict)
                    and item["payload"]["artifact"].get("kind") == "report"
                )
                or item["payload"].get("action") in {"queued", "saved"}
            )
            for item in history
        )

    def _looks_like_report_request(self, normalized: str) -> bool:
        report_terms = {
            "report", "summary", "summarize", "executive", "stakeholder",
            "board", "brief", "memo", "narrative", "recommendation", "recommendations",
        }
        return bool(set(normalized.split()) & report_terms)

    def _looks_like_existing_chart_explanation(self, normalized: str) -> bool:
        chart_terms = {"chart", "plot", "graph", "histogram", "distribution", "visual", "visualization"}
        explanation_terms = {
            "explain", "interpret", "meaning", "mean", "means", "understand", "about",
            "what", "why", "how", "tell", "describe",
        }
        existing_context_terms = {"data", "pulse", "existing", "current", "this", "that"}
        tokens = set(normalized.split())
        return bool(tokens & chart_terms) and bool(tokens & explanation_terms) and bool(tokens & existing_context_terms)

    def _looks_like_visualization_request(
        self,
        normalized: str,
        history: list[dict[str, Any]],
        dataset: dict[str, Any],
    ) -> bool:
        viz_terms = {
            "chart", "table", "plot", "graph", "visual", "visualize",
            "dashboard", "histogram", "scatter", "pie", "donut",
        }
        if not (set(normalized.split()) & viz_terms):
            return False
        has_profile_match = any(
            self._column_mentioned(normalized, str(column.get("name") or ""))
            or self._profile_value_mentioned(normalized, column)
            for column in get_flat_profile(dataset.get("profile", {})).get("columns", [])
        )
        if has_profile_match:
            return True
        if self._has_specific_chart_target(normalized):
            return True
        if self._last_assistant_payload(history, require_data=True):
            return True
        return False

    def _looks_like_intake_request(self, normalized: str) -> bool:
        intake_terms = {"upload", "uploaded", "file", "csv", "xlsx", "excel", "ingest", "validate", "valid"}
        return bool(set(normalized.split()) & intake_terms)

    def _looks_like_profiling_request(self, normalized: str) -> bool:
        profiling_phrases = {
            "big picture", "overall view", "what stands out",
            "important feature", "column meaning", "column meanings",
        }
        if any(phrase in normalized for phrase in profiling_phrases):
            return True
        profiling_terms = {
            "profile", "overview", "quality", "missing", "null", "duplicate",
            "schema", "meaning", "meanings", "columns", "correlation", "correlations",
            "relationship", "relationships", "driver", "drivers", "readiness", "trust",
        }
        return bool(set(normalized.split()) & profiling_terms)

    def _last_assistant_payload(self, history: list[dict[str, Any]], require_data: bool = False) -> dict[str, Any] | None:
        for item in reversed(history):
            if str(item.get("role")) != "assistant":
                continue
            payload = item.get("payload", {}) or {}
            if require_data and not payload.get("data"):
                continue
            return payload
        return None

    def _column_mentioned(self, normalized_message: str, column_name: str) -> bool:
        normalized_column = re.sub(r"[^a-z0-9]+", " ", column_name.lower()).strip()
        return bool(normalized_column) and normalized_column in normalized_message

    def _profile_value_mentioned(self, normalized_message: str, column: dict[str, Any]) -> bool:
        top_values = column.get("top_values") or []
        mentioned_values = [
            value
            for value in top_values
            if (label := normalize_label(str(value.get("label") or ""))) and label in normalized_message
        ]
        if mentioned_values:
            return True
        return False

    def _has_specific_chart_target(self, normalized_message: str) -> bool:
        return bool(re.search(r"\b(?:for|of|by|about)\s+[a-z0-9]", normalized_message))


def normalize_label(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()
