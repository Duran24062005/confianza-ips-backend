from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Appointment, AppointmentStatus, AuditEvent, Doctor, Patient, Role, User
from ..schemas import (
    AuditResponse,
    DashboardAnalyticsResponse,
    DashboardBreakdown,
    DashboardPeriod,
    DashboardResponse,
    DashboardServiceBreakdown,
    DashboardSummary,
    DashboardTrendPoint,
)
from ..security import CurrentUser, require_roles

router = APIRouter(tags=["Administración"])
admin_or_reception = require_roles(Role.ADMIN, Role.RECEPTIONIST)
admin = require_roles(Role.ADMIN)
BUSINESS_TZ = ZoneInfo("America/Bogota")


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


@router.get("/dashboard/analytics", response_model=DashboardAnalyticsResponse)
def dashboard_analytics(
    user: CurrentUser,
    db: Session = Depends(get_db),
    days: int = Query(default=30, ge=7, le=90),
) -> DashboardAnalyticsResponse:
    now = datetime.now(timezone.utc)
    local_now = now.astimezone(BUSINESS_TZ)
    start_date = local_now.date() - timedelta(days=days - 1)
    end_date = local_now.date() + timedelta(days=1)
    start = datetime.combine(start_date, time.min, tzinfo=BUSINESS_TZ).astimezone(timezone.utc)
    end = datetime.combine(end_date, time.min, tzinfo=BUSINESS_TZ).astimezone(timezone.utc)

    query = select(Appointment).order_by(Appointment.starts_at)
    scope = "global"
    if user.role == Role.DOCTOR:
        scope = "doctor"
        query = query.where(Appointment.doctor_id == user.doctor_id)
    elif user.role == Role.PATIENT:
        scope = "patient"
        query = query.where(Appointment.patient_id == user.patient_id)

    period_appointments = list(
        db.scalars(query.where(Appointment.starts_at >= start, Appointment.starts_at < end)).all()
    )
    upcoming_query = query.where(
        Appointment.starts_at > now,
        Appointment.status.in_((AppointmentStatus.REQUESTED, AppointmentStatus.CONFIRMED)),
    )
    upcoming_count = len(db.scalars(upcoming_query).all())

    counts = {status: 0 for status in AppointmentStatus}
    trend_counts = {
        current_date: {status: 0 for status in AppointmentStatus}
        for current_date in (start_date + timedelta(days=index) for index in range(days))
    }
    service_counts: dict[tuple[int, str], int] = {}
    for appointment in period_appointments:
        counts[appointment.status] += 1
        appointment_date = appointment.starts_at.astimezone(BUSINESS_TZ).date()
        if appointment_date in trend_counts:
            trend_counts[appointment_date][appointment.status] += 1
        service_name = appointment.service.name if appointment.service else f"Servicio #{appointment.service_id}"
        service_key = (appointment.service_id, service_name)
        service_counts[service_key] = service_counts.get(service_key, 0) + 1

    attended = counts[AppointmentStatus.COMPLETED] + counts[AppointmentStatus.NO_SHOW]
    attendance_rate = (
        round(counts[AppointmentStatus.COMPLETED] / attended * 100, 1) if attended else None
    )
    today_start = local_now.date()
    today_count = sum(
        1
        for appointment in period_appointments
        if appointment.starts_at.astimezone(BUSINESS_TZ).date() == today_start
    )

    active_patients = active_doctors = None
    if scope == "global":
        active_patients = db.scalar(
            select(func.count(Patient.id)).where(Patient.active.is_(True))
        ) or 0
        active_doctors = db.scalar(
            select(func.count(Doctor.id)).where(Doctor.active.is_(True))
        ) or 0

    return DashboardAnalyticsResponse(
        scope=scope,
        period=DashboardPeriod(days=days, start=start, end=end, timezone="America/Bogota"),
        summary=DashboardSummary(
            active_patients=active_patients,
            active_doctors=active_doctors,
            appointments_today=today_count,
            upcoming_appointments=upcoming_count,
            pending_appointments=counts[AppointmentStatus.REQUESTED],
            confirmed_appointments=counts[AppointmentStatus.CONFIRMED],
            completed_appointments=counts[AppointmentStatus.COMPLETED],
            cancelled_appointments=counts[AppointmentStatus.CANCELLED],
            no_show_appointments=counts[AppointmentStatus.NO_SHOW],
            attendance_rate=attendance_rate,
        ),
        trend=[
            DashboardTrendPoint(
                date=current_date,
                total=sum(day_counts.values()),
                requested=day_counts[AppointmentStatus.REQUESTED],
                confirmed=day_counts[AppointmentStatus.CONFIRMED],
                completed=day_counts[AppointmentStatus.COMPLETED],
                cancelled=day_counts[AppointmentStatus.CANCELLED],
                no_show=day_counts[AppointmentStatus.NO_SHOW],
            )
            for current_date, day_counts in trend_counts.items()
        ],
        status_breakdown=[
            DashboardBreakdown(status=status, count=counts[status]) for status in AppointmentStatus
        ],
        service_breakdown=[
            DashboardServiceBreakdown(service_id=service_id, service_name=service_name, count=count)
            for (service_id, service_name), count in sorted(
                service_counts.items(), key=lambda item: (-item[1], item[0][1])
            )
        ],
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
