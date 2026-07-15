from __future__ import annotations

from typing import Any

from app.services.query_engine import AmbiguousQueryError, build_sql, execute_sql
from app.storage import database
from data_berge_core.contracts.dataset import DatasetContext


def _normalize_identifier(value: str) -> str:
    return value.replace("-", "_").replace(" ", "_").lower()


def _find_schema_containing_table(
    dataset_id: str,
    project_id: str,
    user_id: str | None,
) -> dict[str, Any] | None:
    """Find a relational schema containing a table matching a virtual dataset ID."""
    schemas = database.list_relational_schemas(project_id, user_id=user_id)
    if not schemas:
        schemas = database.list_relational_schemas(project_id=None, user_id=user_id)

    schemas_by_table = {
        _normalize_identifier(table_name): schema
        for schema in schemas
        for table_name in ((schema.get("schema") or {}).get("tables") or {})
    }
    return schemas_by_table.get(_normalize_identifier(dataset_id))


class LocalProfileProvider:
    """Provide user-scoped dataset profiles from local database records."""

    def __init__(self, user_id: str | None = None) -> None:
        self.user_id = user_id

    def get_dataset_context(self, dataset_id: str, project_id: str | None = None) -> DatasetContext | None:
        """Return an accessible dataset or relational-table context for an ID."""
        dataset = database.get_dataset(dataset_id)
        if dataset:
            if project_id and str(dataset.get("project_id")) != project_id:
                return None
            if self.user_id and dataset.get("user_id") != self.user_id:
                return None
            return DatasetContext.from_record(dataset)

        schema = database.get_relational_schema(dataset_id)
        if schema:
            if self.user_id and schema.get("user_id") != self.user_id:
                return None
            return self._schema_to_context(schema, project_id)

        if project_id:
            matching_schema = _find_schema_containing_table(dataset_id, project_id, self.user_id)
            if matching_schema:
                return self._schema_to_context(
                    matching_schema,
                    project_id or matching_schema.get("project_id"),
                )

        return None

    def _schema_to_context(self, schema: dict, project_id: str | None = None) -> DatasetContext:
        from app.workflows.chat_workflow import _schema_to_virtual_dataset
        virtual = _schema_to_virtual_dataset(schema)
        if project_id:
            virtual["project_id"] = project_id
        return DatasetContext.from_record(virtual)

    def get_profile(self, dataset_id: str, project_id: str | None = None) -> dict[str, Any] | None:
        context = self.get_dataset_context(dataset_id, project_id=project_id)
        return context.profile if context else None

    def save_profile(self, dataset_context: DatasetContext, profile: dict[str, Any]) -> DatasetContext | None:
        persisted = database.update_dataset_profile(dataset_context.dataset_id, profile)
        if not persisted:
            return None
        return DatasetContext.from_record(persisted)

    def project_exists(self, project_id: str) -> bool:
        if self.user_id:
            return bool(database.get_project_for_user(self.user_id, project_id))
        return bool(database.get_project(project_id))


class LocalQueryRunner:
    """Build and execute read-only queries against local dataset files."""

    def build_safe_query(self, dataset_context: DatasetContext, message: str) -> tuple[str | None, str]:
        """Translate a user message into validated SQL and an evidence note."""
        try:
            sql, evidence_note = build_sql(message, dataset_context.profile)
        except AmbiguousQueryError as exc:
            return None, str(exc)
        return sql, evidence_note

    def run_sql(
        self,
        dataset_context: DatasetContext,
        sql: str,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Execute validated SQL against a dataset, capped at the requested limit."""
        return execute_sql(dataset_context.working_path, sql, limit=limit)


class LocalArtifactStore:
    """Persist and retrieve locally stored artifacts within an optional user scope."""

    def __init__(self, profile_provider: LocalProfileProvider | None = None, user_id: str | None = None) -> None:
        self.profile_provider = profile_provider or LocalProfileProvider()
        self.user_id = user_id or self.profile_provider.user_id

    def create_artifact(
        self,
        project_id: str,
        kind: str,
        title: str,
        payload: dict[str, Any],
        dataset_id: str | None = None,
        status: str = "draft",
    ) -> dict[str, Any]:
        """Create an artifact record and return its persisted representation."""
        return database.create_artifact(
            project_id,
            kind,
            title,
            payload,
            dataset_id=dataset_id,
            status=status,
            user_id=self.user_id,
        )

    def list_artifacts(self, project_id: str, dataset_id: str | None = None) -> list[dict[str, Any]]:
        if self.user_id:
            return database.list_artifacts_for_user(self.user_id, project_id, dataset_id)
        return database.list_artifacts(project_id, dataset_id)
