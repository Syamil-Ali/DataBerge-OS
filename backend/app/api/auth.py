from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth.security import create_access_token, get_current_user, hash_password, verify_password
from app.storage.database import create_user, get_user_by_email, get_user_storage, MAX_STORAGE_BYTES

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    email: str
    name: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


@router.post("/register")
def register(req: RegisterRequest):
    if len(req.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
    existing = get_user_by_email(req.email.strip().lower())
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    user = create_user(
        email=req.email.strip().lower(),
        name=req.name.strip(),
        password_hash=hash_password(req.password),
    )
    token = create_access_token({"sub": user["id"], "email": user["email"]})
    return {"token": token, "user": user}


@router.post("/login")
def login(req: LoginRequest):
    user = get_user_by_email(req.email.strip().lower())
    if not user or not verify_password(req.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = create_access_token({"sub": user["id"], "email": user["email"]})
    safe_user = {k: v for k, v in user.items() if k != "password_hash"}
    return {"token": token, "user": safe_user}


@router.get("/me")
def me(user: dict = Depends(get_current_user)):
    storage = get_user_storage(user["id"])
    return {
        "user": user,
        "storage_used": storage,
        "storage_limit": MAX_STORAGE_BYTES,
    }
