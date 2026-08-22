from __future__ import annotations

from time import perf_counter
import shutil

from app.agents import AnalyticsTeam
from app.services.llm_observability import log_profile_run
from app.storage import database
from app.storage.object_store import get_object_store, persist_file
from app import settings
from app.services.files import directory_size


def run_upload_workflow(project_id: str, file_obj, filename: str, user_id: str | None = None) -> dict:
    team = AnalyticsTeam(user_id=user_id)
    team.intake.validate_filename(filename)
    ingested = team.data_engineer.ingest_uploaded_file(file_obj, filename)
    df = ingested.dataframe
    if df.empty:
        raise ValueError("Dataset is empty.")

    profile_started = perf_counter()
    table_profile = team.data_analyst.profile_dataset(df, column_descriptions=ingested.column_descriptions)
    table_profile["source"] = ingested.source_metadata()
    table_profile["data_engineering"] = team.data_engineer.prepare(df, table_profile)
    profile_elapsed_ms = int((perf_counter() - profile_started) * 1000)

    # Store in the unified tables format (same shape as multi-table schemas)
    profile = {
        "tables": {ingested.name: table_profile},
        "relationships": [],
        "description_map": {},
    }

    storage_bytes = directory_size(ingested.source_path.parent)
    if user_id and not database.reserve_user_storage(user_id, storage_bytes):
        shutil.rmtree(ingested.source_path.parent, ignore_errors=True)
        raise ValueError("Storage limit exceeded. Delete some datasets before uploading another file.")

    source_uri = str(ingested.source_path)
    working_uri = str(ingested.working_path)
    if user_id:
        try:
            source_uri = persist_file(
                ingested.source_path,
                user_id=user_id,
                namespace=ingested.dataset_id,
                name=f"source-{ingested.source_path.name}",
            )
            working_uri = persist_file(
                ingested.working_path,
                user_id=user_id,
                namespace=ingested.dataset_id,
                name=f"working-{ingested.working_path.name}",
            )
        except Exception:
            database.update_user_storage(user_id, -storage_bytes)
            get_object_store().delete_namespace(user_id=user_id, namespace=ingested.dataset_id)
            shutil.rmtree(ingested.source_path.parent, ignore_errors=True)
            raise

    table_profile["source"]["source_path"] = source_uri
    lineage = table_profile["source"].get("lineage") or {}
    lineage["read_path"] = source_uri
    lineage["working_path"] = working_uri
    table_profile["source"]["lineage"] = lineage

    record = {
        "id": ingested.dataset_id,
        "project_id": project_id,
        "name": ingested.name,
        "original_filename": filename,
        "file_type": ingested.file_type,
        "source_path": source_uri,
        "working_path": working_uri,
        "row_count": int(len(df)),
        "column_count": int(df.shape[1]),
        "status": "profiled",
        "profile": profile,
    }
    try:
        if user_id:
            dataset = database.create_dataset_for_user(user_id, record)
        else:
            dataset = database.create_dataset(record)

        starter_payload = {
            "title": f"Starter Dashboard: {ingested.name}",
            "summary": "Auto-generated draft dashboard from the upload workflow.",
            "charts": team.report.tools.starter_charts(table_profile.get("columns", [])),
        }
        team.set_active_context(project_id, ingested.dataset_id)
        team.report.tools.create_dashboard_artifact(
            project_id,
            ingested.dataset_id,
            starter_payload["title"],
            starter_payload["summary"],
            starter_payload["charts"],
        )
        log_profile_run(
            dataset_id=ingested.dataset_id,
            project_id=project_id,
            filename=filename,
            file_type=ingested.file_type,
            row_count=int(len(df)),
            column_count=int(df.shape[1]),
            profile=table_profile,
            elapsed_ms=profile_elapsed_ms,
            user_id=user_id,
        )
        if settings.OBJECT_STORAGE_BACKEND == "s3":
            shutil.rmtree(ingested.source_path.parent, ignore_errors=True)
        return dataset
    except Exception:
        if user_id:
            if database.get_dataset_for_user(user_id, project_id, ingested.dataset_id):
                database.delete_dataset_for_user(user_id, project_id, ingested.dataset_id)
            database.update_user_storage(user_id, -storage_bytes)
            get_object_store().delete_namespace(user_id=user_id, namespace=ingested.dataset_id)
        shutil.rmtree(ingested.source_path.parent, ignore_errors=True)
        raise
