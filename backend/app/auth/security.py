from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import Depends, HTTPException, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
import bcrypt

from app import settings

SECRET_KEY = settings.JWT_SECRET
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = settings.TOKEN_EXPIRE_MINUTES

security_scheme = HTTPBearer(auto_error=False)

_BCRYPT_MAX_BYTES = 72


def _truncate(password: str) -> bytes:
    """Encode a password while rejecting bcrypt's ambiguous truncation case."""
    encoded = password.encode("utf-8")
    if len(encoded) > _BCRYPT_MAX_BYTES:
        raise ValueError("Password must not exceed 72 UTF-8 bytes")
    return encoded


def hash_password(password: str) -> str:
    return bcrypt.hashpw(_truncate(password), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(_truncate(plain), hashed.encode("utf-8"))


def create_access_token(data: dict[str, Any], expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    issued_at = datetime.now(timezone.utc)
    expire = issued_at + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({
        "exp": expire,
        "iat": issued_at,
        "jti": uuid.uuid4().hex,
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE,
    })
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM],
            issuer=settings.JWT_ISSUER,
            audience=settings.JWT_AUDIENCE,
        )
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")


def issue_session(response: Response, user: dict[str, Any]) -> str:
    token = create_access_token({"sub": user["id"], "email": user["email"]})
    csrf_token = secrets.token_urlsafe(32)
    max_age = ACCESS_TOKEN_EXPIRE_MINUTES * 60
    response.set_cookie(
        settings.AUTH_COOKIE_NAME,
        token,
        max_age=max_age,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        domain=settings.COOKIE_DOMAIN,
        path="/",
    )
    response.set_cookie(
        settings.CSRF_COOKIE_NAME,
        csrf_token,
        max_age=max_age,
        httponly=False,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        domain=settings.COOKIE_DOMAIN,
        path="/",
    )
    return csrf_token


def clear_session(response: Response) -> None:
    for name in (settings.AUTH_COOKIE_NAME, settings.CSRF_COOKIE_NAME):
        response.delete_cookie(name, domain=settings.COOKIE_DOMAIN, path="/")


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security_scheme),
) -> dict[str, Any]:
    """Resolve a user from an HttpOnly session cookie or API bearer token."""
    from app.storage.database import get_user_by_id

    token = credentials.credentials if credentials else request.cookies.get(settings.AUTH_COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    payload = decode_token(token)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")
    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user
