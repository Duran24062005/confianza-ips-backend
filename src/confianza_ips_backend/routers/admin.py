from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Appointment, AppointmentStatus, AuditEvent, Doctor, Patient, Role, User
from ..schemas import AuditResponse, DashboardResponse
from ..security import require_roles

router = APIRouter(tags=["Administración"])
admin_or_reception = require_roles(Role.ADMIN, Role.RECEPTIONIST)
admin = require_roles(Role.ADMIN)


@router.get("/dashboard", response_model=DashboardResponse)
def dashboard(
    _: User = Depends(admin_or_reception), db: Session = Depends(get_db)
) -> DashboardResponse:
    from datetime import datetime, time, timedelta, timezone
    from zoneinfo import ZoneInfo

    now = datetime.now(timezone.utc)
    local_now = now.astimezone(ZoneInfo("America/Bogota"))
    day_start = datetime.combine(
        local_now.date(), time.min, tzinfo=ZoneInfo("America/Bogota")
    ).astimezone(timezone.utc)
    day_end = day_start + timedelta(days=1)
    return DashboardResponse(
        active_patients=db.scalar(select(func.count(Patient.id)).where(Patient.active.is_(True)))
        or 0,
        inactive_patients=db.scalar(select(func.count(Patient.id)).where(Patient.active.is_(False)))
        or 0,
        active_doctors=db.scalar(select(func.count(Doctor.id)).where(Doctor.active.is_(True))) or 0,
        appointments_today=db.scalar(
            select(func.count(Appointment.id)).where(
                Appointment.starts_at >= day_start, Appointment.starts_at < day_end
            )
        )
        or 0,
        pending_appointments=db.scalar(
            select(func.count(Appointment.id)).where(
                Appointment.status == AppointmentStatus.REQUESTED
            )
        )
        or 0,
        confirmed_appointments=db.scalar(
            select(func.count(Appointment.id)).where(
                Appointment.status == AppointmentStatus.CONFIRMED
            )
        )
        or 0,
        cancelled_appointments=db.scalar(
            select(func.count(Appointment.id)).where(
                Appointment.status == AppointmentStatus.CANCELLED
            )
        )
        or 0,
        upcoming_appointments=db.scalar(
            select(func.count(Appointment.id)).where(
                Appointment.starts_at > now,
                Appointment.status.in_((AppointmentStatus.REQUESTED, AppointmentStatus.CONFIRMED)),
            )
        )
        or 0,
    )


@router.get("/audit", response_model=list[AuditResponse])
def audit_events(
    _: User = Depends(admin), db: Session = Depends(get_db), limit: int = 100
) -> list[AuditEvent]:
    if limit < 1 or limit > 500:
        raise HTTPException(status_code=422, detail="El límite debe estar entre 1 y 500")
    return list(
        db.scalars(select(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(limit)).all()
    )
