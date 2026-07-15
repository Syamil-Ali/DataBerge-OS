from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth.security import get_current_user
from app.storage import database

router = APIRouter(prefix="/projects/{project_id}/chat-sessions", tags=["chat-sessions"])


class CreateSessionRequest(BaseModel):
    dataset_id: str
    title: str = "New Chat"


class UpdateSessionRequest(BaseModel):
    title: str


@router.get("")
def list_sessions(project_id: str, dataset_id: str | None = None, user: dict = Depends(get_current_user)):
    if not database.get_project_for_user(user["id"], project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    sessions = database.list_chat_sessions_for_user(user["id"], project_id, dataset_id)
    for session in sessions:
        session["message_count"] = database.get_chat_message_count_for_user(user["id"], session["id"])
    return sessions


@router.post("")
def create_session(project_id: str, payload: CreateSessionRequest, user: dict = Depends(get_current_user)):
    if not database.get_project_for_user(user["id"], project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    session = database.create_chat_session_for_user(user["id"], project_id, payload.dataset_id, payload.title)
    session["message_count"] = 0
    return session


@router.get("/{session_id}")
def get_session(project_id: str, session_id: str, user: dict = Depends(get_current_user)):
    session = database.get_chat_session_for_user(user["id"], project_id, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    messages = database.list_chat_messages_for_user(user["id"], project_id, session_id=session_id)
    session["messages"] = messages
    session["message_count"] = len(messages)
    return session


@router.patch("/{session_id}")
def update_session(project_id: str, session_id: str, payload: UpdateSessionRequest, user: dict = Depends(get_current_user)):
    session = database.get_chat_session_for_user(user["id"], project_id, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    updated = database.update_chat_session_title_for_user(user["id"], project_id, session_id, payload.title)
    if updated:
        updated["message_count"] = database.get_chat_message_count_for_user(user["id"], session_id)
    return updated


@router.delete("/{session_id}")
def delete_session(project_id: str, session_id: str, user: dict = Depends(get_current_user)):
    session = database.get_chat_session_for_user(user["id"], project_id, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    database.delete_chat_session_for_user(user["id"], project_id, session_id)
    return {"deleted": True, "session_id": session_id}
