from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.auth.security import get_current_user
from app.models.schemas import ReportRequest, ReportTypeCreate, ReportTypeUpdate
from app.services.report_queue import queue_report_workflow
from app.storage import database
from data_berge_core.skills.report_templates import get_template, list_templates

router = APIRouter(prefix="/projects/{project_id}/reports", tags=["reports"])


def _validate_report_type_dataset(user_id: str, project_id: str, dataset_id: str) -> None:
    if not database.get_dataset_for_user(user_id, project_id, dataset_id):
        raise HTTPException(status_code=404, detail="Dataset not found for this project")


@router.get("/types")
def list_report_types(project_id: str, dataset_id: str, user: dict = Depends(get_current_user)):
    if not database.get_project_for_user(user["id"], project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    _validate_report_type_dataset(user["id"], project_id, dataset_id)
    return database.list_report_types_for_user(user["id"], project_id, dataset_id)


@router.post("/types")
def create_report_type(project_id: str, payload: ReportTypeCreate, user: dict = Depends(get_current_user)):
    if not database.get_project_for_user(user["id"], project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    _validate_report_type_dataset(user["id"], project_id, payload.dataset_id)
    config = payload.model_dump(exclude={"dataset_id", "name", "description", "is_default"})
    return database.create_report_type_for_user(
        user["id"],
        project_id,
        payload.dataset_id,
        payload.name,
        payload.description,
        config,
        payload.is_default,
    )


@router.patch("/types/{report_type_id}")
def update_report_type(
    project_id: str,
    report_type_id: str,
    payload: ReportTypeUpdate,
    user: dict = Depends(get_current_user),
):
    if not database.get_project_for_user(user["id"], project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    current = database.get_report_type_for_user(user["id"], project_id, report_type_id)
    if not current:
        raise HTTPException(status_code=404, detail="Report type not found")
    dataset_id = str(current.get("dataset_id") or "")
    _validate_report_type_dataset(user["id"], project_id, dataset_id)
    config = payload.model_dump(exclude={"name", "description", "is_default"})
    return database.update_report_type_for_user(
        user["id"],
        project_id,
        report_type_id,
        dataset_id=dataset_id,
        name=payload.name,
        description=payload.description,
        payload=config,
        is_default=payload.is_default,
    )


@router.delete("/types/{report_type_id}")
def delete_report_type(project_id: str, report_type_id: str, user: dict = Depends(get_current_user)):
    if not database.get_project_for_user(user["id"], project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    if not database.delete_report_type_for_user(user["id"], project_id, report_type_id):
        raise HTTPException(status_code=404, detail="Report type not found")
    return {"deleted": True, "report_type_id": report_type_id}


@router.get("/templates")
def get_report_templates(user: dict = Depends(get_current_user)):
    return {"templates": list_templates()}


@router.get("/templates/{template_name}")
def get_report_template(template_name: str, user: dict = Depends(get_current_user)):
    tmpl = get_template(template_name)
    if not tmpl:
        raise HTTPException(status_code=404, detail=f"Template '{template_name}' not found")
    return tmpl


@router.post("")
def create_report(project_id: str, payload: ReportRequest, user: dict = Depends(get_current_user)):
    if not database.get_project_for_user(user["id"], project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    try:
        return queue_report_workflow(project_id, payload, user_id=user["id"])
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
