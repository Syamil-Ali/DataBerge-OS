from __future__ import annotations

import json
import re
from typing import Any

from data_berge_core.contracts import ArtifactStore, ProfileProvider, QueryRunner
from data_berge_core.report_document import has_usable_section_content, is_usable_chart
from data_berge_core.runtime import AgentFactory, AgentSpec, ToolkitFactory
from data_berge_core.skills.report_templates import get_template


class GovernanceSkill:
    spec = AgentSpec(
        name="GovernanceSkill",
        role="Check generated analytics artifacts before approval and refine report quality.",
        instructions=(
            "Review report artifacts for structural completeness, tone consistency, "
            "cross-block coherence, and factual accuracy. Flag unsupported claims, "
            "missing evidence, and whether human approval is required."
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
            include_tools=["list_artifacts"],
            profile_provider=profile_provider,
            query_runner=query_runner,
            artifact_store=artifact_store,
        )
        self.agent = agent_factory(self.spec, tools=[self.tools])

    def review(self, artifact_payload: dict, template: str = "executive") -> dict:
        warnings: list[str] = []
        checks: list[dict[str, Any]] = []

        tmpl = get_template(template)
        is_section_report = isinstance(artifact_payload.get("sections"), list) and bool(artifact_payload.get("sections"))
        is_enhanced = is_section_report or isinstance(artifact_payload.get("executive_summary"), dict) or template != "executive"

        if is_section_report:
            checks, warnings = self._review_sections(artifact_payload)
        elif is_enhanced:
            tmpl = tmpl or get_template("executive")
            checks, warnings = self._review_dynamic(artifact_payload, tmpl)
        else:
            checks, warnings = self._review_legacy(artifact_payload)

        passed_count = sum(1 for c in checks if c["passed"])
        total_count = len(checks)

        if passed_count == total_count:
            summary = f"All {total_count} governance checks passed. Ready for human approval."
        elif passed_count >= total_count - 2:
            summary = f"{passed_count}/{total_count} checks passed. Minor issues flagged for review."
        else:
            summary = f"Only {passed_count}/{total_count} checks passed. Significant gaps found."

        return {
            "requires_approval": True,
            "status": "reviewed",
            "warnings": warnings,
            "checks": checks,
            "passed": passed_count,
            "total": total_count,
            "summary": summary,
        }

    def review_with_quality_pass(self, artifact_payload: dict, template: str = "executive") -> tuple[dict, dict]:
        """Run structural review + LLM quality pass. Returns (refined_payload, governance)."""
        governance = self.review(artifact_payload, template)
        refined = artifact_payload
        if hasattr(self.agent, "run"):
            quality_result = self._quality_pass(artifact_payload, template)
            if quality_result:
                candidate = self._restore_report_contract(artifact_payload, quality_result)
                candidate_governance = self.review(candidate, template)
                if (
                    self._preserves_section_contract(artifact_payload, candidate)
                    and candidate_governance["passed"] >= governance["passed"]
                ):
                    refined = candidate
                    governance = candidate_governance
                    governance["quality_pass"] = True
                else:
                    governance["quality_pass"] = False
                    governance["quality_pass_warning"] = (
                        "The model quality pass was discarded because it changed or invalidated the report contract."
                    )
            else:
                governance["quality_pass"] = False
        else:
            governance["quality_pass"] = False

        return refined, governance

    def _restore_report_contract(self, original: dict, candidate: dict) -> dict:
        restored = dict(candidate)
        for key in (
            "template",
            "report_type",
            "block_order",
            "block_labels",
            "context",
            "evidence_context",
            "readiness",
            "custom_blocks",
            "generation_source",
            "generation_warning",
        ):
            if key in original:
                restored[key] = original[key]
        restored.pop("document", None)
        restored.pop("design", None)
        for section in restored.get("sections", []) if isinstance(restored.get("sections"), list) else []:
            if isinstance(section, dict) and section.get("key"):
                restored[str(section["key"])] = section.get("content")
        return restored

    def _preserves_section_contract(self, original: dict, candidate: dict) -> bool:
        original_sections = original.get("sections")
        candidate_sections = candidate.get("sections")
        if not isinstance(original_sections, list) or not original_sections:
            return True
        if not isinstance(candidate_sections, list) or len(candidate_sections) != len(original_sections):
            return False

        for expected, actual in zip(original_sections, candidate_sections):
            if not isinstance(expected, dict) or not isinstance(actual, dict):
                return False
            if str(expected.get("key") or "") != str(actual.get("key") or ""):
                return False
            expected_kind = self._section_kind(expected)
            actual_kind = self._section_kind(actual)
            if expected_kind != actual_kind:
                return False
            if not has_usable_section_content(expected_kind, actual.get("content")):
                return False
        return True

    def _section_kind(self, section: dict[str, Any]) -> str:
        presentation = section.get("presentation")
        if isinstance(presentation, dict) and presentation.get("kind"):
            return str(presentation["kind"])
        return str(section.get("kind") or "")

    def _quality_pass(self, payload: dict, template: str) -> dict | None:
        """LLM-based quality pass: review assembled report for coherence, tone, and structure."""
        prompt = self._quality_pass_prompt(payload, template)
        try:
            run_output = self.agent.run(prompt, stream=False)
            content = str(getattr(run_output, "content", "") or "").strip()
            if not content:
                return None
            parsed = self._parse_json_content(content)
            if parsed and isinstance(parsed, dict) and parsed.get("refined"):
                return parsed.get("payload", payload)
        except Exception:
            pass
        return None

    def _quality_pass_prompt(self, payload: dict, template: str) -> str:
        tmpl = get_template(template)
        if isinstance(payload.get("sections"), list) and payload.get("sections"):
            block_labels = [str(section.get("label") or section.get("key")) for section in payload.get("sections", []) if isinstance(section, dict)]
            report_name = str(payload.get("report_type") or "Custom Report")
        else:
            tmpl = tmpl or get_template("executive")
            block_labels = [b["label"] for b in tmpl["blocks"]]
            report_name = tmpl["name"]

        report_text = json.dumps(payload, indent=2, default=str)
        if len(report_text) > 8000:
            report_text = report_text[:8000] + "\n... (truncated)"

        return (
            f"You are the GovernanceSkill quality reviewer for Data-Berge OS.\n"
            f"Review this {report_name} report for quality.\n\n"
            f"Template blocks: {', '.join(block_labels)}\n\n"
            f"Report payload:\n{report_text}\n\n"
            "Check for:\n"
            "1. Tone consistency — does the writing style match across all blocks?\n"
            "2. Cross-block coherence — do findings support the summary claims? Do action items relate to findings?\n"
            "3. Structural completeness — are all requested blocks present with meaningful content?\n"
            "4. Factual grounding — are specific numbers cited? Are claims supported by data?\n"
            "5. Professional quality — is the writing clear, concise, and appropriate for the audience?\n\n"
            "Do not call tools and do not change artifact status. Only review the payload and return JSON.\n\n"
            "If the report passes all quality checks, return:\n"
            '{"refined": false}\n\n'
            "If you can improve the report, return the refined version:\n"
            '{"refined": true, "payload": {<the improved report JSON>}}\n\n'
            "Only make improvements that are clearly needed. Do not rewrite sections that are already good.\n"
            "Preserve every section key, section order, presentation kind, chart object, evidence_context, readiness field, and generation metadata exactly.\n"
            "Never replace a chart object with prose or invent new chart data.\n"
            "Return JSON only, no markdown."
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

    def _review_dynamic(self, payload: dict, tmpl: dict) -> tuple[list[dict[str, Any]], list[str]]:
        """Dynamic review based on which blocks are present in the payload."""
        warnings: list[str] = []
        checks: list[dict[str, Any]] = []

        for block in tmpl["blocks"]:
            key = block["key"]
            label = block["label"]
            required = block.get("required", False)

            if key not in payload:
                if required:
                    checks.append({"check": f"{label} present", "passed": False})
                    warnings.append(f"Required block '{label}' is missing.")
                continue

            value = payload[key]

            if key == "executive_summary":
                if isinstance(value, dict):
                    for section in ("situation", "background", "assessment", "recommendation"):
                        items = value.get(section, [])
                        has = bool(items) and isinstance(items, list) and len(items) > 0
                        checks.append({"check": f"SBAR: {section.title()} present", "passed": has})
                        if not has:
                            warnings.append(f"SBAR {section} section is empty.")
                else:
                    checks.append({"check": f"{label} present", "passed": bool(value)})

            elif key == "key_metrics":
                has_metrics = bool(value) and isinstance(value, list)
                checks.append({"check": f"{label} present", "passed": has_metrics})
                if not has_metrics:
                    warnings.append("No key metrics were generated.")

            elif key == "findings":
                has_findings = bool(value) and isinstance(value, list)
                checks.append({"check": f"{label} present", "passed": has_findings})
                if not has_findings:
                    warnings.append("No findings were generated.")
                elif has_findings:
                    has_severity = all(isinstance(f, dict) and f.get("severity") for f in value)
                    checks.append({"check": "Findings have severity levels", "passed": has_severity})
                    if not has_severity:
                        warnings.append("Some findings lack severity levels.")

            elif key == "top_findings":
                has_top = bool(value) and isinstance(value, list)
                checks.append({"check": f"{label} present", "passed": has_top})
                if not has_top:
                    warnings.append("No top findings were generated.")

            elif key == "charts":
                has_charts = (
                    isinstance(value, list)
                    and bool(value)
                    and all(is_usable_chart(chart) for chart in value)
                )
                checks.append({"check": f"{label} included", "passed": has_charts})
                if not has_charts:
                    warnings.append("No charts were included.")

            elif key == "data_quality_assessment":
                if isinstance(value, dict):
                    has_score = "overall_score" in value
                    checks.append({"check": f"{label} has score", "passed": has_score})
                    if not has_score:
                        warnings.append("Data quality assessment lacks overall score.")
                else:
                    checks.append({"check": f"{label} present", "passed": bool(value)})

            elif key == "schema_analysis":
                if isinstance(value, dict):
                    has_cols = "total_columns" in value
                    checks.append({"check": f"{label} has column count", "passed": has_cols})
                else:
                    checks.append({"check": f"{label} present", "passed": bool(value)})

            elif key == "action_plan":
                if isinstance(value, dict):
                    has_plan = bool(value.get("immediate")) or bool(value.get("short_term"))
                    checks.append({"check": f"{label} present", "passed": has_plan})
                    if not has_plan:
                        warnings.append("Action plan is empty.")
                else:
                    checks.append({"check": f"{label} present", "passed": bool(value)})

            elif key == "prognosis":
                if isinstance(value, dict):
                    has_prog = bool(value.get("current_state")) or bool(value.get("with_recommendations"))
                    checks.append({"check": f"{label} present", "passed": has_prog})
                    if not has_prog:
                        warnings.append("Prognosis is empty.")
                else:
                    checks.append({"check": f"{label} present", "passed": bool(value)})

            elif key in ("central_theme", "summary", "problem_statement", "methodology",
                         "conclusions", "overview", "data_story", "recommendations"):
                has_content = bool(value) and (isinstance(value, str) and len(value.strip()) > 10 or isinstance(value, list))
                checks.append({"check": f"{label} present", "passed": has_content})
                if not has_content:
                    warnings.append(f"{label} is missing or too short.")

            elif key == "references":
                has_refs = bool(value) and isinstance(value, list)
                checks.append({"check": f"{label} present", "passed": has_refs})

            else:
                checks.append({"check": f"{label} present", "passed": bool(value)})

        readiness = payload.get("readiness", {})
        if readiness:
            checks.append({"check": "Data readiness assessment included", "passed": True})
            limitations = readiness.get("limitations", []) if isinstance(readiness, dict) else []
            checks.append({"check": "Data limitations documented", "passed": bool(limitations)})
            if not limitations:
                warnings.append("Data limitations were not documented.")
        else:
            checks.append({"check": "Data readiness assessment included", "passed": False})
            warnings.append("Data readiness assessment is missing.")

        return checks, warnings

    def _review_sections(self, payload: dict) -> tuple[list[dict[str, Any]], list[str]]:
        warnings: list[str] = []
        checks: list[dict[str, Any]] = []
        sections = payload.get("sections", [])
        has_sections = isinstance(sections, list) and bool(sections)
        checks.append({"check": "Report sections present", "passed": has_sections})
        if not has_sections:
            warnings.append("No report sections were generated.")
            return checks, warnings

        for section in sections:
            if not isinstance(section, dict):
                checks.append({"check": "Section has valid shape", "passed": False})
                warnings.append("A section has an invalid shape.")
                continue
            label = str(section.get("label") or section.get("key") or "Section")
            content = section.get("content")
            kind = self._section_kind(section)
            has_content = has_usable_section_content(kind, content)
            checks.append({"check": f"{label} present", "passed": has_content})
            if not has_content:
                if kind == "chart":
                    warnings.append(f"{label} does not contain a renderable chart backed by data.")
                else:
                    warnings.append(f"{label} is missing, too short, or has the wrong content shape.")

        readiness = payload.get("readiness", {})
        checks.append({"check": "Data readiness assessment included", "passed": bool(readiness)})
        if not readiness:
            warnings.append("Data readiness assessment is missing.")

        limitations = readiness.get("limitations", []) if isinstance(readiness, dict) else []
        checks.append({"check": "Data limitations documented", "passed": bool(limitations)})
        if not limitations:
            warnings.append("Data limitations were not documented.")

        return checks, warnings

    def _review_legacy(self, payload: dict) -> tuple[list[dict[str, Any]], list[str]]:
        """Review legacy flat-format report."""
        warnings: list[str] = []
        checks: list[dict[str, Any]] = []

        has_summary = bool(payload.get("executive_summary"))
        checks.append({"check": "Executive summary present", "passed": has_summary})
        if not has_summary:
            warnings.append("Executive summary is missing.")

        findings = payload.get("key_findings", [])
        has_findings = bool(findings)
        checks.append({"check": "Key findings present", "passed": has_findings})
        if not has_findings:
            warnings.append("No key findings were generated.")

        if findings:
            substantive = [f for f in findings if isinstance(f, str) and len(f.strip()) > 10]
            all_substantive = len(substantive) == len(findings)
            checks.append({"check": "Findings are substantive", "passed": all_substantive})
            if not all_substantive:
                warnings.append("Some findings appear too short or empty.")

        implications = payload.get("business_implications", [])
        checks.append({"check": "Business implications present", "passed": bool(implications)})
        if not implications:
            warnings.append("No business implications were generated.")

        recommendations = payload.get("recommendations", [])
        checks.append({"check": "Recommendations present", "passed": bool(recommendations)})
        if not recommendations:
            warnings.append("No recommendations were generated.")

        charts = payload.get("charts", [])
        checks.append({"check": "Charts included", "passed": bool(charts)})
        if not charts:
            warnings.append("No charts were included.")

        readiness = payload.get("readiness", {})
        checks.append({"check": "Data readiness assessment included", "passed": bool(readiness)})
        if not readiness:
            warnings.append("Data readiness assessment is missing.")

        limitations = readiness.get("limitations", []) if isinstance(readiness, dict) else []
        checks.append({"check": "Data limitations documented", "passed": bool(limitations)})
        if not limitations:
            warnings.append("Data limitations were not documented.")

        return checks, warnings
