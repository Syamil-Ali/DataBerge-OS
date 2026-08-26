from __future__ import annotations

import base64
import hashlib
import json
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

from app import settings


def _fernet() -> Fernet:
    seed = settings.CONNECTOR_SECRET_KEY or settings.JWT_SECRET
    key = base64.urlsafe_b64encode(hashlib.sha256(seed.encode("utf-8")).digest())
    return Fernet(key)


def encrypt_connector_secret(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return "v1:" + _fernet().encrypt(raw).decode("ascii")


def decrypt_connector_secret(value: str) -> dict[str, str]:
    if not value.startswith("v1:"):
        raise ValueError("Unsupported connector secret format")
    try:
        payload = json.loads(_fernet().decrypt(value[3:].encode("ascii")).decode("utf-8"))
    except (InvalidToken, ValueError, json.JSONDecodeError) as exc:
        raise ValueError("Connector credentials could not be decrypted") from exc
    return {str(key): str(item) for key, item in payload.items()}
