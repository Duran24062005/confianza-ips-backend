from __future__ import annotations

import hashlib
import hmac
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from ..application.services.agent import (
    activation_digest,
    generate_activation_code,
    normalize_identity,
    verify_activation_code,
)
from ..audit import record_audit
from ..config import Settings, get_settings
from ..db import get_db
from ..models import AgentActivationCode, AgentAuthAttempt, Patient, Role, User
from ..schemas import (
    AgentActivationCodeResponse,
    AgentIdentityResponse,
    AgentTokenRequest,
    AgentTokenResponse,
)
from ..security import (
    create_agent_access_token,
    require_internal_roles,
)

router = APIRouter(prefix="/integrations/agent", tags=["Integración del agente"])
patient = require_internal_roles(Role.PATIENT)

RATE_LIMIT_MAX_ATTEMPTS = 5
RATE_LIMIT_WINDOW = timedelta(minutes=5)
ATTEMPT_RETENTION = timedelta(days=1)


def _require_configuration() -> Settings:
    settings = get_settings()
    if not all(
        value.strip()
        for value in (
            settings.agent_api_key,
            settings.agent_activation_secret,
            settings.agent_jwt_secret,
        )
    ):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Integración del agente no configurada",
        )
    return settings


def _fingerprint(value: str, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), value.encode("utf-8"), hashlib.sha256).hexdigest()


def _request_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _cleanup_attempts(db: Session, now: datetime) -> None:
    db.execute(
        delete(AgentAuthAttempt).where(
            AgentAuthAttempt.attempted_at < now - ATTEMPT_RETENTION
        )
    )


def _is_rate_limited(
    db: Session,
    fingerprints: tuple[tuple[object, str], ...],
    now: datetime,
) -> bool:
    cutoff = now - RATE_LIMIT_WINDOW
    for column, value in fingerprints:
        failures = db.scalar(
            select(func.count(AgentAuthAttempt.id)).where(
                column == value,
                AgentAuthAttempt.attempted_at >= cutoff,
                AgentAuthAttempt.succeeded.is_(False),
            )
        )
        if failures and failures >= RATE_LIMIT_MAX_ATTEMPTS:
            return True
    return False


def _record_attempt(
    db: Session,
    document_fingerprint: str,
    eps_fingerprint: str,
    ip_fingerprint: str,
    client_fingerprint: str,
    succeeded: bool,
    now: datetime,
) -> None:
    db.add(
        AgentAuthAttempt(
            document_fingerprint=document_fingerprint,
            eps_fingerprint=eps_fingerprint,
            ip_fingerprint=ip_fingerprint,
            client_fingerprint=client_fingerprint,
            attempted_at=now,
            succeeded=succeeded,
        )
    )


def _invalid_credentials(
    db: Session,
    document_fingerprint: str,
    eps_fingerprint: str,
    ip_fingerprint: str,
    client_fingerprint: str,
    now: datetime,
) -> None:
    _record_attempt(
        db,
        document_fingerprint,
        eps_fingerprint,
        ip_fingerprint,
        client_fingerprint,
        False,
        now,
    )
    db.commit()
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciales inválidas",
        headers={"WWW-Authenticate": "Bearer"},
    )


@router.post("/activation-code", response_model=AgentActivationCodeResponse)
def issue_activation_code(
    user: User = Depends(patient),
    db: Session = Depends(get_db),
) -> AgentActivationCodeResponse:
    settings = _require_configuration()
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(seconds=settings.agent_activation_expire_seconds)
    if not user.patient_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="El usuario no es un paciente")
    patient_record = db.get(Patient, user.patient_id)
    if not patient_record or not patient_record.active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="El paciente no está activo")
    db.execute(
        update(AgentActivationCode)
        .execution_options(synchronize_session=False)
        .where(
            AgentActivationCode.patient_id == user.patient_id,
            AgentActivationCode.consumed_at.is_(None),
            AgentActivationCode.revoked_at.is_(None),
        )
        .values(revoked_at=now)
    )
    code = generate_activation_code()
    db.add(
        AgentActivationCode(
            patient_id=user.patient_id,
            code_digest=activation_digest(code, settings.agent_activation_secret),
            issued_at=now,
            expires_at=expires_at,
            issued_by_user_id=user.id,
        )
    )
    record_audit(
        db,
        user,
        "issue",
        "agent_activation_code",
        user.patient_id,
        metadata={"channel": "internal", "single_use": True},
    )
    db.commit()
    return AgentActivationCodeResponse(
        code=code,
        expires_at=expires_at,
        expires_in=settings.agent_activation_expire_seconds,
    )


@router.post("/token", response_model=AgentTokenResponse)
def issue_agent_token(
    payload: AgentTokenRequest,
    request: Request,
    agent_api_key: str | None = Header(default=None, alias="X-Confianza-Agent-Key"),
    db: Session = Depends(get_db),
) -> AgentTokenResponse:
    settings = _require_configuration()
    now = datetime.now(timezone.utc)
    document_type = normalize_identity(payload.document_type)
    document_number = normalize_identity(payload.document_number)
    eps = normalize_identity(payload.eps)
    document_fingerprint = _fingerprint(
        f"{document_type}:{document_number}", settings.agent_activation_secret
    )
    eps_fingerprint = _fingerprint(eps, settings.agent_activation_secret)
    ip_fingerprint = _fingerprint(_request_ip(request), settings.agent_activation_secret)
    client_fingerprint = _fingerprint(agent_api_key or "missing", settings.agent_activation_secret)
    fingerprints = (
        (AgentAuthAttempt.document_fingerprint, document_fingerprint),
        (AgentAuthAttempt.eps_fingerprint, eps_fingerprint),
        (AgentAuthAttempt.ip_fingerprint, ip_fingerprint),
        (AgentAuthAttempt.client_fingerprint, client_fingerprint),
    )
    _cleanup_attempts(db, now)
    if _is_rate_limited(db, fingerprints, now):
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Demasiados intentos. Intente nuevamente más tarde.",
            headers={"Retry-After": str(int(RATE_LIMIT_WINDOW.total_seconds()))},
        )

    if not agent_api_key or not hmac.compare_digest(agent_api_key, settings.agent_api_key):
        return _invalid_credentials(
            db,
            document_fingerprint,
            eps_fingerprint,
            ip_fingerprint,
            client_fingerprint,
            now,
        )

    patient_record = db.scalar(
        select(Patient).where(
            func.lower(Patient.document_type) == document_type,
            func.lower(Patient.document_number) == document_number,
        )
    )
    user = (
        db.scalar(
            select(User).where(User.patient_id == patient_record.id, User.role == Role.PATIENT)
        )
        if patient_record
        else None
    )
    activation = (
        db.scalar(
            select(AgentActivationCode)
            .where(
                AgentActivationCode.patient_id == patient_record.id,
                AgentActivationCode.consumed_at.is_(None),
                AgentActivationCode.revoked_at.is_(None),
                AgentActivationCode.expires_at > now,
            )
            .order_by(AgentActivationCode.issued_at.desc())
        )
        if patient_record
        else None
    )
    identity_matches = (
        patient_record
        and patient_record.active
        and user
        and user.active
        and normalize_identity(patient_record.eps) == eps
    )
    if not identity_matches or not activation or not verify_activation_code(
        payload.activation_code, activation.code_digest, settings.agent_activation_secret
    ):
        return _invalid_credentials(
            db,
            document_fingerprint,
            eps_fingerprint,
            ip_fingerprint,
            client_fingerprint,
            now,
        )

    consumed = db.execute(
        update(AgentActivationCode)
        .execution_options(synchronize_session=False)
        .where(
            AgentActivationCode.id == activation.id,
            AgentActivationCode.consumed_at.is_(None),
            AgentActivationCode.revoked_at.is_(None),
            AgentActivationCode.expires_at > now,
        )
        .values(consumed_at=now)
    )
    if consumed.rowcount != 1:
        return _invalid_credentials(
            db,
            document_fingerprint,
            eps_fingerprint,
            ip_fingerprint,
            client_fingerprint,
            now,
        )

    token, expires_in = create_agent_access_token(user)
    _record_attempt(
        db,
        document_fingerprint,
        eps_fingerprint,
        ip_fingerprint,
        client_fingerprint,
        True,
        now,
    )
    record_audit(
        db,
        user,
        "issue",
        "agent_token",
        user.id,
        metadata={"channel": "agent", "scope": "agent:patient"},
    )
    db.commit()
    return AgentTokenResponse(
        access_token=token,
        expires_in=expires_in,
        identity=AgentIdentityResponse(
            user_id=user.id,
            patient_id=patient_record.id,
            full_name=user.full_name,
            eps=patient_record.eps,
        ),
    )
