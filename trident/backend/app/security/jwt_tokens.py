from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import jwt

from app.config.settings import Settings


def create_access_token(user_id: uuid.UUID, cfg: Settings) -> str:
    now = datetime.now(timezone.utc)
    exp = now + timedelta(minutes=cfg.jwt_access_expire_minutes)
    payload = {"sub": str(user_id), "typ": "access", "iat": int(now.timestamp()), "exp": exp}
    return jwt.encode(payload, cfg.jwt_secret, algorithm=cfg.jwt_algorithm)


def create_refresh_token(user_id: uuid.UUID, cfg: Settings) -> str:
    now = datetime.now(timezone.utc)
    exp = now + timedelta(days=cfg.jwt_refresh_expire_days)
    payload = {"sub": str(user_id), "typ": "refresh", "iat": int(now.timestamp()), "exp": exp}
    return jwt.encode(payload, cfg.jwt_secret, algorithm=cfg.jwt_algorithm)


def decode_token_subject(token: str, cfg: Settings, *, expected_typ: str) -> uuid.UUID:
    try:
        payload = jwt.decode(token, cfg.jwt_secret, algorithms=[cfg.jwt_algorithm])
    except jwt.PyJWTError as e:
        raise ValueError("invalid_token") from e
    if payload.get("typ") != expected_typ:
        raise ValueError("wrong_token_type")
    sub = payload.get("sub")
    if not sub:
        raise ValueError("missing_subject")
    return uuid.UUID(str(sub))
