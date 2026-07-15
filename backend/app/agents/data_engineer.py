from __future__ import annotations

from typing import Any

import pandas as pd

from app.adapters import AnalyticsToolkit, LocalProfileProvider
from app.agents.base import AgentSpec, make_agno_agent
from app.services.connectors import FileConnector, IngestedDataset
from app.services.data_engineering import build_data_engineering_contract
from app.services.files import load_dataframe
from data_berge_core.contracts import ProfileProvider
from data_berge_core.skills import EngineeringSkill


class DataEngineerAgent:
    """Thin role wrapper around the reusable engineering skill."""

    spec = AgentSpec(
        name="DataEngineerAgent",
        role="Prepare uploaded datasets for trustworthy analytics work.",
        instructions=(
            "Lead when the conversation shifts to cleaning, typing, schema trust, joins, or data readiness, "
            "using the shared engineering skill as the source of engineering reasoning. Do not lead simple "
            "row counts, field counts, column-name inventory, calculations, or general dataset summaries."
        ),
    )

    def __init__(self, profile_provider: ProfileProvider | None = None) -> None:
        self.profile_provider = profile_provider or LocalProfileProvider()
        self.file_connector = FileConnector()
        self.engineering_skill = EngineeringSkill(
            toolkit_factory=AnalyticsToolkit,
            agent_factory=make_agno_agent,
            profile_provider=self.profile_provider,
            load_dataframe_fn=load_dataframe,
            prepare_contract_fn=build_data_engineering_contract,
        )
        self.tools = self.engineering_skill.tools
        self.agent = self.engineering_skill.agent

    def ingest_uploaded_file(self, file_obj, filename: str) -> IngestedDataset:
        return self.file_connector.ingest_upload(file_obj, filename)

    def prepare(self, df: pd.DataFrame, profile: dict[str, Any]) -> dict:
        return self.engineering_skill.prepare(df, profile)

    def assess_for_report(self, dataset: dict[str, Any]) -> dict[str, Any]:
        return self.engineering_skill.assess_for_report(dataset)

    def answer(
        self,
        message: str,
        dataset: dict[str, Any],
        history: list[dict[str, Any]] | None = None,
        shared_state: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        response = self.engineering_skill.answer(message, dataset, history or [], shared_state=shared_state)
        response["active_skill"] = "engineering"
        return response

    def should_lead(
        self,
        message: str,
        dataset: dict[str, Any],
        previous_lead: str | None = None,
        history: list[dict[str, Any]] | None = None,
    ) -> bool:
        return self.engineering_skill.should_lead(
            message,
            dataset,
            previous_lead=previous_lead,
            history=history or [],
        )
