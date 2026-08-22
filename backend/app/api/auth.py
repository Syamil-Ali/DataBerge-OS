from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel

from app import settings
from app.auth.security import clear_session, get_current_user, hash_password, issue_session, verify_password
from app.storage.database import create_user, get_user_by_email, get_user_storage, MAX_STORAGE_BYTES

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    email: str
    name: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


def _validate_password(password: str) -> None:
    if len(password) < 12:
        raise HTTPException(status_code=400, detail="Password must be at least 12 characters")
    if len(password.encode("utf-8")) > 72:
        raise HTTPException(status_code=400, detail="Password must not exceed 72 UTF-8 bytes")
    if not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        raise HTTPException(status_code=400, detail="Password must contain a letter and a number")


@router.post("/register", status_code=201)
def register(req: RegisterRequest, response: Response):
    if not req.name.strip():
        raise HTTPException(status_code=400, detail="Name is required")
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", req.email.strip()):
        raise HTTPException(status_code=400, detail="A valid email address is required")
    _validate_password(req.password)
    existing = get_user_by_email(req.email.strip().lower())
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    user = create_user(
        email=req.email.strip().lower(),
        name=req.name.strip(),
        password_hash=hash_password(req.password),
    )
    csrf_token = issue_session(response, user)
    return {"user": user, "csrf_token": csrf_token}


@router.post("/login")
def login(req: LoginRequest, response: Response):
    user = get_user_by_email(req.email.strip().lower())
    try:
        valid = bool(user and verify_password(req.password, user["password_hash"]))
    except ValueError:
        valid = False
    if not valid:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    assert user is not None
    safe_user = {k: v for k, v in user.items() if k != "password_hash"}
    csrf_token = issue_session(response, safe_user)
    return {"user": safe_user, "csrf_token": csrf_token}


@router.post("/logout", status_code=204)
def logout(response: Response):
    clear_session(response)


@router.get("/me")
def me(request: Request, user: dict = Depends(get_current_user)):
    storage = get_user_storage(user["id"])
    return {
        "user": user,
        "storage_used": storage,
        "storage_limit": MAX_STORAGE_BYTES,
        "csrf_token": request.cookies.get(settings.CSRF_COOKIE_NAME),
    }
