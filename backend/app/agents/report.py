from __future__ import annotations

from typing import Any

from app.adapters.analytics_toolkit import AnalyticsToolkit
from app.agents.base import AgentSpec, make_agno_agent
from data_berge_core.contracts import ArtifactStore, ProfileProvider, QueryRunner
from data_berge_core.report_document import compose_report_document
from data_berge_core.skills import ReportingSkill


class ReportAgent:
    """Role agent that turns verified analysis into a publishable report document."""

    spec = AgentSpec(
        name="ReportAgent",
        role="Compose evidence-backed analytics reports for specific audiences and decisions.",
        instructions=(
            "Own report hierarchy, narrative flow, section selection, chart placement, and presentation intent. "
            "Use only the constrained report section kinds and presentation tokens supplied by Data-Berge OS. "
            "Never generate HTML or CSS. Preserve analyst evidence and data-engineering limitations."
        ),
    )

    def __init__(
        self,
        profile_provider: ProfileProvider | None = None,
        query_runner: QueryRunner | None = None,
        artifact_store: ArtifactStore | None = None,
    ) -> None:
        self.report_skill = ReportingSkill(
            AnalyticsToolkit,
            make_agno_agent,
            profile_provider,
            query_runner,
            artifact_store,
        )
        self.tools = self.report_skill.tools
        self.agent = make_agno_agent(self.spec, tools=[self.tools])

    def draft(self, dataset: dict[str, Any], context: dict[str, Any], message: str = "") -> dict[str, Any]:
        return self.report_skill.plan(dataset, context, message)

    def narrate(
        self,
        dataset: dict[str, Any],
        context: dict[str, Any],
        readiness_brief: dict[str, Any],
        findings: list[dict[str, Any]],
    ) -> dict[str, Any]:
        report = self.report_skill.narrate(dataset, context, readiness_brief, findings)
        return self.compose(report, template=str(report.get("template") or "executive"))

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
        report = self.report_skill.narrate_enhanced(
            dataset,
            context,
            readiness_brief,
            findings,
            template=template,
            blocks=blocks,
            block_definitions=block_definitions,
        )
        return self.compose(report, template=template, block_definitions=block_definitions)

    def answer(
        self,
        dataset: dict[str, Any],
        message: str,
        history: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        response = self.report_skill.answer(dataset, message, history)
        draft = response.get("report_draft")
        if isinstance(draft, dict):
            composed = self.compose(
                draft,
                template=str(draft.get("template") or "custom"),
                block_definitions=draft.get("custom_blocks"),
            )
            response["report_draft"] = composed
            request = response.get("report_request")
            if isinstance(request, dict):
                request["custom_blocks"] = composed.get("custom_blocks") or request.get("custom_blocks")
        response["active_skill"] = "reporting"
        return response

    def compose(
        self,
        report: dict[str, Any],
        template: str | None = None,
        block_definitions: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        return compose_report_document(report, template=template, block_definitions=block_definitions)
