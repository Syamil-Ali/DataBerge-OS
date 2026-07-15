from __future__ import annotations

from typing import Any, Protocol

from data_berge_core.contracts.dataset import DatasetContext


class ProfileProvider(Protocol):
    def get_dataset_context(self, dataset_id: str, project_id: str | None = None) -> DatasetContext | None: ...

    def get_profile(self, dataset_id: str, project_id: str | None = None) -> dict[str, Any] | None: ...

    def save_profile(self, dataset_context: DatasetContext, profile: dict[str, Any]) -> DatasetContext | None: ...

    def project_exists(self, project_id: str) -> bool: ...


class QueryRunner(Protocol):
    def build_safe_query(self, dataset_context: DatasetContext, message: str) -> tuple[str | None, str]: ...

    def run_sql(
        self,
        dataset_context: DatasetContext,
        sql: str,
        limit: int = 100,
    ) -> list[dict[str, Any]]: ...


class ArtifactStore(Protocol):
    def create_artifact(
        self,
        project_id: str,
        kind: str,
        title: str,
        payload: dict[str, Any],
        dataset_id: str | None = None,
        status: str = "draft",
    ) -> dict[str, Any]: ...

    def list_artifacts(self, project_id: str, dataset_id: str | None = None) -> list[dict[str, Any]]: ...
