from __future__ import annotations

import json
import re
import uuid
from typing import Any

from data_berge_core.contracts import ArtifactStore, ProfileProvider, QueryRunner
from data_berge_core.runtime import AgentFactory, AgentSpec, ToolkitFactory
from data_berge_core.contracts import get_flat_profile, normalize_top_values
from data_berge_core.report_document import is_usable_chart
from data_berge_core.skills.report_templates import (
    REPORT_TEMPLATES,
    build_block_schemas,
    get_block_keys,
    get_template,
)

DRAFT_BRIEF_TEMPLATE = "draft_brief"
DRAFT_BRIEF_BLOCKS = [
    "executive_summary",
    "key_findings",
    "business_implications",
    "recommendations",
    "next_steps",
    "charts",
]
DRAFT_BRIEF_BLOCK_DEFINITIONS = [
    {"key": "executive_summary", "label": "Executive Summary", "description": "Concise report summary", "required": True},
    {"key": "key_findings", "label": "Key Findings", "description": "Main evidence-backed findings", "required": True},
    {"key": "business_implications", "label": "Business Implications", "description": "Meaning and impact of the findings", "required": True},
    {"key": "recommendations", "label": "Recommendations", "description": "Recommended actions", "required": True},
    {"key": "next_steps", "label": "Next Steps", "description": "Immediate follow-up actions", "required": True},
    {"key": "charts", "label": "Charts", "description": "Supporting visualizations", "required": False},
]


class ReportingSkill:
    spec = AgentSpec(
        name="ReportingSkill",
        role="Create executive analytics narratives from verified profile evidence.",
        instructions=(
            "Draft concise reports with findings, implications, recommendations, and next steps. "
            "Align the narrative with target audience, business goal, decision horizon, risk tolerance, "
            "tone, and focus areas. Ground every claim in provided profile/query evidence, avoid unsupported "
            "speculation, and map chart takeaways to the charts being shown."
        ),
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
            include_tools=[
                "get_dataset_profile",
                "draft_report_payload",
                "create_report_artifact",
                "create_dashboard_artifact",
                "list_artifacts",
            ],
            profile_provider=profile_provider,
            query_runner=query_runner,
            artifact_store=artifact_store,
        )
        self.agent = agent_factory(self.spec, tools=[self.tools])
        self._last_draft_error: str | None = None

    def plan(
        self,
        dataset: dict[str, Any],
        context: dict[str, Any],
        message: str = "",
        previous_plan: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self._last_draft_error = None
        if hasattr(self.agent, "run"):
            plan = self._plan_with_llm(dataset, context, message, previous_plan=previous_plan)
            if plan:
                plan["generation_source"] = "llm"
                return plan
        else:
            self._last_draft_error = "The configured report model is unavailable."

        return {
            "version": int(previous_plan.get("version", 0)) + 1 if previous_plan else 1,
            "plan_id": str(previous_plan.get("plan_id") or uuid.uuid4().hex) if previous_plan else uuid.uuid4().hex,
            "status": "failed",
            "title": "Report plan unavailable",
            "template": "custom",
            "sections": [],
            "generation_source": "failed",
            "generation_warning": self._last_draft_error
            or "The report model did not return a valid custom report plan.",
        }

    def draft(self, dataset: dict[str, Any], context: dict[str, Any], message: str = "") -> dict[str, Any]:
        """Backward-compatible alias for callers that request a report plan."""
        return self.plan(dataset, context, message)

    def narrate(
        self,
        dataset: dict[str, Any],
        context: dict[str, Any],
        readiness_brief: dict[str, Any],
        findings: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Use LLM to generate a structured executive report from findings."""
        # Build the narrative with or without LLM
        if hasattr(self.agent, "run"):
            narrative = self._narrate_with_llm(dataset, context, readiness_brief, findings)
            if narrative:
                narrative["generation_source"] = "llm"
                return narrative

        fallback = self._narrate_fallback(dataset, context, readiness_brief, findings)
        fallback["generation_source"] = "deterministic_fallback"
        fallback["generation_warning"] = "The report model did not complete narrative generation."
        return fallback

    def narrate_enhanced(
        self,
        dataset: dict[str, Any],
        context: dict[str, Any],
        readiness_brief: dict[str, Any],
        findings: list[dict[str, Any]],
        template: str = "executive",
        blocks: list[str] | None = None,
        block_definitions: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Generate an enhanced report using the selected template and blocks."""
        tmpl = get_template(template)
        if tmpl is None:
            if block_definitions:
                tmpl = {
                    "name": str(context.get("report_type") or "Custom Report"),
                    "blocks": block_definitions,
                }
            else:
                template = "executive"
                tmpl = get_template("executive")

        active_blocks = blocks if blocks is not None else [b["key"] for b in tmpl["blocks"]]
        resolved_blocks = self._resolve_block_definitions(template, active_blocks, block_definitions)

        if hasattr(self.agent, "run"):
            narrative = self._narrate_enhanced_with_llm(dataset, context, readiness_brief, findings, template, active_blocks, resolved_blocks)
            if narrative:
                narrative["generation_source"] = "llm"
                return narrative

        if template == "custom":
            raise RuntimeError(
                "The ReportAgent could not generate the approved custom report. No fixed template was substituted."
            )

        fallback = self._narrate_enhanced_fallback(
            dataset,
            context,
            readiness_brief,
            findings,
            template,
            active_blocks,
            resolved_blocks,
        )
        fallback["generation_source"] = "deterministic_fallback"
        fallback["generation_warning"] = "The report model did not complete narrative generation."
        return fallback

    def _narrate_enhanced_with_llm(
        self,
        dataset: dict[str, Any],
        context: dict[str, Any],
        readiness_brief: dict[str, Any],
        findings: list[dict[str, Any]],
        template: str = "executive",
        active_blocks: list[str] | None = None,
        block_definitions: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any] | None:
        prompt = self._enhanced_narration_prompt(dataset, context, readiness_brief, findings, template, active_blocks, block_definitions)
        try:
            run_output = self.agent.run(prompt, stream=False)
            content = str(getattr(run_output, "content", "") or "").strip()
            if not content:
                return None
            parsed = self._parse_json_content(content)
            if parsed and isinstance(parsed, dict):
                return self._enrich_enhanced_narrative(parsed, dataset, context, readiness_brief, findings, template, active_blocks, block_definitions)
        except Exception:
            pass
        return None

    def _enhanced_narration_prompt(
        self,
        dataset: dict[str, Any],
        context: dict[str, str | list[str]],
        readiness_brief: dict[str, Any],
        findings: list[dict[str, Any]],
        template: str = "executive",
        active_blocks: list[str] | None = None,
        block_definitions: list[dict[str, Any]] | None = None,
    ) -> str:
        dataset_evidence = self._compact_dataset_evidence(dataset)
        findings_text = ""
        for i, f in enumerate(findings, 1):
            data_summary = str(f.get("data_preview", [])[:3])
            findings_text += (
                f"\nFinding {i}: {f.get('finding', '')}\n"
                f"  SQL: {f.get('sql', '')}\n"
                f"  Confidence: {f.get('confidence', 'medium')}\n"
                f"  Data preview: {data_summary}\n"
            )

        limitations = "\n".join(f"- {l}" for l in readiness_brief.get("data_limitations", []))
        preparation_notes = "\n".join(
            f"- {note}" for note in readiness_brief.get("data_preparation_notes", [])
        ) or "- None"
        measures = ", ".join(readiness_brief.get("trustable_measures", []))
        caution = ", ".join(readiness_brief.get("caution_columns", []))

        tmpl = get_template(template)
        if tmpl is None:
            tmpl = {
                "name": str(context.get("report_type") or "Custom Report"),
                "blocks": block_definitions or self._resolve_block_definitions(template, active_blocks),
            }
        tmpl_name = tmpl["name"]
        resolved_blocks = block_definitions or self._resolve_block_definitions(template, active_blocks)
        block_schemas = self._build_block_schemas_from_definitions(template, resolved_blocks)
        contract_json = json.dumps(block_schemas, indent=2)
        output_example = {
            "title": "Report title including the dataset name",
            **{key: self._schema_example(schema) for key, schema in block_schemas.items()},
        }
        output_example_json = json.dumps(output_example, indent=2)

        block_descriptions = []
        for block in resolved_blocks:
            key = block["key"]
            label = block.get("label") or key.replace("_", " ").title()
            fields = ", ".join(str(field) for field in (block.get("data_fields") or []))
            chart_intent = str(block.get("chart_intent") or "")
            details = [str(block.get("description") or "")]
            if fields:
                details.append(f"Evidence fields: {fields}")
            if chart_intent:
                details.append(f"Chart intent: {chart_intent}")
            block_descriptions.append(
                f"- {label}: {'; '.join(item for item in details if item)}"
            )

        blocks_section = "\n".join(block_descriptions) if block_descriptions else "Generate all standard report sections."

        return (
            f"You are the ReportingSkill inside Data-Berge OS.\n"
            f"Generate a {tmpl_name} as JSON.\n\n"
            f"Dataset: {dataset.get('name', 'unknown')} ({dataset.get('row_count', 0)} rows, {dataset.get('column_count', 0)} columns)\n"
            f"Verified dataset evidence JSON: {json.dumps(dataset_evidence, default=str, ensure_ascii=False)}\n"
            f"Audience: {context.get('audience', 'Leadership team')}\n"
            f"Goal: {context.get('goal', 'Summarize key findings')}\n"
            f"Time horizon: {context.get('horizon', 'Next quarter')}\n"
            f"Tone: {context.get('tone', 'Strategic')}\n"
            f"Focus areas: {', '.join(context.get('focus_areas', []))}\n\n"
            f"Data Readiness: {readiness_brief.get('readiness_score', '?')}/10 ({readiness_brief.get('readiness_label', '?')})\n"
            f"Trustable measures: {measures}\n"
            f"Caution columns: {caution}\n\n"
            f"Investigation findings:{findings_text}\n\n"
            f"Data limitations:\n{limitations}\n\n"
            f"Data preparation notes (not evidence that values are invalid):\n{preparation_notes}\n\n"
            f"Report blocks to generate:\n{blocks_section}\n\n"
            f"Content contracts for each top-level report block (instructions only):\n{contract_json}\n\n"
            f"Return this JSON shape and replace every placeholder with actual report content:\n{output_example_json}\n\n"
            "Rules:\n"
            "- Cite SPECIFIC numbers from findings (e.g., 'Average income for approved loans is $85,000')\n"
            "- Every key_metrics value must be a verified numeric value, percentage, ratio, currency amount, or date-linked number; qualitative labels such as 'Positive Growth' are findings, not metrics\n"
            "- Only include blocks that were requested — do NOT add extra sections\n"
            "- Severity must match the evidence: critical=urgent action needed, concerning=needs attention, good=positive finding, info=neutral observation\n"
            "- The data_story must explain WHY, not just WHAT. Connect patterns to root causes.\n"
            "- Action plan must be phased: immediate (days), short-term (months), long-term (6+ months)\n"
            "- Prognosis must reference actual data projections\n"
            "- References must link each finding to its source query or column\n"
            "- Do NOT make unsupported claims\n"
            "- Reference data limitations honestly\n"
            "- Treat field descriptions in Verified dataset evidence JSON as authoritative semantics\n"
            "- Treat profile statistics, sample values, and query findings as applying only to the loaded workspace rows\n"
            "- Do not describe a valid source date as stale, legacy, malformed, or an integration problem unless the evidence explicitly says it is invalid\n"
            "- A type-casting preparation note is not evidence that the underlying values are wrong\n"
            "- Chart data is attached from verified profile or query evidence after narration; return an empty array for chart blocks and do not invent chart values\n"
            "- Write in a professional but accessible tone\n"
            "- Section values must contain report content directly\n"
            "- Never copy JSON Schema metadata such as description, type, items, properties, or enum into a section value\n"
            "- Return JSON only, no markdown"
        )

    def _enrich_enhanced_narrative(
        self,
        narrative: dict[str, Any],
        dataset: dict[str, Any],
        context: dict[str, str | list[str]],
        readiness_brief: dict[str, Any],
        findings: list[dict[str, Any]],
        template: str = "executive",
        active_blocks: list[str] | None = None,
        block_definitions: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Ensure all required fields exist and add charts from findings."""
        chart_candidates = self._chart_candidates(dataset, findings)

        # Ensure SBAR structure
        es = narrative.get("executive_summary", {})
        if isinstance(es, str):
            es = {"situation": [es], "background": [], "assessment": [], "recommendation": []}

        # Ensure key_metrics
        key_metrics = self._validated_key_metrics(narrative.get("key_metrics", []))
        if not key_metrics:
            key_metrics = self._build_default_metrics(findings, readiness_brief)

        enhanced_findings = self._grounded_findings(narrative.get("findings", []), findings)

        resolved_blocks = block_definitions or self._resolve_block_definitions(template, active_blocks)
        block_order = [str(block.get("key")) for block in resolved_blocks if block.get("key")]
        block_labels = {
            str(block.get("key")): str(block.get("label") or str(block.get("key")).replace("_", " ").title())
            for block in resolved_blocks
            if block.get("key")
        }
        blocks_enabled = set(block_order)

        result: dict[str, Any] = {
            "title": narrative.get("title") or f"Report: {dataset.get('name', 'Dataset')}",
            "template": template,
            "report_type": context.get("report_type") or ("Custom Report" if template == "custom" else template),
            "block_order": block_order,
            "block_labels": block_labels,
            "context": context,
            "evidence_context": self._compact_dataset_evidence(dataset),
            "readiness": {
                "score": readiness_brief.get("readiness_score"),
                "label": readiness_brief.get("readiness_label"),
                "limitations": readiness_brief.get("data_limitations", []),
            },
        }

        if "central_theme" in blocks_enabled:
            result["central_theme"] = narrative.get("central_theme", "")

        if "executive_summary" in blocks_enabled:
            result["executive_summary"] = {
                "situation": es.get("situation", []),
                "background": es.get("background", []),
                "assessment": es.get("assessment", []),
                "recommendation": es.get("recommendation", []),
            }

        if "key_metrics" in blocks_enabled:
            result["key_metrics"] = key_metrics

        if "findings" in blocks_enabled:
            result["findings"] = enhanced_findings

        if "top_findings" in blocks_enabled:
            top = enhanced_findings[:5]
            result["top_findings"] = [
                {"title": f["title"], "severity": f["severity"], "evidence": f["evidence"]}
                for f in top
            ]

        if "data_story" in blocks_enabled:
            result["data_story"] = narrative.get("data_story", "")

        if "systems_detail" in blocks_enabled:
            result["systems_detail"] = narrative.get("systems_detail", [])

        if "action_plan" in blocks_enabled:
            result["action_plan"] = narrative.get("action_plan", {"immediate": [], "short_term": [], "long_term": []})

        if "prognosis" in blocks_enabled:
            result["prognosis"] = narrative.get("prognosis", {"current_state": "", "with_recommendations": ""})

        if "charts" in blocks_enabled:
            charts_block = next((block for block in resolved_blocks if block.get("key") == "charts"), {})
            result["charts"] = self._charts_for_block(charts_block, chart_candidates)

        if "references" in blocks_enabled:
            result["references"] = narrative.get("references", [])

        if "summary" in blocks_enabled:
            result["summary"] = narrative.get("summary", narrative.get("central_theme", ""))

        if "problem_statement" in blocks_enabled:
            result["problem_statement"] = narrative.get("problem_statement", "")

        if "methodology" in blocks_enabled:
            result["methodology"] = narrative.get("methodology", "")

        if "conclusions" in blocks_enabled:
            result["conclusions"] = narrative.get("conclusions", "")

        if "overview" in blocks_enabled:
            result["overview"] = narrative.get("overview", "")

        if "data_quality_assessment" in blocks_enabled:
            result["data_quality_assessment"] = narrative.get("data_quality_assessment", {
                "overall_score": readiness_brief.get("readiness_score", 5),
                "strengths": [],
                "weaknesses": readiness_brief.get("data_limitations", []),
                "recommendations": [],
            })

        if "schema_analysis" in blocks_enabled:
            result["schema_analysis"] = narrative.get("schema_analysis", {
                "total_columns": dataset.get("column_count", 0),
                "column_breakdown": {},
                "key_relationships": [],
            })

        if "recommendations" in blocks_enabled:
            result["recommendations"] = narrative.get("recommendations", [])

        for block in resolved_blocks:
            key = str(block.get("key") or "")
            if not key or key in result:
                continue
            value = (
                self._charts_for_block(block, chart_candidates)
                if block.get("kind") == "chart"
                else narrative.get(key)
            )
            if value is None:
                value = []
            result[key] = value

        result["sections"] = self._sections_from_result(result, resolved_blocks)
        return result

    @staticmethod
    def _validated_key_metrics(value: Any) -> list[dict[str, Any]]:
        if not isinstance(value, list):
            return []
        metrics: list[dict[str, Any]] = []
        for metric in value:
            if not isinstance(metric, dict):
                continue
            metric_value = str(metric.get("value", "")).strip()
            if metric_value and re.search(r"\d", metric_value):
                metrics.append(metric)
        return metrics

    @classmethod
    def _grounded_findings(
        cls,
        narrative_findings: Any,
        verified_findings: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        candidates = narrative_findings if isinstance(narrative_findings, list) else []
        grounded: list[dict[str, Any]] = []
        for index, source in enumerate(verified_findings):
            candidate = candidates[index] if index < len(candidates) and isinstance(candidates[index], dict) else {}
            candidate_title = str(candidate.get("title") or candidate.get("finding") or "").strip()
            candidate_evidence = str(candidate.get("evidence") or "").strip()
            title = candidate_title if cls._is_result_statement(candidate_title) else str(source.get("finding", ""))
            evidence = candidate_evidence if cls._is_result_statement(candidate_evidence) else str(
                source.get("evidence") or source.get("finding", "")
            )
            severity = str(candidate.get("severity", "info")).casefold()
            if severity not in {"critical", "concerning", "good", "info"}:
                severity = "info"
            grounded.append({
                "title": title,
                "severity": severity,
                "confidence": source.get("confidence", "medium"),
                "evidence": evidence,
                "sql": source.get("sql", ""),
                "data_preview": source.get("data_preview", []),
                "chart": source.get("chart"),
                "columns_used": source.get("columns_used", []),
            })
        return grounded

    @staticmethod
    def _is_result_statement(value: str) -> bool:
        if not value or not re.search(r"\d", value):
            return False
        return not re.match(
            r"^\s*(calculate|analy[sz]e|compare|break\s*down|investigate|explore|identify|examine|evaluate)\b",
            value,
            re.I,
        )

    def _resolve_block_definitions(
        self,
        template: str,
        active_blocks: list[str] | None = None,
        block_definitions: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        if block_definitions:
            by_key = {
                str(block.get("key")): {
                    "key": str(block.get("key")),
                    "label": str(block.get("label") or str(block.get("key")).replace("_", " ").title()),
                    "description": str(block.get("description") or ""),
                    "required": bool(block.get("required", False)),
                    "kind": block.get("kind"),
                    "presentation": block.get("presentation") if isinstance(block.get("presentation"), dict) else None,
                    "data_fields": [
                        str(field)
                        for field in (block.get("data_fields") or [])
                        if str(field).strip()
                    ],
                    "chart_intent": str(block.get("chart_intent") or "") or None,
                }
                for block in block_definitions
                if block.get("key")
            }
            order = active_blocks or list(by_key)
            return [by_key[key] for key in order if key in by_key]

        tmpl = get_template(template) or get_template("executive")
        template_blocks = {str(block["key"]): block for block in tmpl["blocks"]}
        order = active_blocks or list(template_blocks)
        resolved: list[dict[str, Any]] = []
        for key in order:
            block = template_blocks.get(str(key))
            if block:
                resolved.append({
                    "key": str(block["key"]),
                    "label": str(block.get("label") or block["key"]),
                    "description": str(block.get("description") or ""),
                    "required": bool(block.get("required", False)),
                })
            else:
                resolved.append({
                    "key": str(key),
                    "label": str(key).replace("_", " ").title(),
                    "description": "",
                    "required": False,
                })
        return resolved

    def _build_block_schemas_from_definitions(
        self,
        template: str,
        block_definitions: list[dict[str, Any]],
    ) -> dict[str, Any]:
        known = build_block_schemas(template, [str(block.get("key")) for block in block_definitions])
        schemas: dict[str, Any] = {}
        for block in block_definitions:
            key = str(block.get("key") or "")
            if not key:
                continue
            description = str(block.get("description") or f"{block.get('label') or key} section")
            schemas[key] = known.get(key) or self._schema_for_section_kind(
                str(block.get("kind") or "narrative"),
                description,
            )
        return schemas

    def _schema_for_section_kind(self, kind: str, description: str) -> dict[str, Any]:
        if kind in {"narrative", "callout", "summary"}:
            return {"description": description, "type": "string"}
        if kind in {"actions", "bullets", "references"}:
            return {
                "description": description,
                "type": "array",
                "items": {"type": "string"},
            }
        if kind == "metrics":
            return {
                "description": description,
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "value": {"type": "string"},
                        "description": {"type": "string"},
                    },
                },
            }
        if kind == "findings":
            return {
                "description": description,
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "evidence": {"type": "string"},
                        "confidence": {"type": "string"},
                        "severity": {"type": "string"},
                    },
                },
            }
        if kind == "chart":
            return {
                "description": description,
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "type": {"type": "string"},
                        "title": {"type": "string"},
                        "x": {"type": "string"},
                        "y": {"type": "array", "items": {"type": "string"}},
                    },
                },
            }
        if kind == "comparison":
            return {
                "description": description,
                "type": "object",
                "properties": {
                    "current_state": {"type": "string"},
                    "with_recommendations": {"type": "string"},
                },
            }
        if kind == "key_value":
            return {
                "description": description,
                "type": "object",
                "properties": {
                    "headline": {"type": "string"},
                    "detail": {"type": "string"},
                },
            }
        return {
            "description": description,
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "label": {"type": "string"},
                    "value": {"type": "string"},
                },
            },
        }

    def _sections_from_result(
        self,
        result: dict[str, Any],
        block_definitions: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        sections: list[dict[str, Any]] = []
        for block in block_definitions:
            key = str(block.get("key") or "")
            if not key or key not in result:
                continue
            sections.append({
                "key": key,
                "label": str(block.get("label") or key.replace("_", " ").title()),
                "content": result.get(key),
                "kind": block.get("kind"),
                "presentation": block.get("presentation") if isinstance(block.get("presentation"), dict) else None,
            })
        return sections

    def _compact_dataset_evidence(self, dataset: dict[str, Any]) -> dict[str, Any]:
        raw_profile = dataset.get("profile", {}) or {}
        flat_profile = get_flat_profile(raw_profile)
        relational = raw_profile.get("relational_schema", {}) or {}
        source = relational.get("source") or raw_profile.get("source") or {}
        columns: list[dict[str, Any]] = []
        for column in flat_profile.get("columns", [])[:30]:
            entry = {
                "name": column.get("name"),
                "semantic_type": column.get("semantic_type"),
                "engineering_role": column.get("engineering_role"),
                "description": column.get("description"),
                "sample_values": (column.get("sample_values") or [])[:5],
                "top_values": normalize_top_values(column.get("top_values"))[:5],
                "quality_notes": column.get("quality_notes") or [],
                "preparation_notes": column.get("preparation_notes") or [],
            }
            stats = column.get("stats") if isinstance(column.get("stats"), dict) else {}
            if stats:
                entry["stats"] = {
                    key: stats.get(key)
                    for key in ("count", "min", "q1", "median", "mean", "q3", "max")
                    if stats.get(key) is not None
                }
            columns.append(entry)

        sample_limit = source.get("sample_limit")
        is_connector_sample = bool(
            source.get("source_type") == "opendosm" and sample_limit not in (None, "", 0)
        )
        return {
            "workspace": {
                "loaded_rows": dataset.get("row_count") or flat_profile.get("row_count"),
                "loaded_columns": dataset.get("column_count") or flat_profile.get("column_count"),
                "is_connector_sample": is_connector_sample,
                "sample_limit": sample_limit,
                "scope_rule": (
                    "Source catalogue metadata describes the full source; all profile statistics and findings "
                    "describe only the loaded workspace rows."
                    if is_connector_sample
                    else "All profile statistics and findings describe the current workspace dataset."
                ),
            },
            "source": {
                key: value
                for key, value in source.items()
                if key in {
                    "source_type", "dataset_id", "title", "description", "frequency",
                    "data_source", "data_as_of", "last_updated", "sample_limit", "original_name",
                }
                and value not in (None, "", [])
            },
            "columns": columns,
        }

    def _chart_candidates(
        self,
        dataset: dict[str, Any],
        findings: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        candidates: list[dict[str, Any]] = []
        signatures: set[str] = set()

        def add(chart: Any, fields: list[Any], description: str, origin: str) -> None:
            if not is_usable_chart(chart):
                return
            signature = json.dumps(chart, sort_keys=True, default=str)
            if signature in signatures:
                return
            signatures.add(signature)
            candidates.append({
                "chart": chart,
                "fields": {str(field).casefold() for field in fields if str(field).strip()},
                "description": description,
                "origin": origin,
            })

        for finding in findings:
            chart_value = finding.get("chart")
            finding_charts = chart_value if isinstance(chart_value, list) else [chart_value]
            for chart in finding_charts:
                add(
                    chart,
                    finding.get("columns_used") or [],
                    str(finding.get("finding") or ""),
                    "query",
                )

        columns = get_flat_profile(dataset.get("profile", {})).get("columns", [])
        for column in columns:
            for chart in self.tools.starter_charts([column]):
                add(
                    chart,
                    [column.get("name")],
                    f"Profile distribution for {column.get('name')}",
                    "profile",
                )
        return candidates

    def _charts_for_block(
        self,
        block: dict[str, Any],
        candidates: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        requested_fields = {
            str(field).casefold()
            for field in (block.get("data_fields") or [])
            if str(field).strip()
        }
        if requested_fields or block.get("chart_intent"):
            matched = [
                candidate
                for candidate in candidates
                if not requested_fields or requested_fields & candidate["fields"]
            ]
            ranked = sorted(
                matched,
                key=lambda candidate: self._chart_fit_score(block, candidate, requested_fields),
                reverse=True,
            )
            return [candidate["chart"] for candidate in ranked[:1]]
        return [candidate["chart"] for candidate in candidates[:5]]

    def _chart_fit_score(
        self,
        block: dict[str, Any],
        candidate: dict[str, Any],
        requested_fields: set[str],
    ) -> float:
        chart = candidate["chart"]
        purpose = " ".join(
            str(block.get(key) or "")
            for key in ("label", "description", "chart_intent")
        ).casefold()
        chart_text = f"{chart.get('title', '')} {candidate.get('description', '')}".casefold()
        fields = candidate.get("fields") or set()
        score = float(len(requested_fields & fields) * 20)
        score -= float(len(fields - requested_fields) * 2) if requested_fields else 0.0

        distribution_terms = {"distribution", "range", "concentration", "spread", "histogram", "magnitude"}
        trend_terms = {"trend", "over time", "timeline", "year", "monthly", "annual"}
        comparison_terms = {"compare", "comparison", "segment", "category", "group", "breakdown"}
        if any(term in purpose for term in distribution_terms):
            if "distribution" in chart_text or candidate.get("origin") == "profile":
                score += 30
            if chart.get("type") == "table":
                score -= 12
        if any(term in purpose for term in trend_terms):
            if chart.get("type") == "line" or any(term in chart_text for term in trend_terms):
                score += 20
        if any(term in purpose for term in comparison_terms):
            if chart.get("type") in {"bar", "donut"} and candidate.get("origin") == "query":
                score += 15

        rows = chart.get("data") or []
        x_key = chart.get("x")
        if isinstance(rows, list) and x_key:
            distinct_x = {str(row.get(x_key)) for row in rows if isinstance(row, dict) and x_key in row}
            score += min(8.0, float(len(distinct_x)))
            if len(distinct_x) <= 1:
                score -= 8
        return score

    def _schema_example(self, schema: dict[str, Any]) -> Any:
        schema_type = schema.get("type")
        if schema_type == "object":
            return {
                key: self._schema_example(value)
                for key, value in (schema.get("properties") or {}).items()
            }
        if schema_type == "array":
            item_schema = schema.get("items")
            if isinstance(item_schema, dict) and item_schema:
                return [self._schema_example(item_schema)]
            return []
        if schema_type == "number":
            return 0
        if schema_type == "boolean":
            return False
        return "actual report content"

    def _build_default_metrics(
        self,
        findings: list[dict[str, Any]],
        readiness_brief: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Build key metrics from findings and readiness brief."""
        metrics: list[dict[str, Any]] = []
        score = readiness_brief.get("readiness_score", 5)
        health = "good" if score >= 7 else "concerning" if score >= 5 else "critical"
        metrics.append({
            "name": "Data Readiness",
            "value": f"{score}/10",
            "health": health,
            "trend": "stable",
            "score": int(score * 10),
            "description": readiness_brief.get("readiness_label", "Unknown"),
        })
        metrics.append({
            "name": "Investigation Queries",
            "value": str(len(findings)),
            "health": "good" if len(findings) >= 3 else "concerning",
            "trend": "stable",
            "score": min(100, len(findings) * 20),
            "description": f"{len(findings)} queries executed",
        })
        high_conf = sum(1 for f in findings if f.get("confidence") == "high")
        metrics.append({
            "name": "High Confidence Findings",
            "value": str(high_conf),
            "health": "good" if high_conf >= 2 else "info",
            "trend": "stable",
            "score": min(100, high_conf * 25) if findings else 0,
            "description": f"{high_conf} of {len(findings)} findings",
        })
        caution = readiness_brief.get("caution_columns", [])
        metrics.append({
            "name": "Caution Columns",
            "value": str(len(caution)),
            "health": "critical" if len(caution) > 3 else "concerning" if caution else "good",
            "trend": "stable",
            "score": max(0, 100 - len(caution) * 20),
            "description": f"{len(caution)} columns need attention",
        })
        return metrics

    def _narrate_enhanced_fallback(
        self,
        dataset: dict[str, Any],
        context: dict[str, str | list[str]],
        readiness_brief: dict[str, Any],
        findings: list[dict[str, Any]],
        template: str = "executive",
        active_blocks: list[str] | None = None,
        block_definitions: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Deterministic fallback for enhanced report when LLM is unavailable."""
        name = dataset.get("name", "the dataset")
        row_count = dataset.get("row_count", 0)
        col_count = dataset.get("column_count", 0)
        score = readiness_brief.get("readiness_score", "?")
        target = readiness_brief.get("domain_context", {}).get("target_variable", "the target variable")
        measures = readiness_brief.get("trustable_measures", [])
        caution = readiness_brief.get("caution_columns", [])

        key_findings = [f.get("finding", "") for f in findings if f.get("finding")]
        if not key_findings:
            key_findings = [
                f"The dataset contains {row_count} rows and {col_count} columns.",
                f"Data readiness score: {score}/10.",
            ]

        charts = [f["chart"] for f in findings if f.get("chart")]
        if not charts:
            charts = self.tools.starter_charts(get_flat_profile(dataset.get("profile", {})).get("columns", []))

        enhanced_findings = self._grounded_findings([], findings)

        # Build references
        references = []
        for i, f in enumerate(findings, 1):
            references.append({
                "id": f"q{i}",
                "type": "query",
                "description": f.get("finding", ""),
                "source": f.get("sql", ""),
            })

        resolved_blocks = block_definitions or self._resolve_block_definitions(template, active_blocks)
        block_order = [str(block.get("key")) for block in resolved_blocks if block.get("key")]
        block_labels = {
            str(block.get("key")): str(block.get("label") or str(block.get("key")).replace("_", " ").title())
            for block in resolved_blocks
            if block.get("key")
        }
        blocks_enabled = set(block_order)

        quality = "good" if score and score >= 7 else "moderate" if score and score >= 5 else "poor"

        result: dict[str, Any] = {
            "title": f"Report: {name}",
            "template": template,
            "report_type": context.get("report_type") or ("Custom Report" if template == "custom" else template),
            "block_order": block_order,
            "block_labels": block_labels,
            "context": context,
            "evidence_context": self._compact_dataset_evidence(dataset),
            "readiness": {
                "score": readiness_brief.get("readiness_score"),
                "label": readiness_brief.get("readiness_label"),
                "limitations": readiness_brief.get("data_limitations", []),
            },
        }

        if "central_theme" in blocks_enabled:
            result["central_theme"] = f"Analysis of {name} reveals {len(findings)} key findings with a data readiness score of {score}/10."

        if "executive_summary" in blocks_enabled:
            result["executive_summary"] = {
                "situation": [
                    f"Dataset contains {row_count} rows and {col_count} columns",
                    f"Primary target variable: {target}",
                    f"Trustable measures: {', '.join(measures[:5])}",
                ],
                "background": [
                    f"Data readiness score: {score}/10",
                    f"Caution columns: {', '.join(caution[:5])}" if caution else ["No caution columns identified"],
                ],
                "assessment": [
                    f"Overall data quality is {quality}",
                    f"{len(findings)} investigation queries executed successfully",
                ],
                "recommendation": [
                    "Review findings with domain experts",
                    "Validate assumptions before acting on recommendations",
                ],
            }

        if "key_metrics" in blocks_enabled:
            result["key_metrics"] = self._build_default_metrics(findings, readiness_brief)

        if "findings" in blocks_enabled:
            result["findings"] = enhanced_findings

        if "top_findings" in blocks_enabled:
            top = enhanced_findings[:5]
            result["top_findings"] = [
                {"title": f["title"], "severity": f["severity"], "evidence": f["evidence"]}
                for f in top
            ]

        if "data_story" in blocks_enabled:
            result["data_story"] = (
                f"The analysis of {name} reveals {len(findings)} key patterns. "
                f"The dataset has a readiness score of {score}/10, indicating {quality} data quality. "
                f"The primary target variable is {target}, and the investigation focused on understanding its distribution and relationships with other variables."
            )

        if "systems_detail" in blocks_enabled:
            result["systems_detail"] = [
                {"name": "Data Quality", "score": float(score) if score else 5.0, "findings": readiness_brief.get("data_limitations", [])[:3]},
                {"name": "Key Relationships", "score": 7.0, "findings": key_findings[:3]},
            ]

        if "action_plan" in blocks_enabled:
            result["action_plan"] = {
                "immediate": ["Review findings with domain experts", "Validate data quality assumptions"],
                "short_term": ["Run follow-up analysis on flagged segments", "Address caution columns"],
                "long_term": ["Establish data quality monitoring", "Build automated reporting pipeline"],
            }

        if "prognosis" in blocks_enabled:
            result["prognosis"] = {
                "current_state": f"Without action, the current data quality issues in {len(caution)} caution columns may lead to unreliable insights.",
                "with_recommendations": f"Addressing the {len(caution)} caution columns and validating findings with domain experts will improve insight reliability.",
            }

        if "charts" in blocks_enabled:
            result["charts"] = charts[:5]

        if "references" in blocks_enabled:
            result["references"] = references

        if "summary" in blocks_enabled:
            result["summary"] = (
                f"Analysis of {name} ({row_count} rows, {col_count} columns) reveals {len(findings)} key findings. "
                f"Data readiness score: {score}/10 ({quality})."
            )

        if "problem_statement" in blocks_enabled:
            result["problem_statement"] = (
                f"Investigate {name} to identify patterns, risks, and opportunities "
                f"for {context.get('audience', 'stakeholders')} focusing on {context.get('goal', 'key findings')}."
            )

        if "methodology" in blocks_enabled:
            result["methodology"] = (
                f"Analyzed {row_count} rows across {col_count} columns using automated profiling, "
                f"statistical testing, and {len(findings)} targeted SQL queries against an in-memory DuckDB instance."
            )

        if "conclusions" in blocks_enabled:
            result["conclusions"] = (
                f"The analysis confirms {len(findings)} patterns in the data with an overall quality rating of {quality}. "
                f"Key measures include {', '.join(measures[:3]) if measures else 'N/A'}."
            )

        if "overview" in blocks_enabled:
            result["overview"] = f"Dataset: {name} ({row_count} rows, {col_count} columns). Readiness: {score}/10."

        if "data_quality_assessment" in blocks_enabled:
            result["data_quality_assessment"] = {
                "overall_score": float(score) if score else 5.0,
                "strengths": [f"{len(measures)} trustable numeric measures identified"] if measures else [],
                "weaknesses": readiness_brief.get("data_limitations", []),
                "recommendations": ["Address caution columns", "Validate findings with domain experts"],
            }

        if "schema_analysis" in blocks_enabled:
            result["schema_analysis"] = {
                "total_columns": col_count,
                "column_breakdown": {},
                "key_relationships": [],
            }

        if "recommendations" in blocks_enabled:
            result["recommendations"] = [
                "Review findings with domain experts",
                "Validate data quality assumptions",
                "Consider running follow-up analysis on specific segments",
            ]

        for block in resolved_blocks:
            key = str(block.get("key") or "")
            if not key or key in result:
                continue
            label = block_labels.get(key, key.replace("_", " ").title())
            result[key] = [
                f"{label} should be reviewed with the data owner.",
                f"Use the findings from {name} to refine this section before approval.",
            ]

        result["sections"] = self._sections_from_result(result, resolved_blocks)
        return result

    def _narrate_with_llm(
        self,
        dataset: dict[str, Any],
        context: dict[str, Any],
        readiness_brief: dict[str, Any],
        findings: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        prompt = self._narration_prompt(dataset, context, readiness_brief, findings)
        try:
            run_output = self.agent.run(prompt, stream=False)
            content = str(getattr(run_output, "content", "") or "").strip()
            if not content:
                return None
            # Try to parse as JSON first
            parsed = self._parse_json_content(content)
            if parsed and isinstance(parsed, dict):
                return self._enrich_narrative(parsed, dataset, context, readiness_brief, findings)
        except Exception:
            pass
        return None

    def _narration_prompt(
        self,
        dataset: dict[str, Any],
        context: dict[str, str | list[str]],
        readiness_brief: dict[str, Any],
        findings: list[dict[str, Any]],
    ) -> str:
        findings_text = ""
        for i, f in enumerate(findings, 1):
            data_summary = str(f.get("data_preview", [])[:3])
            findings_text += (
                f"\nFinding {i}: {f.get('finding', '')}\n"
                f"  SQL: {f.get('sql', '')}\n"
                f"  Confidence: {f.get('confidence', 'medium')}\n"
                f"  Data preview: {data_summary}\n"
            )

        limitations = "\n".join(f"- {l}" for l in readiness_brief.get("data_limitations", []))

        return (
            "You are the ReportingSkill inside Data-Berge OS.\n"
            "Generate an executive report as JSON.\n\n"
            f"Dataset: {dataset.get('name', 'unknown')} ({dataset.get('row_count', 0)} rows, {dataset.get('column_count', 0)} columns)\n"
            f"Audience: {context.get('audience', 'Leadership team')}\n"
            f"Goal: {context.get('goal', 'Summarize key findings')}\n"
            f"Time horizon: {context.get('horizon', 'Next quarter')}\n"
            f"Tone: {context.get('tone', 'Strategic')}\n"
            f"Focus areas: {', '.join(context.get('focus_areas', []))}\n\n"
            f"Data Readiness: {readiness_brief.get('readiness_score', '?')}/10 ({readiness_brief.get('readiness_label', '?')})\n"
            f"Trustable measures: {', '.join(readiness_brief.get('trustable_measures', []))}\n"
            f"Caution columns: {', '.join(readiness_brief.get('caution_columns', []))}\n\n"
            f"Investigation findings:{findings_text}\n\n"
            f"Data limitations:\n{limitations}\n\n"
            "Generate a JSON report with these fields:\n"
            '- "title": Report title including the dataset name\n'
            '- "executive_summary": 2-3 paragraph executive summary citing specific numbers from findings\n'
            '- "key_findings": list of strings, each citing specific data evidence\n'
            '- "business_implications": list of strings interpreting what findings mean\n'
            '- "recommendations": list of strings with actionable next steps\n'
            '- "next_steps": list of strings for immediate follow-up actions\n\n'
            "Rules:\n"
            "- Cite specific numbers from the findings (e.g., 'Average income for approved loans is $85,000')\n"
            "- Do NOT make unsupported claims\n"
            "- Reference data limitations honestly\n"
            "- Write in a professional but accessible tone\n"
            "- Return JSON only, no markdown"
        )

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

    def _enrich_narrative(
        self,
        narrative: dict[str, Any],
        dataset: dict[str, Any],
        context: dict[str, str | list[str]],
        readiness_brief: dict[str, Any],
        findings: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Ensure all required fields exist and add charts from findings."""
        charts = [f["chart"] for f in findings if f.get("chart")]
        if not charts:
            charts = self.tools.starter_charts(get_flat_profile(dataset.get("profile", {})).get("columns", []))

        return {
            "title": narrative.get("title") or f"Executive Report: {dataset.get('name', 'Dataset')}",
            "executive_summary": narrative.get("executive_summary", ""),
            "key_findings": narrative.get("key_findings", []),
            "business_implications": narrative.get("business_implications", []),
            "recommendations": narrative.get("recommendations", []),
            "next_steps": narrative.get("next_steps", []),
            "charts": charts[:5],
            "context": context,
            "readiness": {
                "score": readiness_brief.get("readiness_score"),
                "label": readiness_brief.get("readiness_label"),
                "limitations": readiness_brief.get("data_limitations", []),
            },
        }

    def _narrate_fallback(
        self,
        dataset: dict[str, Any],
        context: dict[str, str | list[str]],
        readiness_brief: dict[str, Any],
        findings: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Deterministic fallback when LLM is unavailable."""
        name = dataset.get("name", "the dataset")
        row_count = dataset.get("row_count", 0)
        readiness = readiness_brief.get("readiness_score", "?")
        target = readiness_brief.get("domain_context", {}).get("target_variable", "the target variable")

        key_findings = [f.get("finding", "") for f in findings if f.get("finding")]
        if not key_findings:
            key_findings = [
                f"The dataset contains {row_count} rows and {dataset.get('column_count', 0)} columns.",
                f"Data readiness score: {readiness}/10.",
            ]

        charts = [f["chart"] for f in findings if f.get("chart")]
        if not charts:
            charts = self.tools.starter_charts(get_flat_profile(dataset.get("profile", {})).get("columns", []))

        return {
            "title": f"Executive Report: {name}",
            "executive_summary": (
                f"This report analyzes {name} ({row_count} rows) for {context.get('audience', 'Leadership team')} "
                f"with a focus on {context.get('goal', 'key findings')}. "
                f"The dataset has a readiness score of {readiness}/10. "
                f"The primary target variable is {target}."
            ),
            "key_findings": key_findings[:6],
            "business_implications": [
                "The findings above provide a data-driven foundation for decision-making.",
                "Data quality should be validated before using results for high-stakes decisions.",
            ],
            "recommendations": [
                "Review the key findings with domain experts.",
                "Validate assumptions before acting on recommendations.",
                "Consider running follow-up analysis on specific segments.",
            ],
            "next_steps": [
                "Review findings with stakeholders.",
                "Define follow-up analysis questions.",
                "Approve report for distribution.",
            ],
            "charts": charts[:5],
            "context": context,
            "readiness": {
                "score": readiness_brief.get("readiness_score"),
                "label": readiness_brief.get("readiness_label"),
                "limitations": readiness_brief.get("data_limitations", []),
            },
        }

    def _plan_with_llm(
        self,
        dataset: dict[str, Any],
        context: dict[str, Any],
        message: str,
        previous_plan: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        flat_profile = get_flat_profile(dataset.get("profile", {}))
        raw_profile = dataset.get("profile", {}) or {}
        columns = flat_profile.get("columns", [])
        column_summary = [
            {
                "name": col.get("name"),
                "type": col.get("semantic_type") or col.get("type") or col.get("dtype"),
                "dtype": col.get("dtype"),
                "missing_pct": col.get("missing_pct"),
                "unique_count": col.get("unique_count"),
                "description": col.get("description") or col.get("semantic_description"),
                "stats": {
                    key: col.get("stats", {}).get(key)
                    for key in ("min", "median", "mean", "max")
                    if isinstance(col.get("stats"), dict) and col.get("stats", {}).get(key) is not None
                },
                "top_values": [
                    {
                        "label": value.get("label"),
                        "count": value.get("count"),
                    }
                    for value in normalize_top_values(col.get("top_values"))[:5]
                    if isinstance(value, dict)
                ],
            }
            for col in columns[:20]
        ]
        relational = raw_profile.get("relational_schema", {}) or {}
        raw_source = relational.get("source") or raw_profile.get("source") or {}
        source_summary = {
            key: raw_source.get(key)
            for key in (
                "source_type",
                "dataset_id",
                "title",
                "description",
                "frequency",
                "data_source",
                "data_as_of",
                "last_updated",
                "sample_limit",
                "original_name",
            )
            if raw_source.get(key) not in (None, "", [])
        }
        sample_limit = source_summary.get("sample_limit")
        is_connector_sample = bool(
            source_summary.get("source_type") == "opendosm"
            and sample_limit not in (None, "", 0)
        )
        profile_summary = {
            "name": dataset.get("name"),
            "row_count": dataset.get("row_count") or flat_profile.get("row_count"),
            "column_count": dataset.get("column_count") or flat_profile.get("column_count"),
            "source": source_summary,
            "workspace_scope": {
                "loaded_rows": dataset.get("row_count") or flat_profile.get("row_count"),
                "is_connector_sample": is_connector_sample,
                "sample_limit": sample_limit,
                "interpretation": (
                    "Catalogue metadata describes the full source. Profile statistics and top values "
                    "describe only the rows loaded into this workspace."
                    if is_connector_sample
                    else "Profile statistics describe the current workspace dataset."
                ),
            },
            "metadata": flat_profile.get("metadata", {}),
            "quality_flags": flat_profile.get("quality_flags", [])[:6],
            "correlations": flat_profile.get("correlations", [])[:5],
            "columns": column_summary,
        }
        previous_plan_context = (
            "This is a revision. Preserve every unaffected choice and apply the requested changes.\n"
            f"Previous report plan JSON: {json.dumps(previous_plan, default=str, ensure_ascii=False)}\n\n"
            if previous_plan
            else "This is a new report plan.\n\n"
        )
        prompt = (
            "You are the report architect inside Data-Berge OS.\n"
            "Design the report plan only. Do not write any report findings, prose, metrics, or section content yet.\n"
            "Do not force a fixed template. Choose only the section blocks that fit the data and stakeholder need.\n\n"
            + previous_plan_context
            + f"User request: {message}\n"
            f"Dataset profile JSON: {json.dumps(profile_summary, default=str, ensure_ascii=False)}\n"
            f"Audience hint: {context.get('audience', 'General stakeholders')}\n"
            f"Goal hint: {context.get('goal', 'Create a useful report')}\n\n"
            "Return JSON only with this shape:\n"
            "{\n"
            '  "title": "short report title",\n'
            '  "report_type": "short label such as Quick Brief, Risk Memo, Executive Report, Technical Notes",\n'
            '  "audience": "audience label",\n'
            '  "goal": "one sentence goal",\n'
            '  "horizon": "time horizon or current",\n'
            '  "tone": "Board-ready|Strategic|Operational|Technical",\n'
            '  "focus_areas": ["short focus labels"],\n'
            '  "sections": [\n'
            '    {"key": "snake_case_unique_key", "label": "Natural Section Name", '
            '"purpose": "what decision this section supports and what it will contain", '
            '"kind": "summary|narrative|metrics|findings|chart|actions|comparison|table|key_value|bullets|references|callout", '
            '"data_fields": ["exact dataset field names needed as evidence"], '
            '"chart_intent": "specific chart purpose or null", "required": true, '
            '"presentation": {"variant": "hero|feature|standard|compact", "width": "full|half|third", '
            '"emphasis": "primary|supporting|context", "page_break_before": false}}\n'
            "  ]\n"
            "}\n\n"
            "Rules:\n"
            "- Sections are flexible. Add, remove, rename, and order sections based on the user request.\n"
            "- Infer the likely stakeholder need from the source context and available fields, but label any assumption.\n"
            "- For a quick brief, prefer two to four high-value sections rather than a standard report outline.\n"
            "- Use natural, data-specific section names. Avoid generic headings such as Executive Summary, "
            "Key Findings, Recommendations, or Next Steps unless the request truly requires them.\n"
            "- The section keys must be snake_case and unique.\n"
            "- data_fields may contain only exact names from Dataset profile JSON columns.\n"
            "- Explain each section's intended evidence and stakeholder purpose, not its eventual conclusions.\n"
            "- Use only the listed kind and presentation values. Never return HTML or CSS.\n"
            "- Return a concise plan the user can revise before expensive analysis begins.\n"
            "- Treat a connector sample as a sample; do not imply that sample row counts describe the full source.\n"
            "- Keep catalogue coverage separate from workspace evidence. If is_connector_sample is true, "
            "include a section purpose that makes the loaded-preview limitation explicit.\n"
            "- Do not claim longitudinal trends or full-population distribution findings from a connector sample.\n"
            "- Include a chart section only when the profile contains meaningful variation worth visualizing.\n"
            "- Do not include content, findings, recommendations, statistics, or conclusions in this plan.\n"
            "- Return JSON only, no markdown."
        )
        try:
            run_output = self.agent.run(prompt, stream=False)
            parsed = self._parse_json_content(str(getattr(run_output, "content", "") or ""))
        except Exception as exc:
            self._last_draft_error = f"Report model request failed: {str(exc)[:400]}"
            return None
        if not isinstance(parsed, dict):
            self._last_draft_error = "The report model returned an invalid JSON response."
            return None
        normalized = self._normalize_llm_plan(
            parsed,
            dataset,
            context,
            profile_summary,
            previous_plan=previous_plan,
            revision_instruction=message if previous_plan else None,
        )
        if normalized is None:
            self._last_draft_error = "The report model returned no usable report-plan sections."
        return normalized

    def _normalize_llm_plan(
        self,
        raw_plan: dict[str, Any],
        dataset: dict[str, Any],
        context: dict[str, Any],
        profile_summary: dict[str, Any],
        previous_plan: dict[str, Any] | None = None,
        revision_instruction: str | None = None,
    ) -> dict[str, Any] | None:
        raw_sections = raw_plan.get("sections")
        if not isinstance(raw_sections, list) or not raw_sections:
            return None

        allowed_kinds = {
            "summary", "narrative", "metrics", "findings", "chart", "actions",
            "comparison", "table", "key_value", "bullets", "references", "callout",
        }
        available_fields = {
            str(column.get("name")).casefold(): str(column.get("name"))
            for column in profile_summary.get("columns", [])
            if isinstance(column, dict) and column.get("name")
        }
        sections: list[dict[str, Any]] = []
        used_keys: set[str] = set()
        for index, raw in enumerate(raw_sections, 1):
            if not isinstance(raw, dict):
                continue
            label = str(raw.get("label") or raw.get("title") or f"Section {index}").strip()
            key = self._section_key(str(raw.get("key") or label), used_keys)
            if not key:
                continue
            used_keys.add(key)
            purpose = str(
                raw.get("purpose")
                or raw.get("description")
                or f"Define the evidence and decision supported by {label}."
            ).strip()
            kind_value = str(raw.get("kind") or "narrative").strip().lower()
            kind = kind_value if kind_value in allowed_kinds else "narrative"
            presentation = raw.get("presentation") if isinstance(raw.get("presentation"), dict) else None
            requested_fields = raw.get("data_fields") if isinstance(raw.get("data_fields"), list) else []
            data_fields = list(dict.fromkeys(
                available_fields[str(field).casefold()]
                for field in requested_fields
                if str(field).casefold() in available_fields
            ))
            chart_intent = str(raw.get("chart_intent") or "").strip() or None
            sections.append({
                "key": key,
                "label": label,
                "purpose": purpose,
                "kind": kind,
                "data_fields": data_fields,
                "chart_intent": chart_intent,
                "required": bool(raw.get("required", True)),
                "presentation": presentation,
            })

        if not sections:
            return None

        tone = str(raw_plan.get("tone") or context.get("tone") or "Strategic")
        if tone not in {"Board-ready", "Strategic", "Operational", "Technical"}:
            tone = "Strategic"
        focus_areas = raw_plan.get("focus_areas") if isinstance(raw_plan.get("focus_areas"), list) else context.get("focus_areas", [])
        audience = str(raw_plan.get("audience") or context.get("audience") or "General stakeholders")
        goal = str(raw_plan.get("goal") or context.get("goal") or "Create a useful report")
        horizon = str(raw_plan.get("horizon") or context.get("horizon") or "Current")
        report_type = str(raw_plan.get("report_type") or "Custom Report")
        normalized_focus = [str(item) for item in focus_areas if str(item).strip()] or ["quality", "risk"]

        result: dict[str, Any] = {
            "version": int(previous_plan.get("version", 0)) + 1 if previous_plan else 1,
            "plan_id": str(previous_plan.get("plan_id") or uuid.uuid4().hex) if previous_plan else uuid.uuid4().hex,
            "status": "proposed",
            "title": str(raw_plan.get("title") or f"{report_type}: {dataset.get('name', 'Dataset')}"),
            "template": "custom",
            "report_type": report_type,
            "audience": audience,
            "goal": goal,
            "horizon": horizon,
            "tone": tone,
            "focus_areas": normalized_focus,
            "dataset_scope": {
                "name": dataset.get("name"),
                "row_count": profile_summary.get("row_count"),
                "column_count": profile_summary.get("column_count"),
                **(profile_summary.get("workspace_scope") or {}),
            },
            "sections": sections,
            "revision_instruction": revision_instruction,
        }
        return result

    def _section_key(self, value: str, used_keys: set[str]) -> str:
        base = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
        if not base:
            base = "section"
        key = base[:48]
        suffix = 2
        while key in used_keys:
            key = f"{base[:42]}_{suffix}"
            suffix += 1
        return key

    def _starter_charts(self, columns: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return self.tools.starter_charts(columns)

    def answer(
        self,
        dataset: dict[str, Any],
        message: str,
        history: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        history = history or []
        normalized = re.sub(r"[^a-z0-9]+", " ", message.lower()).strip()
        tokens = set(normalized.split())
        previous_plan = self._find_plan_in_history(history)
        legacy_draft = self._find_draft_in_history(history)
        starts_new_report = any(
            phrase in normalized
            for phrase in {"new report", "another report", "different report", "create a report", "create report"}
        )
        confirmation_terms = {"confirm", "confirmation", "execute", "finalize", "approve", "publish", "submit"}
        is_confirmation = (
            bool(previous_plan or legacy_draft)
            and not starts_new_report
            and bool(tokens & confirmation_terms)
        )
        revision_terms = {"revise", "revision", "change", "rename", "remove", "add", "reorder"}
        is_revision = bool(previous_plan) and not starts_new_report and not is_confirmation and bool(
            tokens & revision_terms
        )

        if is_confirmation:
            if previous_plan:
                approved_plan = {**previous_plan, "status": "approved"}
                queued_request = self._report_request_from_plan(approved_plan)
                title = str(approved_plan.get("title") or "Custom Report")
                evidence = f"Confirmed report plan '{title}' with {len(approved_plan.get('sections') or [])} sections."
            else:
                queued_request = self._find_report_request_in_history(history)
                title = str((legacy_draft or {}).get("title") or "Report")
                evidence = f"Accepted legacy report draft '{title}' for generation."

            if queued_request:
                return {
                    "answer": (
                        f"The report plan '{title}' is confirmed and generation is starting. "
                        "You can follow the progress in the Executive Report page."
                    ),
                    "evidence": [evidence],
                    "sql": None,
                    "data": [],
                    "chart": None,
                    "confidence": 0.95,
                    "mode": "report",
                    "report_plan": None,
                    "report_draft": None,
                    "report_request": queued_request,
                    "action": "execute_requested",
                }

        context = self._context_from_plan(previous_plan) if is_revision and previous_plan else self._context_from_message(message)
        plan = self.plan(
            dataset,
            context,
            message,
            previous_plan=previous_plan if is_revision else None,
        )

        if plan.get("generation_source") != "llm" or not plan.get("sections"):
            if is_revision and previous_plan:
                return {
                    "answer": (
                        "The Reporter could not revise the plan, so the current plan is unchanged. "
                        "You can retry the revision or confirm the existing plan."
                    ),
                    "evidence": [str(plan.get("generation_warning") or "Report-plan revision failed.")],
                    "sql": None,
                    "data": [],
                    "chart": None,
                    "confidence": 0.35,
                    "mode": "report_plan",
                    "report_plan": previous_plan,
                    "report_draft": None,
                    "report_request": self._report_request_from_plan(previous_plan),
                    "action": "plan_revision_failed",
                }
            return {
                "answer": (
                    "The Reporter could not create an agent-designed report plan. "
                    "No fixed report template was substituted; please retry when the model is available."
                ),
                "evidence": [str(plan.get("generation_warning") or "Report-plan generation failed.")],
                "sql": None,
                "data": [],
                "chart": None,
                "confidence": 0.2,
                "mode": "report_plan",
                "report_plan": None,
                "report_draft": None,
                "report_request": None,
                "action": "plan_failed",
            }

        report_request = self._report_request_from_plan(plan)
        action = "plan_revised" if is_revision else "plan"
        answer = (
            "I've prepared your customized report draft structure. Executive Report can now open it for review before content generation."
            if is_revision
            else "I've prepared your customized report draft structure. Executive Report can now open it for review before content generation."
        )
        return {
            "answer": answer,
            "evidence": [
                f"The ReportAgent selected {len(plan['sections'])} custom sections for '{plan.get('audience')}'.",
                "Analysis and narrative generation will begin only after the user confirms this plan.",
            ],
            "sql": None,
            "data": [],
            "chart": None,
            "confidence": 0.86,
            "mode": "report_plan",
            "report_plan": plan,
            "report_draft": None,
            "report_request": report_request,
            "action": action,
        }

    def _report_request_from_plan(self, plan: dict[str, Any]) -> dict[str, Any]:
        sections = [section for section in (plan.get("sections") or []) if isinstance(section, dict)]
        custom_blocks = [
            {
                "key": str(section.get("key") or ""),
                "label": str(section.get("label") or ""),
                "description": str(section.get("purpose") or ""),
                "required": bool(section.get("required", True)),
                "kind": section.get("kind"),
                "presentation": section.get("presentation") if isinstance(section.get("presentation"), dict) else None,
                "data_fields": [str(field) for field in (section.get("data_fields") or [])],
                "chart_intent": str(section.get("chart_intent") or "") or None,
            }
            for section in sections
            if section.get("key") and section.get("label")
        ]
        return {
            "audience": str(plan.get("audience") or "General stakeholders"),
            "goal": str(plan.get("goal") or "Create a useful report"),
            "horizon": str(plan.get("horizon") or "Current"),
            "tone": str(plan.get("tone") or "Strategic"),
            "focus_areas": [str(item) for item in (plan.get("focus_areas") or [])],
            "template": "custom",
            "report_type": str(plan.get("report_type") or "Custom Report"),
            "blocks": [block["key"] for block in custom_blocks],
            "custom_blocks": custom_blocks,
            "approved_plan": plan,
        }

    def _find_plan_in_history(self, history: list[dict[str, Any]]) -> dict[str, Any] | None:
        for item in reversed(history):
            payload = item.get("payload", {}) or {}
            if payload.get("action") in {"queued", "saved"}:
                return None
            plan = payload.get("report_plan")
            if isinstance(plan, dict) and plan.get("sections"):
                return plan
        return None

    def _find_draft_in_history(self, history: list[dict[str, Any]]) -> dict[str, Any] | None:
        """Find the most recent report draft in conversation history."""
        for item in reversed(history):
            payload = item.get("payload", {}) or {}
            if payload.get("action") in {"queued", "saved"}:
                return None
            draft = payload.get("report_draft")
            if draft and isinstance(draft, dict):
                return draft
        return None

    def _find_report_request_in_history(self, history: list[dict[str, Any]]) -> dict[str, Any] | None:
        """Find report settings attached to the most recent plan or legacy draft."""
        for item in reversed(history):
            payload = item.get("payload", {}) or {}
            request = payload.get("report_request")
            plan = payload.get("report_plan")
            draft = payload.get("report_draft")
            if isinstance(request, dict) and (isinstance(plan, dict) or isinstance(draft, dict)):
                return request
        return None

    def _context_from_plan(self, plan: dict[str, Any]) -> dict[str, Any]:
        return {
            "audience": str(plan.get("audience") or "General stakeholders"),
            "goal": str(plan.get("goal") or "Create a useful report"),
            "horizon": str(plan.get("horizon") or "Current"),
            "tone": str(plan.get("tone") or "Strategic"),
            "focus_areas": [str(item) for item in (plan.get("focus_areas") or [])],
            "template": "custom",
            "blocks": [
                str(section.get("key"))
                for section in (plan.get("sections") or [])
                if isinstance(section, dict) and section.get("key")
            ],
        }

    def _context_from_message(self, message: str) -> dict[str, Any]:
        return {
            "audience": "General stakeholders",
            "goal": "Create a useful report plan based on the user request",
            "horizon": "Current",
            "tone": "Strategic",
            "focus_areas": ["quality", "risk"],
            "template": "custom",
            "blocks": [],
        }
