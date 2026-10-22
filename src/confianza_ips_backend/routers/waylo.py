from __future__ import annotations

import binascii
import hashlib
import hmac
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from ..application.services.waylo import (
    current_totp,
    normalize_email,
    normalize_name,
    totp_expiry,
    verify_totp,
)
from ..audit import record_audit
from ..config import Settings, get_settings
from ..db import get_db
from ..models import (
    Appointment,
    AppointmentStatus,
    AppointmentStatusHistory,
    Patient,
    Role,
    User,
    WayloAuthAttempt,
)
from ..schemas import (
    AppointmentHistoryResponse,
    AppointmentResponse,
    PatientResponse,
    UserResponse,
    WayloCodeResponse,
    WayloProfileResponse,
    WayloTokenRequest,
    WayloTokenResponse,
)
from ..security import WayloCurrentUser, create_waylo_access_token, require_roles

router = APIRouter(prefix="/integrations/waylo", tags=["Integración Waylo"])
admin = require_roles(Role.ADMIN)

RATE_LIMIT_MAX_ATTEMPTS = 5
RATE_LIMIT_WINDOW = timedelta(minutes=5)
ATTEMPT_RETENTION = timedelta(days=1)
BUSINESS_TZ = ZoneInfo("America/Bogota")


def _require_configuration() -> Settings:
    settings = get_settings()
    if not settings.waylo_totp_secret.strip() or not settings.waylo_jwt_secret.strip():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Integración Waylo no configurada",
        )
    try:
        current_totp(settings.waylo_totp_secret, settings.waylo_totp_interval_seconds)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Integración Waylo no configurada",
        ) from exc
    return settings


def _fingerprint(value: str) -> str:
    secret = get_settings().jwt_secret.encode("utf-8")
    return hmac.new(secret, value.encode("utf-8"), hashlib.sha256).hexdigest()


def _request_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _cleanup_attempts(db: Session, now: datetime) -> None:
    db.execute(
        delete(WayloAuthAttempt).where(WayloAuthAttempt.attempted_at < now - ATTEMPT_RETENTION)
    )


def _is_rate_limited(
    db: Session, email_fingerprint: str, ip_fingerprint: str, now: datetime
) -> bool:
    cutoff = now - RATE_LIMIT_WINDOW
    for column, value in (
        (WayloAuthAttempt.email_fingerprint, email_fingerprint),
        (WayloAuthAttempt.ip_fingerprint, ip_fingerprint),
    ):
        failures = db.scalar(
            select(func.count(WayloAuthAttempt.id)).where(
                column == value,
                WayloAuthAttempt.attempted_at >= cutoff,
                WayloAuthAttempt.succeeded.is_(False),
            )
        )
        if failures and failures >= RATE_LIMIT_MAX_ATTEMPTS:
            return True
    return False


def _record_attempt(
    db: Session,
    email_fingerprint: str,
    ip_fingerprint: str,
    succeeded: bool,
    now: datetime,
) -> None:
    db.add(
        WayloAuthAttempt(
            email_fingerprint=email_fingerprint,
            ip_fingerprint=ip_fingerprint,
            attempted_at=now,
            succeeded=succeeded,
        )
    )


def _invalid_credentials(
    db: Session,
    email_fingerprint: str,
    ip_fingerprint: str,
    now: datetime,
) -> None:
    _record_attempt(db, email_fingerprint, ip_fingerprint, False, now)
    db.commit()
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciales inválidas",
        headers={"WWW-Authenticate": "Bearer"},
    )


@router.get("/code", response_model=WayloCodeResponse)
def get_waylo_code(_: User = Depends(admin)) -> WayloCodeResponse:
    settings = _require_configuration()
    now = datetime.now(timezone.utc)
    return WayloCodeResponse(
        code=current_totp(settings.waylo_totp_secret, settings.waylo_totp_interval_seconds, now),
        expires_at=totp_expiry(settings.waylo_totp_interval_seconds, now),
        interval_seconds=settings.waylo_totp_interval_seconds,
    )


@router.post("/token", response_model=WayloTokenResponse)
def issue_waylo_token(
    payload: WayloTokenRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> WayloTokenResponse:
    settings = _require_configuration()
    now = datetime.now(timezone.utc)
    email = normalize_email(str(payload.email))
    email_fingerprint = _fingerprint(email)
    ip_fingerprint = _fingerprint(_request_ip(request))
    _cleanup_attempts(db, now)
    if _is_rate_limited(db, email_fingerprint, ip_fingerprint, now):
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Demasiados intentos. Intente nuevamente más tarde.",
            headers={"Retry-After": str(int(RATE_LIMIT_WINDOW.total_seconds()))},
        )

    if not verify_totp(
        settings.waylo_totp_secret,
        payload.code,
        settings.waylo_totp_interval_seconds,
        now,
        window=1,
    ):
        return _invalid_credentials(db, email_fingerprint, ip_fingerprint, now)

    user = db.scalar(select(User).where(func.lower(User.email) == email))
    patient = db.get(Patient, user.patient_id) if user and user.patient_id else None
    if (
        not user
        or not user.active
        or user.role != Role.PATIENT
        or not patient
        or not patient.active
        or not hmac.compare_digest(
            normalize_name(user.full_name), normalize_name(payload.full_name)
        )
    ):
        return _invalid_credentials(db, email_fingerprint, ip_fingerprint, now)

    token, expires_in = create_waylo_access_token(user)
    _record_attempt(db, email_fingerprint, ip_fingerprint, True, now)
    record_audit(
        db,
        user,
        "issue",
        "waylo_token",
        user.id,
        metadata={"integration": "waylo", "scope": "waylo:read"},
    )
    db.commit()
    return WayloTokenResponse(
        access_token=token,
        expires_in=expires_in,
        user=UserResponse.model_validate(user),
        patient=PatientResponse.model_validate(patient),
    )


@router.get("/me", response_model=WayloProfileResponse)
def get_waylo_profile(
    user: WayloCurrentUser, db: Session = Depends(get_db)
) -> WayloProfileResponse:
    patient = db.get(Patient, user.patient_id)
    if not patient or not patient.active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Paciente no encontrado")
    return WayloProfileResponse(
        user=UserResponse.model_validate(user), patient=PatientResponse.model_validate(patient)
    )


@router.get("/appointments", response_model=list[AppointmentResponse])
def list_waylo_appointments(
    user: WayloCurrentUser,
    db: Session = Depends(get_db),
    target_date: date | None = Query(default=None, alias="date"),
    status_filter: AppointmentStatus | None = Query(default=None, alias="status"),
) -> list[Appointment]:
    query = (
        select(Appointment)
        .where(Appointment.patient_id == user.patient_id)
        .order_by(Appointment.starts_at)
    )
    if target_date:
        start = datetime.combine(target_date, datetime.min.time(), tzinfo=BUSINESS_TZ).astimezone(
            timezone.utc
        )
        end = start + timedelta(days=1)
        query = query.where(Appointment.starts_at >= start, Appointment.starts_at < end)
    if status_filter:
        query = query.where(Appointment.status == status_filter)
    return list(db.scalars(query).all())


def _get_owned_appointment(appointment_id: int, user: User, db: Session) -> Appointment:
    appointment = db.get(Appointment, appointment_id)
    if not appointment or appointment.patient_id != user.patient_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cita no encontrada")
    return appointment


@router.get("/appointments/{appointment_id}", response_model=AppointmentResponse)
def get_waylo_appointment(
    appointment_id: int, user: WayloCurrentUser, db: Session = Depends(get_db)
) -> Appointment:
    return _get_owned_appointment(appointment_id, user, db)


@router.get(
    "/appointments/{appointment_id}/history",
    response_model=list[AppointmentHistoryResponse],
)
def get_waylo_appointment_history(
    appointment_id: int, user: WayloCurrentUser, db: Session = Depends(get_db)
) -> list[AppointmentStatusHistory]:
    _get_owned_appointment(appointment_id, user, db)
    return list(
        db.scalars(
            select(AppointmentStatusHistory)
            .where(AppointmentStatusHistory.appointment_id == appointment_id)
            .order_by(AppointmentStatusHistory.changed_at)
        ).all()
    )
