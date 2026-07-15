from __future__ import annotations

import threading

from app.models.schemas import ReportRequest
from app.services.profiling import json_safe
from app.storage import database
from app.workflows.report_workflow import run_report_workflow


def queue_report_workflow(project_id: str, payload: ReportRequest, user_id: str) -> dict:
    dataset = database.get_dataset_for_user(user_id, project_id, payload.dataset_id)
    schema = database.get_relational_schema(payload.dataset_id)
    schema_allowed = bool(
        schema
        and schema.get("project_id") == project_id
        and schema.get("user_id") == user_id
    )
    if not dataset and not schema_allowed:
        raise FileNotFoundError("Dataset not found for this project.")

    template = payload.template or "executive"
    blocks = payload.blocks or []
    custom_blocks = payload.custom_blocks or []
    sections = _progress_sections()
    placeholder = database.create_artifact(
        project_id,
        "report",
        "Generating draft",
        {
            "template": template,
            "request": json_safe(payload.model_dump()),
            "report_progress": {
                "status": "queued",
                "message": "Queued draft generation",
                "percent": 5,
                "current_step": "queued",
                "sections": sections,
            },
            "blocks": blocks,
            "custom_blocks": json_safe([block.model_dump() for block in custom_blocks]),
            "report_type": payload.report_type,
        },
        dataset_id=payload.dataset_id,
        status="generating",
        user_id=user_id,
    )

    thread = threading.Thread(
        target=_run_report_task,
        args=(project_id, payload, user_id, placeholder["id"]),
        daemon=True,
    )
    thread.start()
    return placeholder


def _run_report_task(project_id: str, payload: ReportRequest, user_id: str, artifact_id: str) -> None:
    def progress_callback(key: str, label: str, percent: int) -> None:
        artifact = database.get_artifact_for_user(user_id, project_id, artifact_id)
        if not artifact:
            return
        report_payload = artifact.get("payload") or {}
        progress = report_payload.get("report_progress") or {}
        sections = progress.get("sections") or _progress_sections()
        report_payload["report_progress"] = {
            **progress,
            "status": "running" if percent < 100 else "completed",
            "message": label,
            "percent": percent,
            "current_step": key,
            "sections": _mark_sections(sections, key),
        }
        database.update_artifact_for_user(
            user_id,
            project_id,
            artifact_id,
            payload=report_payload,
        )

    try:
        progress_callback("queued", "Starting draft generation", 10)
        run_report_workflow(
            project_id,
            payload,
            user_id=user_id,
            artifact_id=artifact_id,
            progress_callback=progress_callback,
        )
    except Exception as exc:
        artifact = database.get_artifact_for_user(user_id, project_id, artifact_id)
        report_payload = artifact.get("payload") if artifact else {}
        report_payload = report_payload if isinstance(report_payload, dict) else {}
        progress = report_payload.get("report_progress") or {}
        report_payload["report_progress"] = {
            **progress,
            "status": "failed",
            "message": str(exc) or "Report generation failed.",
            "percent": max(5, int(progress.get("percent") or 5)),
            "current_step": "failed",
            "sections": progress.get("sections") or _progress_sections(),
        }
        database.update_artifact_for_user(
            user_id,
            project_id,
            artifact_id,
            status="failed",
            title="Report generation failed",
            payload=report_payload,
        )


def _progress_sections() -> list[dict[str, str]]:
    return [
        {"key": "readiness", "label": "Readiness", "status": "pending"},
        {"key": "investigation", "label": "Investigation", "status": "pending"},
        {"key": "narrative", "label": "Narrative", "status": "pending"},
        {"key": "governance", "label": "Governance", "status": "pending"},
        {"key": "storage", "label": "Storage", "status": "pending"},
    ]


def _mark_sections(sections: list[dict], current_key: str) -> list[dict[str, str]]:
    order = ["readiness", "investigation", "narrative", "governance", "storage", "complete"]
    current_index = order.index(current_key) if current_key in order else -1
    result: list[dict[str, str]] = []
    for section in sections:
        key = str(section.get("key") or "")
        index = order.index(key) if key in order else 999
        if current_key == "complete" or index < current_index:
            status = "completed"
        elif index == current_index:
            status = "running"
        else:
            status = str(section.get("status") or "pending")
        result.append({
            "key": key,
            "label": str(section.get("label") or key),
            "status": status,
        })
    return result
