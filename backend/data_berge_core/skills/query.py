from __future__ import annotations

import json
import re
from typing import Any

from data_berge_core.contracts import ArtifactStore, ProfileProvider, QueryRunner, get_flat_profile
from data_berge_core.runtime import AgentFactory, AgentSpec, ToolkitFactory

try:
    import mlflow
except Exception:  # pragma: no cover - prompt registry should never block local fallback
    mlflow = None  # type: ignore[assignment]


def normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(text).lower()).strip()


class QuerySkill:
    spec = AgentSpec(
        name="QuerySkill",
        role="Act as a careful data analyst skill for uploaded datasets.",
        instructions=(
            "Understand the user's question first. Use the stored profile for whole-dataset reasoning, "
            "data quality, likely drivers, relationships, and limitations. Use SQL only when a fresh "
            "aggregate, filter, count, or row-level calculation is actually needed. Do not produce charts "
            "unless the question benefits from a visualization."
        ),
    )

    def __init__(
        self,
        toolkit_factory: ToolkitFactory,
        agent_factory: AgentFactory,
        profile_provider: ProfileProvider | None = None,
        query_runner: QueryRunner | None = None,
        artifact_store: ArtifactStore | None = None,
        prompt_registry_config: dict[str, Any] | None = None,
    ) -> None:
        self.prompt_registry_config = prompt_registry_config or {}
        self.tools = toolkit_factory(
            include_tools=[
                "get_dataset_profile",
                "build_safe_query",
                "execute_dataset_sql",
                "answer_dataset_question",
                "suggest_chart",
                "create_chart_artifact",
            ],
            profile_provider=profile_provider,
            query_runner=query_runner,
            artifact_store=artifact_store,
        )
        self.agent = agent_factory(self.spec, tools=[self.tools])
        self.planner_agent = agent_factory(self.spec, None)

    def answer(
        self,
        message: str,
        dataset: dict[str, Any],
        history: list[dict[str, Any]] | None = None,
        data_engineer: Any | None = None,
        allow_handoff: bool = True,
    ) -> dict[str, Any]:
        non_analytics_response = self._non_analytics_response(message)
        if non_analytics_response:
            return non_analytics_response
        contextual_message = self._contextualize_follow_up(message, history or [])
        shape_response = self._answer_dataset_shape_question(contextual_message, dataset)
        if shape_response:
            return shape_response
        analyst_parallel_slice = "[ANALYST_PARALLEL_SLICE]" in contextual_message
        if allow_handoff and data_engineer and self._looks_like_data_engineering_question(contextual_message, dataset):
            return data_engineer.answer(contextual_message, dataset, history or [])
        lookup_response = self._answer_direct_lookup_questions(contextual_message, dataset)
        if lookup_response:
            return lookup_response
        model_response = self._answer_with_analyst_plan(
            contextual_message,
            dataset,
            history or [],
            data_engineer=data_engineer if allow_handoff else None,
        )
        if model_response:
            if not analyst_parallel_slice or model_response.get("mode") == "sql":
                return model_response
        if not analyst_parallel_slice:
            profile_response = self._answer_from_profile(contextual_message, dataset)
            if profile_response:
                return profile_response
        model_sql_response = self._answer_with_model(contextual_message, dataset)
        if model_sql_response:
            return model_sql_response
        return self.tools.answer_dataset_question(dataset["project_id"], dataset["id"], contextual_message)

    def can_answer_without_model(self, message: str, dataset: dict[str, Any]) -> bool:
        return bool(
            self._non_analytics_response(message)
            or self._is_dataset_shape_question(message)
        )

    def _answer_dataset_shape_question(
        self,
        message: str,
        dataset: dict[str, Any],
    ) -> dict[str, Any] | None:
        normalized = normalize(message)
        if not self._is_dataset_shape_question(normalized):
            return None

        tokens = set(normalized.split())
        profile = get_flat_profile(dataset.get("profile", {}))
        columns = [
            str(column.get("name"))
            for column in profile.get("columns", [])
            if isinstance(column, dict) and column.get("name")
        ]
        dataset_name = str(dataset.get("name") or "The dataset")

        if tokens & {"row", "rows", "record", "records", "observation", "observations"}:
            row_count = profile.get("row_count")
            if row_count is None:
                row_count = dataset.get("row_count", 0)
            return self._profile_response(
                dataset,
                f"{dataset_name} has {row_count} rows.",
                ["Answered directly from the stored dataset shape."],
                confidence=0.99,
            )

        column_count = profile.get("column_count")
        if column_count is None:
            column_count = dataset.get("column_count")
        if column_count is None:
            column_count = len(columns)

        answer = f"{dataset_name} has {column_count} fields"
        if columns:
            visible = columns[:12]
            names = self._human_join(visible)
            if len(columns) > len(visible):
                names += f", plus {len(columns) - len(visible)} more"
            answer += f": {names}"
        answer += "."
        return self._profile_response(
            dataset,
            answer,
            ["Answered directly from the stored column count and field names."],
            confidence=0.99,
        )

    def _is_dataset_shape_question(self, message: str) -> bool:
        normalized = normalize(message)
        tokens = set(normalized.split())
        if tokens & {"missing", "null", "empty", "blank"}:
            return False
        field_terms = {"field", "fields", "column", "columns", "variable", "variables", "feature", "features"}
        row_terms = {"row", "rows", "record", "records", "observation", "observations"}
        asks_count = (
            "how many" in normalized
            or "number of" in normalized
            or "count of" in normalized
            or "field count" in normalized
            or "column count" in normalized
            or "row count" in normalized
        )
        asks_names = (
            normalized.startswith(("what fields", "which fields", "what columns", "which columns"))
            or "fields are in" in normalized
            or "columns are in" in normalized
        )
        return (asks_count and bool(tokens & (field_terms | row_terms))) or asks_names

    def _human_join(self, values: list[str]) -> str:
        if not values:
            return ""
        if len(values) == 1:
            return values[0]
        if len(values) == 2:
            return f"{values[0]} and {values[1]}"
        return ", ".join(values[:-1]) + f", and {values[-1]}"

    def _answer_direct_lookup_questions(self, message: str, dataset: dict[str, Any]) -> dict[str, Any] | None:
        questions = [part.strip() for part in re.split(r"\?+", message) if part.strip()]
        if not questions:
            return None
        if len(questions) == 1 and not self._looks_like_direct_lookup(questions[0]):
            return None
        if len(questions) > 1 and not all(self._looks_like_direct_lookup(question) for question in questions):
            return None

        profile = get_flat_profile(dataset.get("profile", {}))
        columns = [str(column.get("name")) for column in profile.get("columns", []) if column.get("name")]
        if not columns:
            return None

        answers: list[str] = []
        evidence: list[str] = ["Detected direct record lookup questions and queried matching identifier/name fields."]
        all_rows: list[dict[str, Any]] = []
        sql_parts: list[str] = []

        for question in questions:
            lookup = self._extract_lookup_value(question)
            if not lookup:
                return None
            where_columns = self._lookup_columns_for_value(lookup, columns)
            if not where_columns:
                return None
            where_clause = " OR ".join(
                f"lower(cast({self._quote_ident(column)} as varchar)) = lower({self._quote_literal(lookup)})"
                for column in where_columns
            )
            sql = f"select * from dataset where {where_clause} limit 20"
            try:
                result = self.tools.execute_dataset_sql(dataset["project_id"], dataset["id"], sql, limit=20)
            except Exception:
                return None
            rows = result.get("data", []) or []
            all_rows.extend(rows[:5])
            sql_parts.append(sql)
            answers.append(self._format_lookup_answer(question, lookup, rows, columns))

        return {
            "answer": " ".join(answers),
            "evidence": evidence + [f"Ran {len(sql_parts)} safe lookup query{'ies' if len(sql_parts) != 1 else ''} against dataset '{dataset['name']}'."],
            "sql": ";\n".join(sql_parts),
            "data": all_rows[:20],
            "chart": None,
            "confidence": 0.86,
            "mode": "sql",
        }

    def _looks_like_direct_lookup(self, question: str) -> bool:
        normalized = normalize(question)
        starts = (
            "who is ",
            "what is ",
            "what are ",
            "show ",
            "show me ",
            "when was ",
            "when is ",
            "where is ",
            "give me ",
            "find ",
            "lookup ",
        )
        lookup_terms = {"email", "phone", "status", "created", "customer", "order", "id", "name"}
        return normalized.startswith(starts) or bool(set(normalized.split()) & lookup_terms and self._extract_lookup_value(question))

    def _extract_lookup_value(self, question: str) -> str | None:
        id_match = re.search(r"\b[A-Z]{2,}[A-Z0-9_-]*\d+[A-Z0-9_-]*\b", question)
        if id_match:
            return id_match.group(0)
        quoted = re.search(r"['\"]([^'\"]+)['\"]", question)
        if quoted:
            return quoted.group(1).strip()
        name_match = re.search(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\b", question)
        if name_match:
            value = name_match.group(1).strip()
            value = re.sub(r"^(Show|Find|Lookup)\s+", "", value).strip()
            value = re.sub(r"^Give\s+Me\s+", "", value, flags=re.IGNORECASE).strip()
            if value.lower() not in {"what is", "who is", "when was"} and len(value.split()) >= 2:
                return value
        return None

    def _lookup_columns_for_value(self, lookup: str, columns: list[str]) -> list[str]:
        normalized_lookup = normalize(lookup)
        column_scores: list[tuple[int, str]] = []
        looks_like_id = bool(re.search(r"\d", lookup)) and lookup.upper() == lookup
        for column in columns:
            normalized_column = normalize(column)
            score = 0
            if looks_like_id and ("id" in normalized_column or normalized_column.endswith("key")):
                score += 5
            if not looks_like_id and "name" in normalized_column:
                score += 5
            if normalized_lookup.startswith("cust") and "customer" in normalized_column:
                score += 3
            if any(term in normalized_column for term in ["email", "phone", "status", "created", "date", "name", "id"]):
                score += 1
            if score:
                column_scores.append((score, column))
        ranked = [column for _, column in sorted(column_scores, key=lambda item: (-item[0], item[1]))]
        return ranked[:8] if ranked else columns[:12]

    def _format_lookup_answer(
        self,
        question: str,
        lookup: str,
        rows: list[dict[str, Any]],
        columns: list[str],
    ) -> str:
        if not rows:
            return f"I could not find a matching record for {lookup}."

        target_column = self._target_column_for_question(question, columns)
        if target_column:
            values = self._unique_values(rows, target_column)
            value = ", ".join(values) if values else "not available"
            return f"{self._clean_question_label(question)}: {value}."

        summary_columns = self._summary_columns(columns)
        parts = []
        for column in summary_columns:
            values = self._unique_values(rows, column)
            if values:
                parts.append(f"{self._display_column_name(column)} = {', '.join(values[:3])}")
        return f"{self._clean_question_label(question)}: " + ("; ".join(parts) if parts else f"found {len(rows)} matching row(s)") + "."

    def _target_column_for_question(self, question: str, columns: list[str]) -> str | None:
        normalized = normalize(question)
        target_terms: list[str] = []
        if "email" in normalized:
            target_terms = ["email"]
        elif "phone" in normalized:
            target_terms = ["phone", "mobile", "tel"]
        elif "status" in normalized:
            target_terms = ["status"]
        elif "created" in normalized or "when was" in normalized:
            target_terms = ["created", "created date", "date"]
        elif "who is" in normalized:
            target_terms = ["name", "customer name"]
        for term in target_terms:
            for column in columns:
                if term in normalize(column):
                    return column
        return None

    def _summary_columns(self, columns: list[str]) -> list[str]:
        wanted = ["customerid", "customer id", "name", "email", "phone", "status", "created"]
        selected: list[str] = []
        for want in wanted:
            for column in columns:
                if column in selected:
                    continue
                if want in normalize(column):
                    selected.append(column)
                    break
        return selected[:6]

    def _unique_values(self, rows: list[dict[str, Any]], column: str) -> list[str]:
        values: list[str] = []
        seen: set[str] = set()
        for row in rows:
            value = row.get(column)
            if value is None or value == "":
                continue
            text = str(value)
            if text not in seen:
                seen.add(text)
                values.append(text)
        return values

    def _clean_question_label(self, question: str) -> str:
        return question.strip().rstrip("?")

    def _display_column_name(self, column: str) -> str:
        return column.split("__", 1)[-1].replace("_", " ")

    def _quote_ident(self, identifier: str) -> str:
        return '"' + identifier.replace('"', '""') + '"'

    def _quote_literal(self, value: str) -> str:
        return "'" + value.replace("'", "''") + "'"

    def _answer_with_analyst_plan(
        self,
        message: str,
        dataset: dict[str, Any],
        history: list[dict[str, Any]],
        data_engineer: Any | None = None,
    ) -> dict[str, Any] | None:
        if not hasattr(self.planner_agent, "run"):
            return None

        prompt_info = self._analysis_planning_prompt_info(message, dataset, history)
        prompt = prompt_info["rendered_prompt"]
        try:
            run_output = self.planner_agent.run(prompt, stream=False)
            prompt_info["token_usage"] = self._extract_run_usage(run_output)
            plan = self._parse_json_content(getattr(run_output, "content", None))
            mode = str(plan.get("mode", "")).strip().lower()
            rationale = str(plan.get("rationale", "Agno analyst selected the evidence path.")).strip()
            confidence = self._bounded_confidence(plan.get("confidence"), default=0.78)

            if mode in {"profile", "reasoning", "overview"}:
                answer = str(plan.get("answer") or "").strip()
                if not answer:
                    answer = self._relationship_answer(dataset.get("profile", {}))
                return self._profile_response(
                    dataset,
                    answer,
                    [
                        rationale,
                        "Agno analyst used the stored profile instead of running SQL.",
                    ],
                    confidence=confidence,
                    mode="profile",
                    prompt_info=prompt_info,
                )

            if mode in {"data_engineering", "data_preparation", "cleaning"} and data_engineer is not None:
                delegated = data_engineer.answer(message, dataset, history)
                delegated_prompt = delegated.get("_prompt_info")
                if delegated_prompt:
                    delegated_prompt.setdefault("upstream", prompt_info)
                else:
                    delegated["_prompt_info"] = {"upstream": prompt_info}
                delegated.setdefault("evidence", [])
                delegated["evidence"] = [
                    rationale,
                    "Agno analyst delegated this request to the DataEngineerAgent.",
                    *delegated["evidence"],
                ]
                return delegated

            if mode in {"clarify", "clarification"}:
                if self._has_target_context(message, history) and self._asks_feature_importance(message, history):
                    return self._profile_response(
                        dataset,
                        self._important_feature_answer(
                            dataset.get("profile", {}),
                            target=self._infer_target_from_history([*history, {"role": "user", "content": message}]),
                        ),
                        [
                            rationale,
                            "Overrode clarification because the target was already present in the question or recent conversation.",
                            "Agno analyst used the stored profile instead of running SQL.",
                        ],
                        confidence=0.76,
                        mode="profile",
                        prompt_info=prompt_info,
                    )
                answer = str(plan.get("answer") or "").strip() or (
                    "I need one more detail before analyzing this well. Which outcome or business decision should I optimize for?"
                )
                return self._profile_response(
                    dataset,
                    answer,
                    [rationale, "No SQL was run because the analyst requested clarification."],
                    confidence=confidence,
                    mode="clarify",
                    prompt_info=prompt_info,
                )

            if mode in {"out_of_scope", "small_talk"}:
                answer = str(plan.get("answer") or "").strip() or (
                    "I can help with this dataset's profile, quality, relationships, and focused calculations."
                )
                return self._profile_response(
                    dataset,
                    answer,
                    [rationale, "No dataset query was run."],
                    confidence=confidence,
                    mode="out_of_scope",
                    prompt_info=prompt_info,
                )

            if mode == "sql":
                sql = str(plan.get("sql", "")).strip()
                if not sql or not self._queries_dataset(sql):
                    return None
                if self._is_raw_preview_sql(sql) and self._question_asks_outcome_distribution(message, dataset):
                    safe_query = self.tools.build_safe_query(dataset["project_id"], dataset["id"], message)
                    safe_sql = safe_query.get("sql")
                    if not safe_sql:
                        return self._profile_response(
                            dataset,
                            "I need one more detail before running that. Which outcome, metric, or grouping should I compare?",
                            [rationale, safe_query.get("evidence_note") or "Safe query builder requested clarification."],
                            confidence=0.68,
                            mode="clarify",
                            prompt_info=prompt_info,
                        )
                    sql = safe_sql
                    plan["evidence_note"] = safe_query["evidence_note"]
                if self._is_raw_preview_sql(sql) and not self._question_asks_for_rows(message):
                    return self._profile_response(
                        dataset,
                        (
                            "I would not start by previewing raw rows for that question. "
                            "It needs either profile-level reasoning or a focused aggregate. Can you specify the outcome or metric you care about?"
                        ),
                        [rationale, "Blocked raw preview SQL because the user did not ask to list records."],
                        confidence=0.72,
                        mode="clarify",
                        prompt_info=prompt_info,
                    )

                result = self.tools.execute_dataset_sql(dataset["project_id"], dataset["id"], sql)
                data = result["data"]
                needs_chart = bool(plan.get("needs_chart", False))
                chart = self.tools.suggest_chart(data) if needs_chart else None
                evidence_note = str(plan.get("evidence_note") or "Ran a focused aggregate query.").strip()
                answer = self._summarize_model_result(message, data, evidence_note, plan.get("answer"))
                return {
                    "answer": answer,
                    "evidence": [
                        rationale,
                        evidence_note,
                        f"Agno analyst chose SQL and trusted DuckDB executed it against dataset '{dataset['name']}'.",
                    ],
                    "sql": sql,
                    "data": data,
                    "chart": chart,
                    "confidence": confidence,
                    "mode": "sql",
                    "_prompt_info": prompt_info,
                }
        except Exception:
            return None
        return None

    def _analysis_planning_prompt_info(
        self, message: str, dataset: dict[str, Any], history: list[dict[str, Any]] | None = None
    ) -> dict[str, Any]:
        profile_context = self._compact_profile_context(dataset.get("profile", {}))
        recent_history = self._compact_history(history or [])
        profile_context_json = json.dumps(profile_context, ensure_ascii=False)
        variables = {
            "dataset_name": str(dataset["name"]),
            "row_count": str(dataset["row_count"]),
            "recent_conversation_json": json.dumps(recent_history, ensure_ascii=False),
            "profile_context_json": profile_context_json,
            "user_question": message,
        }
        template, prompt_metadata = self._load_analysis_planning_template()
        rendered_prompt = self._format_prompt_template(template, variables)
        return {
            "name": prompt_metadata["name"],
            "version": prompt_metadata["version"],
            "source": prompt_metadata["source"],
            "uri": prompt_metadata.get("uri"),
            "template": template,
            "rendered_prompt": rendered_prompt,
            "profile_context_json": profile_context,
        }

    def _load_analysis_planning_template(self) -> tuple[str, dict[str, str]]:
        prompt_name = str(self.prompt_registry_config.get("prompt_name") or "query-analyst-planner")
        prompt_version = str(self.prompt_registry_config.get("prompt_version") or "").strip()
        tracking_enabled = bool(self.prompt_registry_config.get("tracking_enabled"))
        tracking_uri = str(self.prompt_registry_config.get("tracking_uri") or "").strip()

        if tracking_enabled and mlflow is not None:
            try:
                if tracking_uri:
                    mlflow.set_tracking_uri(tracking_uri)
                version = prompt_version or None
                prompt = mlflow.genai.load_prompt(
                    prompt_name,
                    version=int(version) if version and version.isdigit() else version,
                    cache_ttl_seconds=60,
                )
                return str(prompt.template), {
                    "name": str(prompt.name),
                    "version": str(prompt.version),
                    "source": "mlflow",
                    "uri": f"prompts:/{prompt.name}/{prompt.version}",
                }
            except Exception:
                pass
        return self._analysis_planning_template(), {
            "name": prompt_name,
            "version": "code-fallback",
            "source": "code",
            "uri": "",
        }

    def _format_prompt_template(self, template: str, variables: dict[str, str]) -> str:
        rendered = template
        for key, value in variables.items():
            rendered = rendered.replace("{{" + key + "}}", value)
        return rendered

    def _analysis_planning_template(self) -> str:
        return (
            "You are the Agno QuerySkill inside Data-Berge OS.\n"
            "This is the query-and-analysis skill used by the DataAnalystAgent.\n"
            "Think like a real data analyst: understand the question, look at the overall dataset profile, "
            "consider missing context, avoid bias, and choose the least invasive evidence path.\n\n"
            "Choose exactly one mode:\n"
            "- profile: answer from stored profile, schema, quality flags, distributions, correlations, or bivariate tests.\n"
            "- data_engineering: answer from the stored data engineering contract for cleaning, typing, missingness policy, lineage, prep steps, or semantic roles.\n"
            "- sql: run a focused SELECT/WITH query because the user asks for a count, average, top-N, filtered result, grouping, or fresh calculation.\n"
            "- clarify: ask a concise clarification because a target, metric, or business goal is missing.\n"
            "- out_of_scope: the request is not about this dataset.\n\n"
            "Decision rules:\n"
            "- Do NOT default to SQL. Many analytical questions are better answered from the profile.\n"
            "- Use profile mode for questions about important features, drivers, overall view, likely approach, risks, bias, missingness, quality, relationships, and what to investigate next.\n"
            "- Use data_engineering mode for questions about cleaning, preparation, semantic roles, null handling, duplicates, typing, joins, lineage, or how to make the dataset more analysis-ready.\n"
            "- Use SQL only for explicit computations or focused aggregates.\n"
            "- If the question only asks for explanation, reasoning, interpretation, or follow-up on already available information, use profile mode.\n"
            "- If SQL results are needed, prefer aggregated results such as COUNT, AVG, MIN, MAX, MEDIAN, SUM, GROUP BY, or bins. Avoid raw rows unless explicitly requested.\n"
            "- Users often say 'top' when they mean most common; prefer frequency interpretation unless they clearly ask for numerical maximum.\n"
            "- Before writing SQL, map the user's business words to columns using the profile context: column name, semantic_type, role_hint, description, sample_values, top_values, and word_frequencies.\n"
            "- If the user asks about reasons, purposes, explanations, comments, narratives, text, or descriptions, look for text/narrative columns in the profile context and use them as the grouping/detail field.\n"
            "- If the user asks for the highest/most common reason for each outcome/status/class, group by both the outcome/status column and the reason/narrative column, then rank within each outcome/status.\n"
            "- Do not collapse a multi-column question into a one-column aggregate. If the user mentions both an outcome and a reason/detail, the SQL must include both concepts or you should ask for clarification.\n"
            "- Never generate raw preview SQL unless the user asks to list/show/example actual records.\n"
            "- Only set needs_chart true when visualization adds value by revealing a pattern, comparison, trend, or distribution. Return false for single metrics or small results that are easy to read as text.\n"
            "- If SQL is used, query only the table named dataset and return only SELECT or WITH SQL.\n"
            "- For relational/multi-table datasets, SQL still queries the single working table named dataset; use the prefixed columns from profile_context_json such as Table__Column.\n"
            "- For relational/multi-table questions, use the relational_schema block for table names, relationships, and join meaning, but do not invent separate SQL tables. The query table is still dataset.\n"
            "- Relational working-table rows can duplicate parent entities after one-to-many joins. For entity counts such as orders, customers, products, or completed orders, count distinct entity key columns such as Order__OrderID instead of count(*) unless the user explicitly asks for working rows.\n"
            "- For a batch with several concrete questions, prefer one WITH query that returns rows with question/answer/value columns, using UNION ALL where useful. Do not ask for clarification just because there are multiple questions.\n"
            "- If the message contains [ANALYST_PARALLEL_SLICE], answer the Analyst questions only and prefer sql for concrete lookup, count, list, total, spend, product, order, customer, or status questions. Do not answer with a generic profile overview.\n"
            "- Do not use INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, COPY, PRAGMA, INSTALL, LOAD, ATTACH, DETACH, or CALL.\n"
            "- Quote identifiers with double quotes when needed.\n"
            "- Be honest: profile relationships are not model feature importance unless a model was trained.\n"
            "- Use recent conversation to resolve follow-ups. If the user gives a target like 'loan approval' after you asked for an outcome, treat it as the target for the previous feature-importance question.\n"
            "- If the user asks 'which one', 'so which', or similar, answer using the target and reasoning already established in the recent conversation. Do not ask the same clarification again.\n"
            "- When forced to choose one feature from profile evidence, state the pick and explain the uncertainty briefly.\n"
            "- The user-facing answer should sound natural. Do not mention internal schema context, JSON, tools, or planning. Mention SQL only if the user asks about the query.\n"
            "- Return JSON only, no markdown.\n\n"
            "Dataset name: {{dataset_name}}\n"
            "Rows: {{row_count}}\n"
            "Recent conversation JSON: {{recent_conversation_json}}\n"
            "Profile context JSON: {{profile_context_json}}\n"
            "User question: {{user_question}}\n\n"
            "JSON schema:\n"
            "{"
            '"mode":"profile|data_engineering|sql|clarify|out_of_scope",'
            '"rationale":"short reason for choosing this mode",'
            '"answer":"final answer for profile/clarify/out_of_scope, or short interpretation to combine with SQL result",'
            '"sql":"select ... from dataset, or empty string",'
            '"needs_chart":false,'
            '"evidence_note":"what evidence the answer uses",'
            '"confidence":0.0'
            "}"
        )

    def _compact_profile_context(self, profile: dict[str, Any]) -> dict[str, Any]:
        # --- Unified format: profile has "tables" dict ---
        tables = profile.get("tables", {})
        if tables:
            return self._compact_tables_context(profile)
        # --- Legacy flat format (backward compat for old single-table profiles) ---
        return self._compact_flat_context(profile)

    def _compact_column(self, column: dict[str, Any]) -> dict[str, Any]:
        """Extract compact fields from a single column dict."""
        payload: dict[str, Any] = {
            "name": column.get("name"),
            "semantic_type": column.get("semantic_type"),
            "role_hint": self._column_role_hint(column),
            "description": self._column_description(column),
            "description_source": "human" if column.get("description") else "inferred",
            "dtype": column.get("dtype"),
            "missing_pct": column.get("missing_pct"),
            "unique_count": column.get("unique_count"),
            "sample_values": (column.get("sample_values") or [])[:3],
        }
        if column.get("stats"):
            stats = column["stats"]
            payload["stats"] = {
                "mean": stats.get("mean"), "median": stats.get("median"),
                "min": stats.get("min"), "max": stats.get("max"), "std": stats.get("std"),
            }
        if column.get("top_values"):
            payload["top_values"] = column["top_values"][:3]
        if column.get("word_frequencies"):
            payload["word_frequencies"] = column["word_frequencies"][:12]
        return payload

    def _compact_flat_context(self, profile: dict[str, Any]) -> dict[str, Any]:
        """Legacy: compact context from flat single-table profile."""
        columns = [self._compact_column(col) for col in profile.get("columns", [])[:30]]
        bivariate = profile.get("bivariate_analysis", {}) or {}
        context = {
            "row_count": profile.get("row_count"),
            "column_count": profile.get("column_count"),
            "metadata": profile.get("metadata", {}),
            "quality_flags": profile.get("quality_flags", []),
            "columns": columns,
            "top_correlations": self._rank_numeric_relationships(
                bivariate.get("numeric_numeric", []) or profile.get("correlations", []) or []
            )[:6],
            "top_group_differences": self._rank_mixed_relationships(bivariate.get("numeric_categorical", []))[:6],
            "top_categorical_associations": self._rank_categorical_relationships(
                bivariate.get("categorical_categorical", [])
            )[:6],
        }
        relational_schema = profile.get("relational_schema")
        if isinstance(relational_schema, dict) and relational_schema:
            context["format"] = "relational_working_table"
            context["relational_schema"] = relational_schema
            context["relational_entity_keys"] = self._relational_entity_keys(relational_schema, [col.get("name") for col in columns])
            context["sql_table_policy"] = (
                "Query only the DuckDB table named dataset. Multi-table columns are present in the working table "
                "using Table__Column names shown in columns[]. Count distinct entity keys for table-level counts because "
                "one-to-many joins can repeat parent rows."
            )
        return context

    def _compact_tables_context(self, profile: dict[str, Any]) -> dict[str, Any]:
        """Build compact context from the unified tables format."""
        tables = profile.get("tables", {})
        relationships = profile.get("relationships", [])
        table_summaries = []
        all_columns: list[dict[str, Any]] = []
        numeric_numeric = []
        numeric_categorical = []
        categorical_categorical = []

        for tname, tprofile in tables.items():
            engineering = tprofile.get("data_engineering", {})
            bivariate = tprofile.get("bivariate_analysis", {}) or {}
            table_summaries.append({
                "name": tname,
                "row_count": tprofile.get("row_count", 0),
                "column_count": tprofile.get("column_count", 0),
                "quality_flags": (tprofile.get("quality_flags") or [])[:3],
                "readiness_score": engineering.get("readiness_score"),
                "top_correlations": self._rank_numeric_relationships(
                    bivariate.get("numeric_numeric", []) or tprofile.get("correlations", []) or []
                )[:3],
            })
            # Columns from each table (prefixed for multi-table)
            prefix = f"{tname}__" if len(tables) > 1 else ""
            for column in (tprofile.get("columns") or [])[:15]:
                compact = self._compact_column(column)
                compact["name"] = f"{prefix}{column.get('name', '')}"
                compact["table"] = tname
                all_columns.append(compact)
            # Collect bivariate from all tables
            for item in (bivariate.get("numeric_numeric") or tprofile.get("correlations") or []):
                item_copy = dict(item)
                item_copy["table"] = tname
                numeric_numeric.append(item_copy)
            for item in (bivariate.get("numeric_categorical") or []):
                item_copy = dict(item)
                item_copy["table"] = tname
                numeric_categorical.append(item_copy)
            for item in (bivariate.get("categorical_categorical") or []):
                item_copy = dict(item)
                item_copy["table"] = tname
                categorical_categorical.append(item_copy)

        active_rel_count = sum(1 for r in relationships if r.get("active", True))
        return {
            "format": "relational",
            "table_summaries": table_summaries,
            "relationship_count": active_rel_count,
            "relationships": [
                {"from": f"{r.get('from_table')}.{r.get('from_column')}", "to": f"{r.get('to_table')}.{r.get('to_column')}", "cardinality": r.get("cardinality", "unknown")}
                for r in relationships if r.get("active", True)
            ][:6],
            "columns": all_columns[:40],
            "top_correlations": self._rank_numeric_relationships(numeric_numeric)[:6],
            "top_group_differences": self._rank_mixed_relationships(numeric_categorical)[:6],
            "top_categorical_associations": self._rank_categorical_relationships(categorical_categorical)[:6],
        }

    def _column_role_hint(self, column: dict[str, Any]) -> str:
        name = str(column.get("name", "")).lower()
        description = str(column.get("description") or "").lower()
        semantic_type = column.get("semantic_type")
        top_labels = {
            re.sub(r"[^a-z0-9]+", " ", str(item.get("label", "")).lower()).strip()
            for item in (column.get("top_values") or [])
        }
        narrative_terms = {"narrative", "reason", "purpose", "explanation", "comment", "description", "situation", "request"}
        if semantic_type == "text" or any(term in f"{name} {description}" for term in narrative_terms):
            return "narrative_or_reason"
        if semantic_type == "datetime":
            return "time"
        if semantic_type == "numeric":
            return "measure"
        if "status" in name or "approval" in name or {"approved", "rejected"}.issubset(top_labels):
            return "outcome_or_status"
        return "category"

    def _column_description(self, column: dict[str, Any]) -> str:
        name = column.get("name")
        human_description = str(column.get("description") or "").strip()
        if human_description:
            return human_description
        semantic_type = column.get("semantic_type")
        role = self._column_role_hint(column)
        if role == "narrative_or_reason":
            return (
                f"{name} is free-text narrative evidence. It may represent a reason, purpose, explanation, "
                "comment, request, or description depending on the user's wording."
            )
        if role == "outcome_or_status":
            return f"{name} is a categorical outcome/status field. Use it for class comparisons and approval/rejection style questions."
        if role == "measure":
            return f"{name} is a numeric measure. Use it for averages, ranges, distributions, correlations, and group comparisons."
        if role == "time":
            return f"{name} is a time field. Use it for trends, periods, and recency questions."
        return f"{name} is a categorical field. Use it for breakdowns, segments, and frequency comparisons."

    def _compact_history(self, history: list[dict[str, Any]]) -> list[dict[str, str]]:
        compact: list[dict[str, str]] = []
        for item in history[-8:]:
            role = str(item.get("role", ""))
            content = str(item.get("content", "")).strip()
            if not content:
                continue
            compact.append({"role": role, "content": content[:700]})
        return compact

    def _contextualize_follow_up(self, message: str, history: list[dict[str, Any]]) -> str:
        normalized = re.sub(r"[^a-z0-9]+", " ", message.lower()).strip()
        target = self._infer_target_from_history(history)
        asks_which = normalized in {
            "which one",
            "so which one",
            "so which",
            "which feature",
            "which is most important",
            "what about it",
        } or ("which" in normalized.split() and "important" in self._history_text(history))
        if target and asks_which:
            return f"For {target}, which feature seems most important?"
        if target and normalized in {"loan approval", "approval", "approvals", "approved"}:
            return f"For {target}, identify the most important feature from the dataset profile."
        return message

    def _asks_feature_importance(self, message: str, history: list[dict[str, Any]]) -> bool:
        normalized = re.sub(r"[^a-z0-9]+", " ", message.lower()).strip()
        words = set(normalized.split())
        if words & {"important", "feature", "driver", "predictor", "influence"}:
            return True
        if "which" in words and "important" in self._history_text(history):
            return True
        return False

    def _has_target_context(self, message: str, history: list[dict[str, Any]]) -> bool:
        combined = f"{message.lower()} {self._history_text(history)}"
        return any(
            term in combined
            for term in ["loan approval", "approval", "approved", "loan amount", "default risk", "target", "outcome"]
        )

    def _infer_target_from_history(self, history: list[dict[str, Any]]) -> str | None:
        combined = self._history_text(history)
        if any(term in combined for term in ["loan approval", "approval status", "approval", "approved"]):
            return "loan approval"
        if "loan amount" in combined:
            return "loan amount"
        if "default risk" in combined or "default" in combined:
            return "default risk"
        return None

    def _history_text(self, history: list[dict[str, Any]]) -> str:
        return " ".join(str(item.get("content", "")).lower() for item in history[-8:])

    def _bounded_confidence(self, value: Any, default: float = 0.78) -> float:
        try:
            confidence = float(value)
        except (TypeError, ValueError):
            return default
        return max(0.0, min(1.0, confidence))

    def _is_raw_preview_sql(self, sql: str) -> bool:
        cleaned = re.sub(r"\s+", " ", sql.strip().lower())
        aggregate_terms = r"\b(count|avg|sum|min|max|corr|median|stddev|variance|group\s+by|order\s+by|distinct)\b"
        return bool(re.search(r"\bselect\b.+\bfrom\s+dataset\b", cleaned)) and not bool(
            re.search(aggregate_terms, cleaned)
        )

    def _question_asks_for_rows(self, message: str) -> bool:
        normalized = re.sub(r"[^a-z0-9]+", " ", message.lower()).strip()
        row_terms = {"show", "list", "preview", "rows", "records", "examples", "sample", "raw"}
        return bool(set(normalized.split()) & row_terms)

    def _question_asks_outcome_distribution(self, message: str, dataset: dict[str, Any]) -> bool:
        normalized = re.sub(r"[^a-z0-9]+", " ", message.lower()).strip()
        words = set(normalized.split())
        profile = dataset.get("profile", {})
        outcome_names = {
            normalize(column.get("name", ""))
            for column in profile.get("columns", [])
            if column.get("semantic_type") == "categorical"
            and (
                "approval" in normalize(column.get("name", ""))
                or {"approved", "rejected"}.issubset(
                    {normalize(str(item.get("label", ""))) for item in (column.get("top_values", []) or [])}
                )
            )
        }
        mentions_outcome = bool(words & {"approve", "approved", "approval", "rejected", "reject", "rejection"})
        asks_comparison = bool(words & {"highest", "higher", "most", "more", "count", "counts"})
        return mentions_outcome and asks_comparison and bool(outcome_names)

    def _answer_from_profile(self, message: str, dataset: dict[str, Any]) -> dict[str, Any] | None:
        normalized = re.sub(r"[^a-z0-9]+", " ", message.lower()).strip()
        profile = get_flat_profile(dataset.get("profile", {}))

        important_terms = {
            "important",
            "feature",
            "features",
            "driver",
            "drivers",
            "predictor",
            "predictors",
            "influence",
            "influences",
            "matter",
            "matters",
        }
        relationship_terms = {"relationship", "relationships", "correlation", "correlations", "strongest", "associated"}
        quality_terms = {"quality", "missing", "duplicate", "duplicates", "clean", "issues"}
        overview_terms = {"overview", "summary", "profile", "describe", "structure"}

        tokens = set(normalized.split())
        if tokens & important_terms and ("feature" in tokens or "features" in tokens or "important" in tokens):
            return self._profile_response(
                dataset,
                self._important_feature_answer(profile, target=self._infer_target_from_history([{"role": "user", "content": message}])),
                [
                    "Used stored profile evidence: correlations, ANOVA group-difference tests, and categorical association tests.",
                    "No SQL was run because this is a profile-level interpretation question.",
                ],
                confidence=0.78,
            )
        if tokens & relationship_terms:
            return self._profile_response(
                dataset,
                self._relationship_answer(profile),
                ["Used stored bivariate analysis from the dataset profile.", "No SQL was run for this profile summary."],
                confidence=0.8,
            )
        if tokens & quality_terms:
            return self._profile_response(
                dataset,
                self._quality_answer(profile),
                ["Used stored quality flags and missing-value counts from the dataset profile."],
                confidence=0.86,
            )
        if tokens & overview_terms and not {"count", "counts", "average", "avg", "sum", "top"} & tokens:
            return self._profile_response(
                dataset,
                self._overview_answer(profile),
                ["Used stored dataset profile metadata and column typing."],
                confidence=0.82,
            )
        return None

    def _looks_like_data_engineering_question(self, message: str, dataset: dict[str, Any]) -> bool:
        normalized = re.sub(r"[^a-z0-9]+", " ", message.lower()).strip()
        tokens = set(normalized.split())
        prep_terms = {
            "clean",
            "cleaning",
            "prepare",
            "preparation",
            "preprocess",
            "profiling",
            "quality",
            "missing",
            "null",
            "nulls",
            "duplicate",
            "duplicates",
            "schema",
            "meaning",
            "meanings",
            "description",
            "descriptions",
            "column",
            "columns",
            "type",
            "types",
            "typing",
            "cast",
            "datetime",
            "date",
            "join",
            "joins",
            "identifier",
            "id",
            "lineage",
            "ready",
            "readiness",
            "engineer",
            "engineering",
        }
        return bool(tokens & prep_terms)

    def _profile_response(
        self,
        dataset: dict[str, Any],
        answer: str,
        evidence: list[str],
        confidence: float = 0.8,
        mode: str = "profile",
        prompt_info: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        response = {
            "answer": answer,
            "evidence": [*evidence, f"Profile source: dataset '{dataset['name']}' with {dataset['row_count']} rows."],
            "sql": None,
            "data": [],
            "chart": None,
            "confidence": confidence,
            "mode": mode,
        }
        if prompt_info:
            response["_prompt_info"] = prompt_info
        return response

    def _important_feature_answer(self, profile: dict[str, Any], target: str | None = None) -> str:
        flat = get_flat_profile(profile)
        bivariate = flat.get("bivariate_analysis", {}) or {}
        mixed = self._rank_mixed_relationships(bivariate.get("numeric_categorical", []))
        categorical = self._rank_categorical_relationships(bivariate.get("categorical_categorical", []))
        numeric = self._rank_numeric_relationships(
            bivariate.get("numeric_numeric", []) or flat.get("correlations", []) or []
        )

        findings: list[str] = []
        target_like = [item for item in mixed if self._looks_like_target(item.get("categorical", ""))]
        if target_like:
            item = target_like[0]
            findings.append(
                f"{item['numeric']} looks important for {item['categorical']} because group means differ strongly "
                f"(p-value {self._format_number(item.get('p_value'))}, F {self._format_number(item.get('anova_F'))})."
            )
        elif mixed:
            item = mixed[0]
            findings.append(
                f"{item['numeric']} looks important across {item['categorical']} groups "
                f"(p-value {self._format_number(item.get('p_value'))}, F {self._format_number(item.get('anova_F'))})."
            )

        if categorical:
            item = categorical[0]
            findings.append(
                f"{item['left']} and {item['right']} have the strongest categorical association "
                f"(p-value {self._format_number(item.get('p_value'))})."
            )

        if numeric:
            item = numeric[0]
            findings.append(
                f"{item['left']} and {item['right']} show the strongest numeric relationship "
                f"(correlation {self._format_number(item.get('correlation'))})."
            )

        if not findings:
            columns = profile.get("columns", [])[:5]
            names = ", ".join(str(column.get("name")) for column in columns if column.get("name"))
            if target:
                return (
                    f"I cannot identify a clear most-important feature for {target} from the current profile alone. "
                    f"The first useful fields to inspect are: {names}. To rank true importance, we need target-specific tests or a predictive model."
                )
            return (
                "I cannot identify a clear most-important feature from the current profile alone. "
                f"The first useful fields to inspect are: {names}. To rank true importance, we need to define a target column and train or score a model."
            )

        suffix = (
            f" Because your target is {target}, treat this as an evidence-based shortlist rather than final model feature importance. "
            "A target-specific test or simple predictive model would be the next step to rank it confidently."
            if target
            else " This is statistical evidence from profiling, not model feature importance. For true feature importance, choose a target column first, such as Approval, then we can train or score a model."
        )
        return (
            "From the stored profile, I would treat these as the most important signals right now: "
            + " ".join(findings)
            + suffix
        )

    def _relationship_answer(self, profile: dict[str, Any]) -> str:
        flat = get_flat_profile(profile)
        bivariate = flat.get("bivariate_analysis", {}) or {}
        numeric = self._rank_numeric_relationships(
            bivariate.get("numeric_numeric", []) or flat.get("correlations", []) or []
        )[:3]
        mixed = self._rank_mixed_relationships(bivariate.get("numeric_categorical", []))[:3]
        categorical = self._rank_categorical_relationships(bivariate.get("categorical_categorical", []))[:2]
        parts: list[str] = []
        if numeric:
            parts.append(
                "Top numeric relationships: "
                + "; ".join(
                    f"{item['left']} vs {item['right']} correlation {self._format_number(item.get('correlation'))}"
                    for item in numeric
                )
                + "."
            )
        if mixed:
            parts.append(
                "Strong group differences: "
                + "; ".join(
                    f"{item['numeric']} by {item['categorical']} p-value {self._format_number(item.get('p_value'))}"
                    for item in mixed
                )
                + "."
            )
        if categorical:
            parts.append(
                "Categorical associations: "
                + "; ".join(
                    f"{item['left']} vs {item['right']} p-value {self._format_number(item.get('p_value'))}"
                    for item in categorical
                )
                + "."
            )
        return " ".join(parts) if parts else "The stored profile does not show enough paired fields to summarize relationships yet."

    def _quality_answer(self, profile: dict[str, Any]) -> str:
        flat = get_flat_profile(profile)
        flags = flat.get("quality_flags", []) or []
        metadata = flat.get("metadata", {}) or {}
        missing = metadata.get("missing_cells", 0)
        duplicates = metadata.get("duplicate_rows", 0)
        return (
            f"Data quality summary: {missing} missing cells and {duplicates} duplicate rows. "
            + " ".join(str(flag) for flag in flags)
        )

    def _overview_answer(self, profile: dict[str, Any]) -> str:
        flat = get_flat_profile(profile)
        metadata = flat.get("metadata", {}) or {}
        return (
            f"The profile has {flat.get('row_count', 0)} rows and {flat.get('column_count', 0)} columns. "
            f"It includes {len(metadata.get('numeric_columns', []) or [])} numeric fields, "
            f"{len(metadata.get('categorical_columns', []) or [])} categorical fields, and "
            f"{len(metadata.get('text_columns', []) or [])} text fields. "
            f"Quality: {' '.join(str(flag) for flag in flat.get('quality_flags', []) or [])}"
        )

    def _rank_numeric_relationships(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        valid = [item for item in items if isinstance(item.get("correlation"), (int, float))]
        return sorted(valid, key=lambda item: abs(float(item["correlation"])), reverse=True)

    def _rank_mixed_relationships(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        valid = [item for item in items if isinstance(item.get("p_value"), (int, float))]
        return sorted(
            valid,
            key=lambda item: (
                float(item.get("p_value", 1)),
                -float(item.get("anova_F") or 0),
            ),
        )

    def _rank_categorical_relationships(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        valid = [item for item in items if isinstance(item.get("p_value"), (int, float))]
        return sorted(valid, key=lambda item: float(item.get("p_value", 1)))

    def _looks_like_target(self, name: str) -> bool:
        normalized = re.sub(r"[^a-z0-9]+", " ", name.lower()).strip()
        return any(term in normalized.split() for term in {"approval", "approved", "target", "outcome", "label", "status"})

    def _format_number(self, value: Any) -> str:
        if value is None:
            return "n/a"
        if isinstance(value, (int, float)):
            if abs(float(value)) < 0.0001 and float(value) != 0:
                return f"{float(value):.2e}"
            return f"{float(value):.4g}"
        return str(value)

    def _answer_with_model(self, message: str, dataset: dict[str, Any]) -> dict[str, Any] | None:
        if not hasattr(self.planner_agent, "run"):
            return None

        prompt = self._sql_planning_prompt(message, dataset)
        try:
            run_output = self.planner_agent.run(prompt, stream=False)
            token_usage = self._extract_run_usage(run_output)
            plan = self._parse_json_content(getattr(run_output, "content", None))
            sql = str(plan.get("sql", "")).strip()
            evidence_note = str(plan.get("evidence_note", "Generated a model-assisted SQL query.")).strip()
            if not sql or not self._queries_dataset(sql):
                return None

            result = self.tools.execute_dataset_sql(dataset["project_id"], dataset["id"], sql)
            data = result["data"]
            chart = self.tools.suggest_chart(data)
            answer = self._summarize_model_result(message, data, evidence_note, plan.get("answer"))
            return {
                "answer": answer,
                "evidence": [
                    evidence_note,
                    f"Used Agno model planning with dataset '{dataset['name']}' and trusted DuckDB execution.",
                ],
                "sql": sql,
                "data": data,
                "chart": chart,
                "confidence": 0.86 if data else 0.58,
                "mode": "sql",
                "_token_usage": token_usage,
            }
        except Exception:
            return None

    def _sql_planning_prompt(self, message: str, dataset: dict[str, Any]) -> str:
        profile_context = self._compact_profile_context(dataset["profile"])
        return (
            "You are the QuerySkill for Data-Berge OS.\n"
            "This is the query-and-analysis skill used by the DataAnalystAgent.\n"
            "Create one safe DuckDB SQL query for the user's question by reasoning from the semantic profile context.\n"
            "Rules:\n"
            "- If the message is only a greeting, thanks, small talk, or not an analytics question, return an empty sql string.\n"
            "- Query only the table named dataset.\n"
            "- For relational/multi-table datasets, SQL still queries the single working table named dataset; use the prefixed columns from profile_context_json such as Table__Column.\n"
            "- Use the relational_schema block to understand tables and relationships, but do not invent SQL tables named after source sheets.\n"
            "- Relational working-table rows can duplicate parent entities after one-to-many joins. For entity counts such as orders, customers, products, or completed orders, count distinct entity key columns such as Order__OrderID instead of count(*) unless the user explicitly asks for working rows.\n"
            "- For a batch with several concrete questions, prefer one WITH query that returns rows with question/answer/value columns, using UNION ALL where useful.\n"
            "- If the message contains [ANALYST_PARALLEL_SLICE], answer the Analyst questions only and do not generate profile overview SQL.\n"
            "- Return only SELECT or WITH SQL.\n"
            "- Do not use INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, COPY, PRAGMA, INSTALL, LOAD, ATTACH, DETACH, or CALL.\n"
            "- Pearson corr() is only valid between two numeric columns.\n"
            "- For relationship/correlation questions between a categorical column and a numeric column, group by the categorical column and calculate avg(), count(), min(), and max() for the numeric column.\n"
            "- Map business words to columns using name, semantic_type, role_hint, description, sample_values, top_values, and word_frequencies.\n"
            "- If the user asks about reasons, purposes, explanations, comments, narratives, text, or descriptions, choose the best narrative/text column from the profile context.\n"
            "- If the user asks for highest/most common reason by outcome/status/class, rank reason counts inside each outcome/status using a WITH query and row_number().\n"
            "- Do not reduce multi-concept questions to one-column counts; include each requested concept in the SQL.\n"
            "- Prefer concise aggregate queries over raw previews.\n"
            "- Use exact column names and quote identifiers with double quotes when needed.\n"
            "- Return JSON only, no markdown.\n\n"
            f"Dataset name: {dataset['name']}\n"
            f"Rows: {dataset['row_count']}\n"
            f"Profile context JSON: {json.dumps(profile_context, ensure_ascii=False)}\n"
            f"Question: {message}\n\n"
            "JSON schema:\n"
            '{"sql":"select ... from dataset","evidence_note":"What this query calculates","answer":"Optional short plain-English expectation"}'
        )

    def _non_analytics_response(self, message: str) -> dict[str, Any] | None:
        normalized = re.sub(r"[^a-z0-9]+", " ", message.lower()).strip()
        greetings = {
            "hi",
            "hii",
            "hello",
            "hey",
            "yo",
            "thanks",
            "thank you",
            "ok",
            "okay",
            "yeah",
            "yes",
            "yep",
            "no",
            "nah",
            "what do you mean",
            "what can you do",
        }
        if normalized in greetings:
            return {
                "answer": "I can help with this selected dataset. Ask things like row counts, approvals by category, averages, missing values, distributions, or relationships between fields.",
                "evidence": ["No dataset query was run because the message was not an analytics question."],
                "sql": None,
                "data": [],
                "chart": None,
                "confidence": 0.95,
            }
        return None

    def _queries_dataset(self, sql: str) -> bool:
        cleaned = sql.strip().lower()
        return bool(re.search(r"\bfrom\s+dataset\b|\bjoin\s+dataset\b", cleaned))

    def _parse_json_content(self, content: Any) -> dict[str, Any]:
        if isinstance(content, dict):
            return content
        if not isinstance(content, str):
            raise ValueError("Model did not return JSON content.")
        text = content.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\\s*", "", text, flags=re.IGNORECASE)
            text = re.sub(r"\\s*```$", "", text)
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise ValueError("Model response did not contain a JSON object.")
        return json.loads(text[start : end + 1])

    def _extract_run_usage(self, run_output: Any) -> dict[str, Any]:
        metrics = getattr(run_output, "metrics", None) or getattr(run_output, "session_metrics", None)
        if not metrics:
            return {}

        def metric_value(name: str) -> int | float | None:
            value = getattr(metrics, name, None)
            if value is None and isinstance(metrics, dict):
                value = metrics.get(name)
            if isinstance(value, list):
                values = [item for item in value if isinstance(item, (int, float))]
                return sum(values) if values else None
            if isinstance(value, (int, float)):
                return value
            return None

        input_tokens = metric_value("input_tokens")
        output_tokens = metric_value("output_tokens")
        total_tokens = metric_value("total_tokens")
        if total_tokens is None and input_tokens is not None and output_tokens is not None:
            total_tokens = input_tokens + output_tokens

        usage: dict[str, int] = {}
        if input_tokens is not None:
            usage["input_tokens"] = int(input_tokens)
        if output_tokens is not None:
            usage["output_tokens"] = int(output_tokens)
        if total_tokens is not None:
            usage["total_tokens"] = int(total_tokens)
        if cache_read_tokens := metric_value("cache_read_tokens"):
            usage["cache_read_input_tokens"] = int(cache_read_tokens)
        if cache_write_tokens := metric_value("cache_write_tokens"):
            usage["cache_creation_input_tokens"] = int(cache_write_tokens)

        cost_value = metric_value("cost")
        cost = {"total_cost": float(cost_value)} if cost_value is not None else {}
        payload: dict[str, Any] = {}
        if usage:
            payload["usage"] = usage
        if cost:
            payload["cost"] = cost
        if model := getattr(run_output, "model", None):
            payload["model"] = model
        if provider := getattr(run_output, "model_provider", None):
            payload["provider"] = provider
        return payload

    def _summarize_model_result(
        self, message: str, data: list[dict[str, Any]], evidence_note: str, model_answer: Any = None
    ) -> str:
        row_summary = self._summarize_rows(message, data)
        model_text = str(model_answer or "").strip()
        if row_summary:
            return row_summary + "."
        if model_text:
            return model_text
        return self.tools._summarize_query_result(message, data, evidence_note)

    def _summarize_rows(self, message: str, data: list[dict[str, Any]]) -> str | None:
        if not data:
            return None
        normalized_message = normalize(message)
        if len(data) == 1:
            row = data[0]
            if len(row) == 1:
                key, value = next(iter(row.items()))
                if normalized_message.startswith("who ") or normalized_message.startswith("which customer"):
                    return str(value)
                return f"{self._display_field_name(key)}: {value}"
            return ", ".join(f"{self._display_field_name(key)}: {value}" for key, value in row.items())

        keys = list(data[0].keys())
        if len(keys) == 1 and (
            normalized_message.startswith("who ")
            or normalized_message.startswith("what ")
            or normalized_message.startswith("which ")
            or normalized_message.startswith("list ")
            or normalized_message.startswith("show ")
        ):
            key = keys[0]
            values = [str(row.get(key)) for row in data[:8]]
            extra = len(data) - len(values)
            if extra > 0:
                values.append(f"{extra} more")
            return ", ".join(values)
        if len(keys) == 2:
            label_key, value_key = keys
            parts = [
                f"{self._display_value(row.get(label_key))}: {self._display_value(row.get(value_key))}"
                for row in data[:8]
            ]
            extra = len(data) - len(parts)
            if extra > 0:
                parts.append(f"{extra} more")
            return "; ".join(parts)

        row_parts = []
        for row in data[:5]:
            row_parts.append(", ".join(f"{self._display_field_name(key)}: {value}" for key, value in row.items()))
        if len(data) > len(row_parts):
            row_parts.append(f"{len(data) - len(row_parts)} more rows")
        return "; ".join(row_parts)

    def _display_field_name(self, name: Any) -> str:
        text = str(name)
        if "__" in text:
            text = text.split("__", 1)[1]
        text = text.replace("_", " ")
        text = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", text)
        return text[:1].upper() + text[1:] if text else text

    def _display_value(self, value: Any) -> str:
        return "" if value is None else str(value)

    def _relational_entity_keys(self, relational_schema: dict[str, Any], columns: list[Any]) -> dict[str, str]:
        available = {str(column) for column in columns if column}
        tables = [str(name) for name in relational_schema.get("table_names", []) or []]
        keys: dict[str, str] = {}

        for relationship in relational_schema.get("relationships", []) or []:
            to_table = str(relationship.get("to_table") or "")
            to_column = str(relationship.get("to_column") or "")
            candidate = f"{to_table}__{to_column}"
            if to_table and candidate in available:
                keys.setdefault(to_table, candidate)

        for table in tables:
            candidates = [
                f"{table}__{table}ID",
                f"{table}__{table}Id",
                f"{table}__{table}_ID",
                f"{table}__ID",
                f"{table}__Id",
            ]
            normalized_table = normalize(table)
            for column in available:
                if column.startswith(f"{table}__"):
                    short_name = column.split("__", 1)[1]
                    if normalize(short_name) in {f"{normalized_table} id", f"{normalized_table}id", "id"}:
                        candidates.append(column)
            for candidate in candidates:
                if candidate in available:
                    keys.setdefault(table, candidate)
                    break
        return keys
