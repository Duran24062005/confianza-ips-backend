from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
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


def create_waylo_access_token(user: User) -> tuple[str, int]:
    settings = get_settings()
    expires = timedelta(minutes=settings.waylo_token_expire_minutes)
    payload = {
        "sub": str(user.id),
        "typ": "waylo",
        "aud": "waylo",
        "scope": "waylo:read",
        "session_version": user.session_version,
        "exp": datetime.now(timezone.utc) + expires,
    }
    return jwt.encode(payload, settings.waylo_jwt_secret, algorithm="HS256"), int(
        expires.total_seconds()
    )


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Autenticación requerida"
        )
    try:
        payload = jwt.decode(
            credentials.credentials, get_settings().jwt_secret, algorithms=["HS256"]
        )
        user_id = int(payload["sub"])
    except (jwt.InvalidTokenError, KeyError, TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido"
        ) from exc
    user = db.get(User, user_id)
    if not user or not user.active or user.session_version != payload.get("session_version"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sesión no válida")
    return user


def get_waylo_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Autenticación requerida"
        )
    try:
        payload = jwt.decode(
            credentials.credentials,
            get_settings().waylo_jwt_secret,
            algorithms=["HS256"],
            audience="waylo",
        )
        if payload.get("typ") != "waylo" or payload.get("scope") != "waylo:read":
            raise jwt.InvalidTokenError("Token de integración inválido")
        user_id = int(payload["sub"])
    except (jwt.InvalidTokenError, KeyError, TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido"
        ) from exc
    user = db.get(User, user_id)
    patient = db.get(Patient, user.patient_id) if user and user.patient_id else None
    if (
        not user
        or not user.active
        or user.role != Role.PATIENT
        or not patient
        or not patient.active
        or user.session_version != payload.get("session_version")
    ):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sesión no válida")
    return user


def require_roles(*roles: Role) -> Callable:
    def dependency(user: Annotated[User, Depends(get_current_user)]) -> User:
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Permisos insuficientes"
            )
        return user

    return dependency


CurrentUser = Annotated[User, Depends(get_current_user)]
WayloCurrentUser = Annotated[User, Depends(get_waylo_current_user)]
