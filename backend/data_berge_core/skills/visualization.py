from __future__ import annotations

import json
import re
from typing import Any

from data_berge_core.contracts import ArtifactStore, ProfileProvider, QueryRunner
from data_berge_core.runtime import AgentFactory, AgentSpec, ToolkitFactory
from data_berge_core.contracts import get_flat_profile, normalize_top_values


class VisualizationSkill:
    spec = AgentSpec(
        name="VisualizationSkill",
        role="Turn query results into concise dashboard-ready chart suggestions.",
        instructions="Return chart specs that are easy to render in Recharts and useful to business teams.",
    )

    def __init__(
        self,
        toolkit_factory: ToolkitFactory,
        agent_factory: AgentFactory,
        profile_provider: ProfileProvider | None = None,
        query_runner: QueryRunner | None = None,
        artifact_store: ArtifactStore | None = None,
    ) -> None:
        self.tools = toolkit_factory(
            include_tools=["suggest_chart", "create_chart_artifact"],
            profile_provider=profile_provider,
            query_runner=query_runner,
            artifact_store=artifact_store,
        )
        self.agent = agent_factory(self.spec, tools=[self.tools])
        self.planner_agent = agent_factory(self.spec, None)

    def suggest(self, data: list[dict[str, Any]]) -> dict[str, Any] | None:
        return self.tools.suggest_chart(data)

    def answer(
        self,
        dataset: dict[str, Any],
        message: str,
        history: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        history = history or []
        normalized = re.sub(r"[^a-z0-9]+", " ", message.lower()).strip()
        has_specific_target = self._has_specific_chart_target(normalized)
        source = None
        data: list[dict[str, Any]] = []
        profile = self.tools.get_dataset_profile(dataset["project_id"], dataset["id"]).get("profile", {}) or {}
        chart = self._profile_chart(profile, message)
        evidence: list[str] = []

        if chart:
            data = chart.get("data", []) or []
            evidence.append("Built the chart suggestion from the stored profile instead of rerunning a query.")
        else:
            source = None if has_specific_target else self._last_payload_with_data(history)
            data = source.get("data") if source else []
            chart = self.suggest(data) if data else None
            if chart and data:
                evidence.append("Reused the latest analytical result as the chart source.")

        # LLM-based fallback: when keyword matching failed but there is history context,
        # ask the model to interpret the user's intent (e.g. "give me bar chart" after a donut).
        if not chart and source:
            llm_plan = self._plan_with_llm(message, dataset, profile, history)
            if llm_plan:
                chart = self._apply_llm_plan(llm_plan, profile, source)
                if chart:
                    data = chart.get("data", []) or []
                    evidence.append(
                        f"LLM planner interpreted the request: {llm_plan.get('rationale', 're-plotted the previous data.')}"
                    )

        # Last resort: offer a starter chart when there is no history and no column match
        if not chart and not source:
            starter = self._starter_chart(profile)
            if starter:
                chart = starter
                data = starter.get("data", []) or []
                evidence.append("Used a starter chart from the dataset profile as a fallback.")

        if not chart:
            return {
                "answer": (
                    "I can visualize this, but I need either a recent result set to plot or a specific field/distribution to chart. "
                    "Try asking for a chart of a column distribution or ask a focused question first."
                ),
                "evidence": ["No chart was generated because there was no reusable result or profile chart candidate."],
                "sql": None,
                "data": [],
                "chart": None,
                "confidence": 0.64,
                "mode": "clarify",
            }

        answer = self._chart_answer(chart)
        return {
            "answer": answer,
            "evidence": [
                *evidence,
                f"Prepared a visualization suggestion for dataset '{dataset['name']}'.",
            ],
            "sql": source.get("sql") if source else None,
            "data": data,
            "chart": {key: value for key, value in chart.items() if key != "data"},
            "confidence": 0.8,
            "mode": "visualization",
        }

    # ------------------------------------------------------------------
    # LLM planner
    # ------------------------------------------------------------------

    def _plan_with_llm(
        self,
        message: str,
        dataset: dict[str, Any],
        profile: dict[str, Any],
        history: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        if not hasattr(self.planner_agent, "run"):
            return None
        prompt = self._viz_planning_prompt(message, dataset, profile, history)
        try:
            run_output = self.planner_agent.run(prompt, stream=False)
            content = getattr(run_output, "content", None)
            return self._parse_json_content(content)
        except Exception:
            return None

    def _apply_llm_plan(
        self,
        plan: dict[str, Any],
        profile: dict[str, Any],
        source: dict[str, Any],
    ) -> dict[str, Any] | None:
        action = str(plan.get("action", "")).strip().lower()
        chart_type = str(plan.get("chart_type", "")).strip().lower()
        title = str(plan.get("title", "")).strip() or "Chart"

        valid_types = {"bar", "donut", "table", "scatter", "line"}
        if chart_type not in valid_types:
            chart_type = "bar"

        if action == "retype_previous":
            data = source.get("data", [])
            if not data:
                return None
            keys = list(data[0].keys()) if data else []
            if chart_type == "table":
                return {"title": title, "type": "table", "columns": keys, "data": data}
            x_key = plan.get("x_key") or (keys[0] if keys else "label")
            y_keys = plan.get("y_keys") or ([keys[1]] if len(keys) > 1 else ["count"])
            return {"title": title, "type": chart_type, "x": x_key, "y": y_keys, "data": data}

        if action == "new_column":
            column_name = str(plan.get("column_name", "")).strip()
            if not column_name:
                return None
            for column in get_flat_profile(profile).get("columns", []):
                name = str(column.get("name") or "")
                if name.lower() == column_name.lower():
                    return self._build_profile_chart(column, chart_type)
            return None

        return None

    def _build_profile_chart(self, column: dict[str, Any], chart_type: str) -> dict[str, Any] | None:
        name = str(column.get("name") or "chart")
        if column.get("histogram"):
            bins = column["histogram"].get("bins", [])
            counts = column["histogram"].get("counts", [])
            data = [
                {"bucket": f"{round(bins[i], 2)}-{round(bins[i + 1], 2)}", "count": counts[i]}
                for i in range(min(len(counts), max(0, len(bins) - 1)))
            ]
            if chart_type == "table":
                return {"title": f"Distribution of {name}", "type": "table", "columns": ["bucket", "count"], "data": data}
            return {"title": f"Distribution of {name}", "type": "bar", "x": "bucket", "y": ["count"], "data": data}
        if column.get("top_values"):
            data = normalize_top_values(column.get("top_values"))
            if chart_type == "table":
                return {"title": f"Top values: {name}", "type": "table", "columns": ["label", "count"], "data": data}
            return {
                "title": f"Top values: {name}",
                "type": chart_type if chart_type in {"donut", "bar"} else self._categorical_default_type(data),
                "x": "label",
                "y": ["count"],
                "data": data,
            }
        return None

    def _viz_planning_prompt(
        self,
        message: str,
        dataset: dict[str, Any],
        profile: dict[str, Any],
        history: list[dict[str, Any]],
    ) -> str:
        recent_history = self._compact_history(history)
        previous_chart = self._previous_chart_summary(history)
        available_columns = self._compact_column_list(profile)

        return (
            "You are the VisualizationSkill planner for Data-Berge OS.\n"
            "Your job is to interpret the user's visualization request in conversation context\n"
            "and return a JSON plan for what chart to build.\n\n"
            "You have access to:\n"
            "- The user's current message\n"
            "- Recent conversation history\n"
            "- The previous chart (if any) with its data summary\n"
            "- Available dataset columns with their types and sample data\n\n"
            "Choose exactly one action:\n"
            '- "retype_previous": The user wants to change the chart type of the previous chart (e.g. "give me bar chart" after a donut). '
            "Keep the same data, change the chart type.\n"
            '- "new_column": The user wants to visualize a specific column from the dataset profile.\n'
            '- "none": The request is ambiguous, off-topic, or cannot be visualized.\n\n'
            "Decision rules:\n"
            '- If the user says things like "give me bar chart", "show as donut", "make it a table", "switch to line", '
            "they want to retype the previous chart.\n"
            '- If the user mentions a column name or a concept that maps to a column (e.g. "approval", "income"), use new_column.\n'
            "- If the message is vague or off-topic, use none.\n"
            "- For retype_previous, set x_key and y_keys to match the previous chart's data keys.\n"
            "- For new_column, set column_name to the exact column name from the profile.\n\n"
            f"Dataset: {dataset.get('name', 'unknown')}\n"
            f"Rows: {dataset.get('row_count', 0)}\n"
            f"Previous chart: {json.dumps(previous_chart, ensure_ascii=False) if previous_chart else 'none'}\n"
            f"Recent conversation: {json.dumps(recent_history, ensure_ascii=False)}\n"
            f"Available columns: {json.dumps(available_columns, ensure_ascii=False)}\n"
            f"User message: {message}\n\n"
            "Return JSON only, no markdown.\n"
            "JSON schema:\n"
            '{"action":"retype_previous|new_column|none","chart_type":"bar|donut|table|scatter|line",'
            '"title":"chart title","column_name":"column name or empty","x_key":"x axis key or empty",'
            '"y_keys":["y keys"],"rationale":"short reason"}'
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

    def _previous_chart_summary(self, history: list[dict[str, Any]]) -> dict[str, Any] | None:
        payload = self._last_payload_with_data(history)
        if not payload:
            return None
        chart = payload.get("chart") or {}
        data = payload.get("data") or []
        data_preview = data[:5] if data else []
        return {
            "chart_type": chart.get("type"),
            "title": chart.get("title"),
            "x": chart.get("x"),
            "y": chart.get("y"),
            "data_row_count": len(data),
            "data_preview": data_preview,
        }

    def _compact_column_list(self, profile: dict[str, Any]) -> list[dict[str, Any]]:
        columns: list[dict[str, Any]] = []
        for col in get_flat_profile(profile).get("columns", [])[:30]:
            entry: dict[str, Any] = {
                "name": col.get("name"),
                "semantic_type": col.get("semantic_type"),
            }
            if col.get("top_values"):
                entry["top_values"] = normalize_top_values(col.get("top_values"))[:3]
            if col.get("histogram"):
                entry["has_histogram"] = True
            columns.append(entry)
        return columns

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
    # Keyword-based chart matching (deterministic, no LLM)
    # ------------------------------------------------------------------

    def _last_payload_with_data(self, history: list[dict[str, Any]]) -> dict[str, Any] | None:
        for item in reversed(history):
            if str(item.get("role")) != "assistant":
                continue
            payload = item.get("payload", {}) or {}
            if payload.get("data"):
                return payload
        return None

    def _profile_chart(self, profile: dict[str, Any], message: str) -> dict[str, Any] | None:
        normalized = re.sub(r"[^a-z0-9]+", " ", message.lower()).strip()
        requested_type = self._requested_chart_type(normalized)
        for column in get_flat_profile(profile).get("columns", []):
            name = str(column.get("name") or "")
            if not name or not self._message_matches_column(normalized, column):
                continue
            if column.get("histogram"):
                bins = column["histogram"].get("bins", [])
                counts = column["histogram"].get("counts", [])
                data = [
                    {"bucket": f"{round(bins[i], 2)}-{round(bins[i + 1], 2)}", "count": counts[i]}
                    for i in range(min(len(counts), max(0, len(bins) - 1)))
                ]
                if requested_type == "table":
                    return {"title": f"Distribution of {name}", "type": "table", "columns": ["bucket", "count"], "data": data}
                return {"title": f"Distribution of {name}", "type": "bar", "x": "bucket", "y": ["count"], "data": data}
            if column.get("top_values"):
                data = normalize_top_values(column.get("top_values"))
                if requested_type == "table":
                    return {"title": f"Top values: {name}", "type": "table", "columns": ["label", "count"], "data": data}
                return {
                    "title": f"Top values: {name}",
                    "type": requested_type if requested_type in {"donut", "bar"} else self._categorical_default_type(data),
                    "x": "label",
                    "y": ["count"],
                    "data": data,
                }

        # When no column matched, return None so answer() can fall back to
        # history data via the LLM planner (e.g. "give me bar chart" after a donut was shown).
        return None

    def _starter_chart(self, profile: dict[str, Any]) -> dict[str, Any] | None:
        """Return the first starter chart from the profile as a last-resort fallback."""
        for chart in self.tools.starter_charts(get_flat_profile(profile).get("columns", []) or []):
            if chart.get("data"):
                return chart
        return None

    def _message_matches_column(self, normalized_message: str, column: dict[str, Any]) -> bool:
        name = str(column.get("name") or "")
        normalized_name = normalize_name(name)
        if normalized_name and normalized_name in normalized_message:
            return True
        for item in normalize_top_values(column.get("top_values")):
            label = normalize_name(str(item.get("label") or ""))
            if label and label in normalized_message:
                return True
        return False

    def _has_specific_chart_target(self, normalized_message: str) -> bool:
        return bool(re.search(r"\b(?:for|of|by|about)\s+[a-z0-9]", normalized_message))

    def _requested_chart_type(self, normalized_message: str) -> str | None:
        tokens = set(normalized_message.split())
        if tokens & {"table", "tabular"}:
            return "table"
        if tokens & {"pie", "donut", "doughnut"}:
            return "donut"
        if tokens & {"bar", "bars"}:
            return "bar"
        if tokens & {"scatter"}:
            return "scatter"
        if tokens & {"line", "trend"}:
            return "line"
        return None

    def _categorical_default_type(self, data: list[dict[str, Any]]) -> str:
        return "donut" if 2 <= len(data) <= 5 else "bar"

    def _chart_answer(self, chart: dict[str, Any]) -> str:
        chart_type = chart.get("type", "chart")
        if chart_type == "table":
            return "I'd show this as a table so the exact values are easy to read."
        if chart_type == "donut":
            return (
                f"I'd show this as a donut chart with `{chart.get('x')}` as the slice label "
                f"and {', '.join(chart.get('y', []) or [])} as the value."
            )
        if chart.get("x") and chart.get("y"):
            return (
                f"I'd show this as a {chart_type} chart"
                f" with `{chart.get('x')}` on the x-axis and {', '.join(chart.get('y', []) or [])} on the y-axis."
            )
        return f"I'd show this as a {chart_type} chart."


def normalize_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", name.lower()).strip()
