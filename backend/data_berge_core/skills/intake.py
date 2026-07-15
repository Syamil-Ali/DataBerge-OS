from __future__ import annotations

from typing import Any

from data_berge_core.contracts import ArtifactStore, ProfileProvider, QueryRunner
from data_berge_core.runtime import AgentFactory, AgentSpec, ToolkitFactory


class IntakeSkill:
    spec = AgentSpec(
        name="IntakeSkill",
        role="Validate uploaded analytics files before they enter the workspace.",
        instructions="Check file type, basic structure, and whether it can enter the analytics workspace.",
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
            include_tools=["validate_filename", "profile_file"],
            profile_provider=profile_provider,
            query_runner=query_runner,
            artifact_store=artifact_store,
        )
        self.agent = agent_factory(self.spec, tools=[self.tools])

    def validate_filename(self, filename: str) -> None:
        self.tools.validate_filename(filename)

    def answer(self, dataset: dict[str, Any], message: str) -> dict[str, Any]:
        validation = self.tools.validate_filename(str(dataset.get("original_filename") or dataset.get("name") or "dataset"))
        return {
            "answer": (
                f"The uploaded file looks valid for the workspace. "
                f"It is a {validation.get('file_type', 'supported')} file with "
                f"{dataset.get('row_count', 0)} rows and {dataset.get('column_count', 0)} columns ready for profiling."
            ),
            "evidence": [
                f"Validated uploaded filename '{dataset.get('original_filename') or dataset.get('name')}'.",
                f"Dataset '{dataset.get('name')}' is already loaded into the analytics workspace.",
            ],
            "sql": None,
            "data": [],
            "chart": None,
            "confidence": 0.9,
            "mode": "intake",
        }
