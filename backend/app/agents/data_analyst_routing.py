from __future__ import annotations

import json
import re
from typing import Any, Literal

from data_berge_core.app_context import APP_CONTEXT
from data_berge_core.contracts import get_flat_profile, normalize_top_values


class DataAnalystRoutingMixin:
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
                    for value in normalize_top_values(col.get("top_values"))[:5]
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
        top_values = normalize_top_values(column.get("top_values"))
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
