from __future__ import annotations

from time import perf_counter

from app.agents import AnalyticsTeam
from app.services.llm_observability import log_profile_run
from app.storage import database


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

    record = {
        "id": ingested.dataset_id,
        "project_id": project_id,
        "name": ingested.name,
        "original_filename": filename,
        "file_type": ingested.file_type,
        "source_path": str(ingested.source_path),
        "working_path": str(ingested.working_path),
        "row_count": int(len(df)),
        "column_count": int(df.shape[1]),
        "status": "profiled",
        "profile": profile,
    }
    if user_id:
        dataset = database.create_dataset_for_user(user_id, record)
    else:
        dataset = database.create_dataset(record)

    starter_payload = {
        "title": f"Starter Dashboard: {ingested.name}",
        "summary": "Auto-generated draft dashboard from the upload workflow.",
        "charts": team.report._starter_charts(table_profile.get("columns", [])),
    }
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
    )
    return dataset
