from __future__ import annotations

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.config.settings import Settings
from app.db.session import get_db, get_settings_dep
from app.models.user import User
from app.security.jwt_tokens import decode_token_subject

_security = HTTPBearer(auto_error=False)


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_security),
    db: Session = Depends(get_db),
    cfg: Settings = Depends(get_settings_dep),
) -> User:
    if creds is None or creds.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="not_authenticated")
    try:
        uid = decode_token_subject(creds.credentials, cfg, expected_typ="access")
    except ValueError:
        raise HTTPException(status_code=401, detail="invalid_token") from None
    user = db.get(User, uid)
    if user is None:
        raise HTTPException(status_code=401, detail="user_not_found")
    return user
