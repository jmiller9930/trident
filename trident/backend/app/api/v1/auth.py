from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config.settings import Settings
from app.db.session import get_db, get_settings_dep
from app.models.enums import AuditActorType, AuditEventType
from app.models.user import User
from app.repositories.audit_repository import AuditRepository
from app.schemas.auth_schemas import (
    AuthResponse,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    RegisterResponse,
    TokenBundle,
    UserPublic,
)
from app.security.jwt_tokens import create_access_token, create_refresh_token, decode_token_subject
from app.security.passwords import hash_password, verify_password

router = APIRouter()


def _normalize_email(email: str) -> str:
    return email.strip().lower()


@router.post("/register", response_model=RegisterResponse, status_code=201)
def register(
    body: RegisterRequest,
    db: Session = Depends(get_db),
    cfg: Settings = Depends(get_settings_dep),
) -> RegisterResponse:
    email = _normalize_email(str(body.email))
    existing = db.scalars(select(User).where(User.email == email)).first()
    if existing is not None:
        raise HTTPException(status_code=409, detail="email_already_registered")

    user = User(
        display_name=body.display_name,
        email=email,
        password_hash=hash_password(body.password),
    )
    db.add(user)
    db.flush()
    audit = AuditRepository(db)
    audit.record(
        event_type=AuditEventType.USER_REGISTERED,
        event_payload={"email": email},
        actor_type=AuditActorType.USER,
        actor_id=str(user.id),
    )
    audit.record(
        event_type=AuditEventType.CONTROL_PLANE_ACTION,
        event_payload={"action": "register"},
        actor_type=AuditActorType.USER,
        actor_id=str(user.id),
    )
    tokens = TokenBundle(
        access_token=create_access_token(user.id, cfg),
        refresh_token=create_refresh_token(user.id, cfg),
    )
    return RegisterResponse(user=UserPublic.model_validate(user), tokens=tokens)


@router.post("/login", response_model=AuthResponse)
def login(
    body: LoginRequest,
    db: Session = Depends(get_db),
    cfg: Settings = Depends(get_settings_dep),
) -> AuthResponse:
    email = _normalize_email(str(body.email))
    user = db.scalars(select(User).where(User.email == email)).first()
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="invalid_credentials")

    audit = AuditRepository(db)
    audit.record(
        event_type=AuditEventType.USER_LOGIN,
        event_payload={"email": email},
        actor_type=AuditActorType.USER,
        actor_id=str(user.id),
    )
    audit.record(
        event_type=AuditEventType.CONTROL_PLANE_ACTION,
        event_payload={"action": "login"},
        actor_type=AuditActorType.USER,
        actor_id=str(user.id),
    )
    tokens = TokenBundle(
        access_token=create_access_token(user.id, cfg),
        refresh_token=create_refresh_token(user.id, cfg),
    )
    return AuthResponse(user=UserPublic.model_validate(user), tokens=tokens)


@router.post("/refresh", response_model=TokenBundle)
def refresh_tokens(
    body: RefreshRequest,
    db: Session = Depends(get_db),
    cfg: Settings = Depends(get_settings_dep),
) -> TokenBundle:
    try:
        uid = decode_token_subject(body.refresh_token, cfg, expected_typ="refresh")
    except ValueError:
        raise HTTPException(status_code=401, detail="invalid_refresh_token") from None
    user = db.get(User, uid)
    if user is None:
        raise HTTPException(status_code=401, detail="user_not_found")

    audit = AuditRepository(db)
    audit.record(
        event_type=AuditEventType.AUTH_REFRESH,
        event_payload={},
        actor_type=AuditActorType.USER,
        actor_id=str(user.id),
    )
    return TokenBundle(
        access_token=create_access_token(user.id, cfg),
        refresh_token=create_refresh_token(user.id, cfg),
    )
