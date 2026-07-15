from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.auth.security import get_current_user
from app.models.schemas import ChatRequest
from app.storage import database
from app.workflows.chat_workflow import build_chat_profile_context, run_chat_workflow

router = APIRouter(prefix="/projects/{project_id}/chat", tags=["chat"])


@router.get("/profile-context")
def chat_profile_context(project_id: str, dataset_id: str, user: dict = Depends(get_current_user)):
    try:
        return build_chat_profile_context(project_id, dataset_id, user_id=user["id"])
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("")
def chat_history(project_id: str, dataset_id: str | None = None, user: dict = Depends(get_current_user)):
    if not database.get_project_for_user(user["id"], project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    return database.list_chat_messages_for_user(user["id"], project_id, dataset_id)


@router.post("")
def chat(project_id: str, payload: ChatRequest, user: dict = Depends(get_current_user)):
    try:
        return run_chat_workflow(
            project_id,
            payload.dataset_id,
            payload.message,
            session_id=payload.session_id,
            user_id=user["id"],
            attachments=[attachment.model_dump() for attachment in payload.attachments],
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Chat workflow failed: {exc}") from exc


@router.delete("")
def clear_history(project_id: str, dataset_id: str | None = None, user: dict = Depends(get_current_user)):
    if not database.get_project_for_user(user["id"], project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    deleted = database.clear_chat_messages_for_user(user["id"], project_id, dataset_id)
    return {"deleted": deleted}


@router.delete("/messages/{message_id}")
def delete_message(project_id: str, message_id: str, user: dict = Depends(get_current_user)):
    if not database.delete_chat_message_for_user(user["id"], project_id, message_id):
        raise HTTPException(status_code=404, detail="Chat message not found")
    return {"deleted": True, "message_id": message_id}
