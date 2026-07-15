from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.auth.security import get_current_user
from app.storage import database

router = APIRouter(prefix="/projects/{project_id}/artifacts", tags=["artifacts"])


@router.get("")
def list_artifacts(project_id: str, dataset_id: str | None = None, user: dict = Depends(get_current_user)):
    if not database.get_project_for_user(user["id"], project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    return database.list_artifacts_for_user(user["id"], project_id, dataset_id)


@router.get("/{artifact_id}")
def get_artifact(project_id: str, artifact_id: str, user: dict = Depends(get_current_user)):
    artifact = database.get_artifact_for_user(user["id"], project_id, artifact_id)
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")
    return artifact


@router.delete("/{artifact_id}")
def delete_artifact(project_id: str, artifact_id: str, user: dict = Depends(get_current_user)):
    artifact = database.get_artifact_for_user(user["id"], project_id, artifact_id)
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")
    database.delete_artifact_for_user(user["id"], project_id, artifact_id)
    return {"deleted": True, "artifact_id": artifact_id}
