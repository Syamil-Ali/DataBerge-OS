from __future__ import annotations

from app.adapters import AnalyticsToolkit, LocalArtifactStore, LocalProfileProvider, LocalQueryRunner
from app.agents.coordinator import TeamCoordinator
from app.agents.data_analyst import DataAnalystAgent
from app.agents.data_engineer import DataEngineerAgent
from app.agents.report import ReportAgent
from app.agents.base import make_agno_agent
from data_berge_core.skills import GovernanceSkill, IntakeSkill, VisualizationSkill


class AnalyticsTeam:
    """Coordinating facade for the analytics OS agent layer."""

    def __init__(self, user_id: str | None = None) -> None:
        self.profile_provider = LocalProfileProvider(user_id=user_id)
        self.query_runner = LocalQueryRunner()
        self.artifact_store = LocalArtifactStore(self.profile_provider, user_id=user_id)
        self.toolkit_factory = AnalyticsToolkit
        self.agent_factory = make_agno_agent

        self.intake = IntakeSkill(
            self.toolkit_factory, self.agent_factory, self.profile_provider, self.query_runner, self.artifact_store
        )
        self.data_engineer = DataEngineerAgent(self.profile_provider)
        self.data_analyst = DataAnalystAgent(self.profile_provider, self.query_runner, self.artifact_store)
        self.report_agent = ReportAgent(self.profile_provider, self.query_runner, self.artifact_store)
        self.query = self.data_analyst.query_skill
        self.viz = VisualizationSkill(
            self.toolkit_factory, self.agent_factory, self.profile_provider, self.query_runner, self.artifact_store
        )
        self.report = self.report_agent
        self.governance = GovernanceSkill(
            self.toolkit_factory, self.agent_factory, self.profile_provider, self.query_runner, self.artifact_store
        )
        self.coordinator = TeamCoordinator(self.data_analyst, self.data_engineer, self.report_agent)
        self.team = self.coordinator.manager_agent

    def set_active_context(self, project_id: str, dataset_id: str | None = None) -> None:
        """Lock toolkit calls to the request's real project/dataset IDs.

        LLM tool calls can include invented IDs. The app route already knows the
        trusted active context, so every toolkit should use that instead.
        """
        seen: set[int] = set()
        for candidate in (
            getattr(self.intake, "tools", None),
            getattr(self.data_analyst, "tools", None),
            getattr(getattr(self.data_analyst, "intake_skill", None), "tools", None),
            getattr(getattr(self.data_analyst, "profiler_skill", None), "tools", None),
            getattr(getattr(self.data_analyst, "query_skill", None), "tools", None),
            getattr(getattr(self.data_analyst, "viz_skill", None), "tools", None),
            getattr(getattr(self.data_analyst, "report_skill", None), "tools", None),
            getattr(self.report_agent, "tools", None),
            getattr(self.query, "tools", None),
            getattr(self.viz, "tools", None),
            getattr(self.report, "tools", None),
            getattr(self.governance, "tools", None),
        ):
            if candidate is None or id(candidate) in seen:
                continue
            seen.add(id(candidate))
            setter = getattr(candidate, "set_active_context", None)
            if callable(setter):
                setter(project_id, dataset_id)
