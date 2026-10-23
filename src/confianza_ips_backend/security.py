from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pwdlib import PasswordHash
from sqlalchemy.orm import Session

from .config import get_settings
from .db import get_db
from .models import Patient, Role, User

password_hash = PasswordHash.recommended()
bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return password_hash.verify(password, hashed)


def create_access_token(user: User) -> tuple[str, int]:
    settings = get_settings()
    expires = timedelta(minutes=settings.jwt_expire_minutes)
    payload = {
        "sub": str(user.id),
        "role": user.role.value if isinstance(user.role, Role) else str(user.role),
        "session_version": user.session_version,
        "exp": datetime.now(timezone.utc) + expires,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256"), int(expires.total_seconds())


def create_agent_access_token(user: User) -> tuple[str, int]:
    settings = get_settings()
    expires = timedelta(minutes=settings.agent_token_expire_minutes)
    payload = {
        "sub": str(user.id),
        "typ": "agent",
        "aud": "agent",
        "scope": "agent:patient",
        "session_version": user.session_version,
        "exp": datetime.now(timezone.utc) + expires,
    }
    return jwt.encode(payload, settings.agent_jwt_secret, algorithm="HS256"), int(
        expires.total_seconds()
    )


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    db: Annotated[Session, Depends(get_db)],
    request: Request = None,
) -> User:
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Autenticación requerida"
        )
    settings = get_settings()
    payload: dict[str, object] | None = None
    source = "internal"
    try:
        candidate = jwt.decode(credentials.credentials, settings.jwt_secret, algorithms=["HS256"])
        if candidate.get("typ") == "agent":
            raise jwt.InvalidTokenError("Token de agente en el canal interno")
        payload = candidate
    except jwt.InvalidTokenError:
        try:
            candidate = jwt.decode(
                credentials.credentials,
                getattr(settings, "agent_jwt_secret", ""),
                algorithms=["HS256"],
                audience="agent",
            )
            if candidate.get("typ") != "agent" or candidate.get("scope") != "agent:patient":
                raise jwt.InvalidTokenError("Token de agente inválido")
            payload = candidate
            source = "agent"
        except (jwt.InvalidTokenError, KeyError, TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido"
            ) from exc
    try:
        user_id = int(payload["sub"])
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido"
        ) from exc
    user = db.get(User, user_id)
    patient = db.get(Patient, user.patient_id) if user and user.patient_id else None
    if source == "agent" and (
        not user
        or user.role != Role.PATIENT
        or not patient
        or not patient.active
    ):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sesión no válida")
    if not user or not user.active or user.session_version != payload.get("session_version"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sesión no válida")
    if request is not None:
        request.state.auth_channel = source
    return user


def get_internal_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    db: Annotated[Session, Depends(get_db)],
    request: Request = None,
) -> User:
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Autenticación requerida"
        )
    try:
        payload = jwt.decode(credentials.credentials, get_settings().jwt_secret, algorithms=["HS256"])
        if payload.get("typ") == "agent":
            raise jwt.InvalidTokenError("Token de agente no permitido")
        user_id = int(payload["sub"])
    except (jwt.InvalidTokenError, KeyError, TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido"
        ) from exc
    user = db.get(User, user_id)
    if not user or not user.active or user.session_version != payload.get("session_version"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sesión no válida")
    if request is not None:
        request.state.auth_channel = "internal"
    return user


def is_agent_request(request: Request) -> bool:
    return getattr(request.state, "auth_channel", "internal") == "agent"


def auth_metadata(request: Request, **metadata: object) -> dict[str, object]:
    return {"channel": getattr(request.state, "auth_channel", "internal"), **metadata}


def require_roles(*roles: Role) -> Callable:
    def dependency(user: Annotated[User, Depends(get_current_user)]) -> User:
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Permisos insuficientes"
            )
        return user

    return dependency


CurrentUser = Annotated[User, Depends(get_current_user)]
InternalUser = Annotated[User, Depends(get_internal_user)]


def require_internal_roles(*roles: Role) -> Callable:
    def dependency(user: Annotated[User, Depends(get_internal_user)]) -> User:
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Permisos insuficientes"
            )
        return user

    return dependency
