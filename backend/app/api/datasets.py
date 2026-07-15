from __future__ import annotations

import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.auth.security import get_current_user
from app.settings import UPLOAD_DIR
from app.storage import database
from app.workflows.upload_workflow import run_upload_workflow

router = APIRouter(prefix="/projects/{project_id}/datasets", tags=["datasets"])


@router.get("")
def list_datasets(project_id: str, user: dict = Depends(get_current_user)):
    if not database.get_project_for_user(user["id"], project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    return database.list_datasets_for_user(user["id"], project_id)


@router.post("")
def upload_dataset(project_id: str, file: UploadFile = File(...), user: dict = Depends(get_current_user)):
    if not database.get_project_for_user(user["id"], project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    try:
        return run_upload_workflow(project_id, file.file, file.filename or "dataset.csv", user_id=user["id"])
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{dataset_id}/profile")
def dataset_profile(project_id: str, dataset_id: str, user: dict = Depends(get_current_user)):
    dataset = database.get_dataset_for_user(user["id"], project_id, dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return dataset


@router.delete("/{dataset_id}")
def delete_dataset(project_id: str, dataset_id: str, user: dict = Depends(get_current_user)):
    if not database.get_project_for_user(user["id"], project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    linked_schema = database.get_relational_schema(dataset_id)
    dataset = database.delete_dataset_for_user(user["id"], project_id, dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    if linked_schema and linked_schema.get("project_id") == project_id and linked_schema.get("user_id") == user["id"]:
        database.delete_relational_schema(project_id, dataset_id)
    _delete_upload_folder(dataset)
    return {"deleted": True, "dataset_id": dataset_id}


def _delete_upload_folder(dataset: dict) -> None:
    source_path = Path(str(dataset.get("source_path") or "")).resolve()
    upload_root = UPLOAD_DIR.resolve()
    dataset_dir = source_path.parent
    try:
        dataset_dir.relative_to(upload_root)
    except ValueError:
        return
    if dataset_dir == upload_root:
        return
    shutil.rmtree(dataset_dir, ignore_errors=True)
