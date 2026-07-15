from __future__ import annotations

import json
import re
from typing import Any, Callable

from data_berge_core.app_context import APP_CONTEXT
from data_berge_core.contracts import DatasetContext, ProfileProvider
from data_berge_core.runtime import AgentFactory, AgentSpec, ToolkitFactory
from data_berge_core.contracts import get_flat_profile


DATA_ENGINEERING_CONTRACT_VERSION = 2


class EngineeringSkill:
    spec = AgentSpec(
        name="EngineeringSkill",
        role="Prepare uploaded datasets for trustworthy analytics work.",
        instructions=(
            "Infer semantic roles, flag structural issues, define a working data contract, and recommend "
            "preparation steps without mutating the source data silently."
        ),
    )

    def __init__(
        self,
        toolkit_factory: ToolkitFactory,
        agent_factory: AgentFactory,
        profile_provider: ProfileProvider,
        load_dataframe_fn: Callable[[str], Any],
        prepare_contract_fn: Callable[[Any, dict[str, Any]], dict[str, Any]],
    ) -> None:
        self.profile_provider = profile_provider
        self.load_dataframe_fn = load_dataframe_fn
        self.prepare_contract_fn = prepare_contract_fn
        self.tools = toolkit_factory(
            include_tools=["get_dataset_profile", "profile_file"],
            profile_provider=profile_provider,
        )
        # The prompt already carries the current dataset contract/profile. Do not expose
        # profile lookup tools to the LLM or it may invent project/dataset ids.
        self.agent = agent_factory(self.spec, tools=None)

    def prepare(self, df: Any, profile: dict[str, Any]) -> dict[str, Any]:
        return self.prepare_contract_fn(df, profile)

    def assess_for_report(self, dataset: dict[str, Any]) -> dict[str, Any]:
        """Produce a Readiness Brief for report generation."""
        contract = self._ensure_contract(dataset)
        profile = dataset.get("profile", {}) or {}
        columns = get_flat_profile(profile).get("columns", [])
        metadata = get_flat_profile(profile).get("metadata", {}) or {}
        readiness_score = contract.get("readiness_score", 0)
        warnings = contract.get("warnings", [])
        preparation_notes = contract.get("preparation_notes", [])
        semantic_roles = contract.get("semantic_roles", {})

        trustable_measures = semantic_roles.get("measure", [])
        caution_columns: list[str] = []
        for column in columns:
            name = str(column.get("name"))
            missing_pct = float(column.get("missing_pct") or 0)
            quality_notes = column.get("quality_notes") or []
            if missing_pct > 15 or quality_notes:
                caution_columns.append(name)

        outcome_columns = semantic_roles.get("outcome", [])
        segment_dimensions = semantic_roles.get("category", [])
        time_columns = semantic_roles.get("time", [])

        if readiness_score >= 8:
            readiness_label = "Good"
        elif readiness_score >= 5:
            readiness_label = "Fair"
        else:
            readiness_label = "Poor"

        recommended_focus: list[str] = []
        if trustable_measures and outcome_columns:
            recommended_focus.append(
                f"Relationship between {', '.join(trustable_measures[:3])} and {outcome_columns[0]}"
            )
        if segment_dimensions:
            recommended_focus.append(
                f"Segment comparisons by {', '.join(segment_dimensions[:2])}"
            )
        if trustable_measures:
            recommended_focus.append(
                f"Distribution analysis of {', '.join(trustable_measures[:3])}"
            )
        if time_columns:
            recommended_focus.append(
                f"Time-based trends across {', '.join(time_columns[:2])}"
            )

        data_limitations: list[str] = []
        row_count = profile.get("row_count", 0)
        if row_count < 30:
            data_limitations.append(
                f"Small dataset ({row_count} rows) limits statistical confidence."
            )
        if not time_columns:
            data_limitations.append("No temporal dimension available for trend analysis.")
        if not trustable_measures:
            data_limitations.append("No clearly trustable numeric measures identified.")
        if caution_columns:
            data_limitations.append(
                f"{len(caution_columns)} column(s) have quality concerns: {', '.join(caution_columns[:3])}."
            )
        for warning in warnings[:3]:
            data_limitations.append(warning)

        return {
            "readiness_score": readiness_score,
            "readiness_label": readiness_label,
            "trustable_measures": trustable_measures,
            "caution_columns": caution_columns,
            "outcome_columns": outcome_columns,
            "segment_dimensions": segment_dimensions,
            "time_columns": time_columns,
            "quality_warnings": warnings,
            "data_preparation_notes": preparation_notes,
            "domain_context": {
                "target_variable": outcome_columns[0] if outcome_columns else None,
                "key_segments": segment_dimensions[:3],
                "numeric_measures": trustable_measures[:5],
            },
            "recommended_focus": recommended_focus[:5],
            "data_limitations": data_limitations[:6],
        }

    def answer(
        self,
        message: str,
        dataset: dict[str, Any],
        history: list[dict[str, Any]] | None = None,
        shared_state: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self._ensure_contract(dataset)
        deterministic_answer = self._relational_schema_answer(dataset.get("profile", {}) or {}, message)
        if deterministic_answer:
            return {
                "answer": deterministic_answer,
                "evidence": [
                    "Delegated this request to the DataEngineerAgent.",
                    "Formatted the stored relational schema metadata and data engineering profile.",
                    f"Profile source: dataset '{dataset['name']}' with {dataset['row_count']} working rows.",
                ],
                "sql": None,
                "data": [],
                "chart": None,
                "confidence": 0.88,
                "mode": "data_engineering",
            }
        prompt_info = self._prompt_info(message, dataset, history or [], shared_state=shared_state)
        if hasattr(self.agent, "run"):
            try:
                run_output = self.agent.run(prompt_info["rendered_prompt"], stream=False)
                content = str(getattr(run_output, "content", "") or "").strip()
                if content:
                    return {
                        "answer": content,
                        "evidence": [
                            "Delegated this request to the DataEngineerAgent.",
                            "Used the stored data engineering contract, column descriptions, and profile quality evidence.",
                            f"Profile source: dataset '{dataset['name']}' with {dataset['row_count']} rows.",
                        ],
                        "sql": None,
                        "data": [],
                        "chart": None,
                        "confidence": 0.83,
                        "mode": "data_engineering",
                        "_prompt_info": prompt_info,
                        "_token_usage": self._extract_run_usage(run_output),
                    }
            except Exception:
                pass
        return self._fallback_answer(dataset, message)

    def should_lead(
        self,
        message: str,
        dataset: dict[str, Any],
        previous_lead: str | None = None,
        history: list[dict[str, Any]] | None = None,
    ) -> bool:
        normalized = re.sub(r"[^a-z0-9]+", " ", message.lower()).strip()
        tokens = set(normalized.split())
        if self._looks_like_existing_data_pulse_chart_explanation(normalized):
            return False
        prep_terms = {
            "clean",
            "cleaning",
            "prepare",
            "preparation",
            "preprocess",
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
            "trust",
            "reliable",
            "engineering",
            "summary",
            "warnings",
            "actions",
            "readiness",
            "role",
            "roles",
            "semantic",
        }
        # Also match UI references like "engineering summary", "data pulse", "readiness panel"
        ui_refs = {"data pulse", "engineering summary", "readiness panel", "profile overview", "column explorer"}
        if tokens & ui_refs or any(phrase in normalized for phrase in ui_refs):
            return True
        if tokens & prep_terms:
            return True
        if previous_lead == "data_engineer" and normalized in {"why", "how", "what do you mean", "explain"}:
            return True
        return False

    def _looks_like_existing_data_pulse_chart_explanation(self, normalized: str) -> bool:
        chart_terms = {"chart", "plot", "graph", "histogram", "distribution", "visual", "visualization"}
        explanation_terms = {
            "explain", "interpret", "meaning", "mean", "means", "understand", "about",
            "what", "why", "how", "tell", "describe",
        }
        ui_terms = {"data pulse", "column explorer", "univariate"}
        tokens = set(normalized.split())
        return bool(tokens & chart_terms) and bool(tokens & explanation_terms) and any(term in normalized for term in ui_terms)

    def _prompt_info(
        self,
        message: str,
        dataset: dict[str, Any],
        history: list[dict[str, Any]],
        shared_state: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        contract = self._ensure_contract(dataset)
        compact_history = []
        for item in history[-8:]:
            role = str(item.get("role", "")).strip()
            content = str(item.get("content", "")).strip()
            if role and content:
                compact_history.append({"role": role, "content": content[:500]})

        prompt = (
            "You are the DataEngineerAgent inside Data-Berge OS.\n"
            "Answer only from the stored data engineering contract and dataset profile.\n"
            "Your job is to help the user understand dataset readiness, cleaning steps, semantic roles, "
            "null handling, typing, lineage, and practical preparation suggestions.\n"
            "Do not write SQL. Do not invent statistics that are not present in the profile or contract.\n"
            "If the user asks for cleaning advice, prioritize concrete next steps and mention risk areas.\n"
            "If the user asks about schema meaning, use human column descriptions when available.\n"
            "If the user asks about UI elements (like 'Data Pulse', 'engineering summary', 'column chart'), "
            "use the app context below to map UI references to the correct data concepts.\n"
            "If this is a mixed Analyst/Engineer parallel request, answer only the schema, typing, relationship, "
            "quality, and preparation parts. Do not redirect the whole question to the analyst path.\n"
            "If the request has no data-preparation or schema aspect at all, say briefly that it belongs with the analyst path.\n"
            "Keep the answer natural and concise.\n\n"
            f"{APP_CONTEXT}\n\n"
            f"Dataset name: {dataset['name']}\n"
            f"Rows: {dataset['row_count']}\n"
            f"Recent conversation JSON: {json.dumps(compact_history, ensure_ascii=False)}\n"
            f"Coordinator state JSON: {json.dumps(shared_state or {}, ensure_ascii=False)}\n"
            f"Data engineering contract JSON: {json.dumps(contract, ensure_ascii=False)}\n"
            f"Profile schema context JSON: {json.dumps(self._compact_profile_context(dataset.get('profile', {})), ensure_ascii=False)}\n"
            f"Profile metadata JSON: {json.dumps(dataset.get('profile', {}).get('metadata', {}), ensure_ascii=False)}\n"
            f"Profile quality flags JSON: {json.dumps(dataset.get('profile', {}).get('quality_flags', []), ensure_ascii=False)}\n"
            f"User question: {message}\n"
        )
        return {
            "name": "data-engineer-advisor",
            "version": "code",
            "source": "code",
            "uri": "",
            "rendered_prompt": prompt,
        }

    def _fallback_answer(self, dataset: dict[str, Any], message: str) -> dict[str, Any]:
        profile = dataset.get("profile", {}) or {}
        contract = self._ensure_contract(dataset)
        normalized = re.sub(r"[^a-z0-9]+", " ", message.lower()).strip()
        tokens = set(normalized.split())

        if tokens & {"meaning", "meanings", "describe", "description", "descriptions", "schema", "column", "columns"}:
            answer = self._column_meaning_answer(profile)
        elif tokens & {"missing", "null", "nulls", "duplicate", "duplicates", "quality"}:
            answer = self._quality_answer(profile, contract)
        elif tokens & {"date", "dates", "datetime", "time", "cast", "typing", "type", "types"}:
            answer = self._typing_answer(profile)
        else:
            answer = self._cleaning_answer(profile, contract)

        return {
            "answer": answer,
            "evidence": [
                "Delegated this request to the DataEngineerAgent.",
                "Used the stored data engineering contract and profiling metadata.",
                f"Profile source: dataset '{dataset['name']}' with {dataset['row_count']} rows.",
            ],
            "sql": None,
            "data": [],
            "chart": None,
            "confidence": 0.78,
            "mode": "data_engineering",
        }

    def _cleaning_answer(self, profile: dict[str, Any], contract: dict[str, Any]) -> str:
        readiness = contract.get("readiness_score", "n/a")
        warnings = contract.get("warnings", [])[:3]
        actions = contract.get("recommended_actions", [])[:4]
        parts = [
            f"The dataset is currently at {readiness}/10 readiness for downstream analytics.",
            str(contract.get("summary") or "").strip(),
        ]
        if warnings:
            parts.append("Main issues to watch: " + "; ".join(str(item) for item in warnings) + ".")
        if actions:
            parts.append("I would clean it in this order: " + "; ".join(str(item) for item in actions) + ".")
        if not warnings and not actions:
            parts.append("The current profile does not show major prep issues, so the next step is focused analysis rather than structural cleaning.")
        return " ".join(part for part in parts if part)

    def _quality_answer(self, profile: dict[str, Any], contract: dict[str, Any]) -> str:
        metadata = get_flat_profile(profile).get("metadata", {}) or {}
        missing_cells = metadata.get("missing_cells", 0)
        duplicate_rows = metadata.get("duplicate_rows", 0)
        warnings = contract.get("warnings", [])[:4]
        described = metadata.get("described_columns", 0)
        column_count = profile.get("column_count", 0)
        parts = [
            f"Quality-wise, I see {missing_cells} missing cells and {duplicate_rows} duplicate rows.",
            f"{described} of {column_count} columns have human descriptions.",
        ]
        if warnings:
            parts.append("Specific prep warnings: " + "; ".join(str(item) for item in warnings) + ".")
        return " ".join(parts)

    def _typing_answer(self, profile: dict[str, Any]) -> str:
        time_like = []
        for column in get_flat_profile(profile).get("columns", []):
            candidate_pct = float(column.get("datetime_candidate_pct") or 0)
            if candidate_pct >= 80 or str(column.get("engineering_role")) == "time":
                time_like.append((str(column.get("name")), candidate_pct, str(column.get("semantic_type"))))
        if not time_like:
            return "I do not see a strong time-casting issue in the current profile. Most fields already look aligned with their current semantic role."
        parts = []
        for name, candidate_pct, semantic_type in time_like[:4]:
            if semantic_type == "datetime":
                parts.append(f"{name} is already treated as a time field")
            else:
                parts.append(f"{name} looks time-like ({candidate_pct:.0f}% parseable)")
        return "For typing, I would review these fields first: " + "; ".join(parts) + "."

    def _column_meaning_answer(self, profile: dict[str, Any]) -> str:
        relational_schema = profile.get("relational_schema")
        if isinstance(relational_schema, dict) and relational_schema.get("tables"):
            parts = []
            for table in relational_schema.get("tables", [])[:6]:
                columns = ", ".join(str(column) for column in table.get("columns", [])[:8])
                parts.append(
                    f"{table.get('name')}: {table.get('row_count', 0)} rows, "
                    f"{table.get('column_count', 0)} columns ({columns})"
                )
            return "Here is the current table schema map: " + " | ".join(parts) + "."

        columns = []
        for column in get_flat_profile(profile).get("columns", [])[:12]:
            name = str(column.get("name"))
            description = str(column.get("description") or "").strip()
            role = str(column.get("engineering_role") or column.get("semantic_type") or "unknown")
            if description:
                columns.append(f"{name}: {description} [{role}]")
            else:
                columns.append(f"{name}: inferred as {role}")
        if not columns:
            return "I do not have column metadata yet for this dataset."
        return "Here is the current column meaning map: " + " | ".join(columns) + "."

    def _relational_schema_answer(self, profile: dict[str, Any], message: str) -> str | None:
        relational_schema = profile.get("relational_schema")
        if not isinstance(relational_schema, dict) or not relational_schema.get("tables"):
            return None

        normalized = re.sub(r"[^a-z0-9]+", " ", message.lower()).strip()
        if not any(term in normalized.split() for term in {"schema", "column", "columns", "relationship", "relationships"}):
            return None

        tables = relational_schema.get("tables", []) or []
        selected = None
        for table in tables:
            table_name = str(table.get("name") or "")
            if table_name and re.search(rf"\b{re.escape(table_name.lower())}\b", normalized):
                selected = table
                break

        if selected is None and len(tables) == 1:
            selected = tables[0]
        if selected is None:
            table_bits = [
                f"{table.get('name')}: {table.get('row_count', 0)} rows, {table.get('column_count', 0)} columns"
                for table in tables
            ]
            relationship_count = relational_schema.get("relationship_count", 0)
            return (
                f"This model has {relational_schema.get('table_count', len(tables))} tables and "
                f"{relationship_count} active relationships. " + " | ".join(table_bits)
            )

        return self._format_relational_table_schema(profile, relational_schema, selected)

    def _format_relational_table_schema(
        self, profile: dict[str, Any], relational_schema: dict[str, Any], table: dict[str, Any]
    ) -> str:
        table_name = str(table.get("name") or "Table")
        flat_columns = {
            str(column.get("name")): column
            for column in get_flat_profile(profile).get("columns", [])
            if column.get("name")
        }
        relationships = relational_schema.get("relationships", []) or []
        table_relationships = [
            relationship
            for relationship in relationships
            if relationship.get("from_table") == table_name or relationship.get("to_table") == table_name
        ]

        lines = [
            f"{table_name} has {table.get('row_count', 0)} rows and {table.get('column_count', 0)} columns.",
            "",
            "| Column | Type | Role | Notes |",
            "| --- | --- | --- | --- |",
        ]

        for column_name in table.get("columns", []) or []:
            column_name = str(column_name)
            profile_column = flat_columns.get(f"{table_name}__{column_name}") or flat_columns.get(column_name) or {}
            dtype = str(profile_column.get("semantic_type") or profile_column.get("dtype") or "unknown")
            role, notes = self._relational_column_role(table_name, column_name, table_relationships, profile_column)
            lines.append(
                "| "
                + " | ".join(
                    self._markdown_cell(value)
                    for value in [column_name, dtype, role, notes]
                )
                + " |"
            )

        if table_relationships:
            lines.extend(["", "Relationships:"])
            for relationship in table_relationships:
                confidence = relationship.get("confidence")
                confidence_text = f", confidence {float(confidence):.0%}" if isinstance(confidence, (int, float)) else ""
                lines.append(
                    "- "
                    f"{relationship.get('from_table')}.{relationship.get('from_column')} -> "
                    f"{relationship.get('to_table')}.{relationship.get('to_column')} "
                    f"({relationship.get('cardinality', 'unknown')}{confidence_text})"
                )

        prep_notes = self._relational_table_prep_notes(table_name, table.get("columns", []) or [], flat_columns)
        if prep_notes:
            lines.extend(["", "Preparation notes:"])
            lines.extend(f"- {note}" for note in prep_notes)

        return "\n".join(lines)

    def _relational_column_role(
        self,
        table_name: str,
        column_name: str,
        relationships: list[dict[str, Any]],
        profile_column: dict[str, Any],
    ) -> tuple[str, str]:
        inbound = [
            relationship for relationship in relationships
            if relationship.get("to_table") == table_name and relationship.get("to_column") == column_name
        ]
        outbound = [
            relationship for relationship in relationships
            if relationship.get("from_table") == table_name and relationship.get("from_column") == column_name
        ]
        if inbound and outbound:
            return "Primary / foreign key", "Referenced by another table and links out to another table."
        if inbound:
            refs = ", ".join(f"{rel.get('from_table')}.{rel.get('from_column')}" for rel in inbound[:3])
            return "Primary key", f"Referenced by {refs}."
        if outbound:
            targets = ", ".join(f"{rel.get('to_table')}.{rel.get('to_column')}" for rel in outbound[:3])
            return "Foreign key", f"Links to {targets}."

        role = str(profile_column.get("engineering_role") or profile_column.get("semantic_type") or "Field")
        description = str(profile_column.get("description") or "").strip()
        if description:
            return role, description
        return role, "Profiled from the working relational dataset."

    def _relational_table_prep_notes(
        self, table_name: str, columns: list[Any], flat_columns: dict[str, dict[str, Any]]
    ) -> list[str]:
        notes: list[str] = []
        for column_name in columns:
            profile_column = flat_columns.get(f"{table_name}__{column_name}") or flat_columns.get(str(column_name)) or {}
            semantic_type = str(profile_column.get("semantic_type") or "")
            candidate_pct = float(profile_column.get("datetime_candidate_pct") or 0)
            role = str(profile_column.get("engineering_role") or "")
            if semantic_type != "datetime" and (candidate_pct >= 80 or role == "time"):
                notes.append(f"Cast {column_name} to datetime before time-based analysis.")
        return notes[:3]

    def _markdown_cell(self, value: Any) -> str:
        return str(value).replace("|", "\\|").replace("\n", " ").strip() or "-"

    def _compact_profile_context(self, profile: dict[str, Any]) -> dict[str, Any]:
        relational_schema = profile.get("relational_schema")
        if isinstance(relational_schema, dict) and relational_schema:
            return {
                "format": "relational",
                "table_count": relational_schema.get("table_count"),
                "relationship_count": relational_schema.get("relationship_count"),
                "tables": relational_schema.get("tables", []),
                "relationships": relational_schema.get("relationships", []),
                "analysis_dataset_note": relational_schema.get("analysis_dataset_note"),
            }
        flat = get_flat_profile(profile)
        return {
            "format": "flat",
            "row_count": flat.get("row_count"),
            "column_count": flat.get("column_count"),
            "columns": [
                {
                    "name": column.get("name"),
                    "semantic_type": column.get("semantic_type"),
                    "engineering_role": column.get("engineering_role"),
                    "description": column.get("description"),
                    "missing_pct": column.get("missing_pct"),
                }
                for column in (flat.get("columns") or [])[:20]
            ],
        }

    def _ensure_contract(self, dataset: dict[str, Any]) -> dict[str, Any]:
        context = self._coerce_context(dataset)
        profile = context.profile
        contract = profile.get("data_engineering", {}) or {}
        if contract and contract.get("version") == DATA_ENGINEERING_CONTRACT_VERSION:
            dataset["profile"] = profile
            return contract
        if not context.working_path:
            return {}
        try:
            df = self.load_dataframe_fn(context.working_path)
            contract = self.prepare_contract_fn(df, profile)
            profile["data_engineering"] = contract
            persisted = self.profile_provider.save_profile(context, profile)
            if persisted is not None:
                dataset["profile"] = persisted.profile
                dataset["working_path"] = persisted.working_path
            else:
                dataset["profile"] = profile
            return contract
        except Exception:
            return {}

    def _coerce_context(self, dataset: dict[str, Any]) -> DatasetContext:
        if isinstance(dataset, DatasetContext):
            return dataset
        return DatasetContext.from_record(dataset)

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

        payload: dict[str, Any] = {}
        if usage:
            payload["usage"] = usage
        if model := getattr(run_output, "model", None):
            payload["model"] = model
        if provider := getattr(run_output, "model_provider", None):
            payload["provider"] = provider
        return payload
