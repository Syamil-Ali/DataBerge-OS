from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.auth.security import get_current_user
from app.models.schemas import ProjectCreate
from app.storage import database

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("")
def list_projects(user: dict = Depends(get_current_user)):
    projects = database.list_projects_for_user(user["id"])
    if not projects:
        projects.append(database.create_project_for_user(user["id"], "Executive Analytics Workspace", "Default local workspace"))
    return projects


@router.post("")
def create_project(payload: ProjectCreate, user: dict = Depends(get_current_user)):
    return database.create_project_for_user(user["id"], payload.name, payload.description)


@router.get("/{project_id}/overview")
def project_overview(project_id: str, user: dict = Depends(get_current_user)):
    project = database.get_project_for_user(user["id"], project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    datasets = database.list_datasets_for_user(user["id"], project_id)
    artifacts = database.list_artifacts_for_user(user["id"], project_id)
    return {"project": project, "datasets": datasets, "artifacts": artifacts}
