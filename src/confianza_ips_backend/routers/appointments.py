from datetime import date, datetime, time, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..audit import record_audit
from ..db import get_db
from ..models import (
    Appointment,
    AppointmentStatus,
    AppointmentStatusHistory,
    Doctor,
    DoctorService,
    Patient,
    Role,
    Service,
    Site,
    User,
)
from ..routers.schedules import BUSINESS_TZ, as_utc, is_slot_available, is_within_schedule
from ..schemas import (
    AppointmentCreate,
    AppointmentHistoryResponse,
    AppointmentReschedule,
    AppointmentResponse,
    AppointmentStatusChange,
)
from ..security import CurrentUser, require_roles

router = APIRouter(prefix="/appointments", tags=["Citas"])
staff = require_roles(Role.ADMIN, Role.RECEPTIONIST)
ACTIVE_STATUSES = (AppointmentStatus.REQUESTED, AppointmentStatus.CONFIRMED)
PATIENT_CUTOFF = timedelta(hours=24)


def can_access(appointment: Appointment, user: User) -> bool:
    return (
        user.role in (Role.ADMIN, Role.RECEPTIONIST)
        or (user.role == Role.PATIENT and user.patient_id == appointment.patient_id)
        or (user.role == Role.DOCTOR and user.doctor_id == appointment.doctor_id)
    )


def get_appointment_or_404(db: Session, appointment_id: int) -> Appointment:
    appointment = db.get(Appointment, appointment_id)
    if not appointment:
        raise HTTPException(status_code=404, detail="Cita no encontrada")
    return appointment


def validate_appointment(
    db: Session, patient_id: int, doctor_id: int, service_id: int, site_id: int, starts_at: datetime
) -> tuple[Patient, Doctor, Service, datetime, datetime]:
    patient = db.get(Patient, patient_id)
    doctor = db.get(Doctor, doctor_id)
    service = db.get(Service, service_id)
    site = db.get(Site, site_id)
    if not patient or not patient.active:
        raise HTTPException(status_code=422, detail="El paciente no está activo")
    if not doctor or not doctor.active:
        raise HTTPException(status_code=422, detail="El médico no está activo")
    if not service or not service.active or not site or not site.active:
        raise HTTPException(status_code=422, detail="Servicio o sede no disponible")
    if not db.scalar(
        select(DoctorService.doctor_id).where(
            DoctorService.doctor_id == doctor_id, DoctorService.service_id == service_id
        )
    ):
        raise HTTPException(status_code=422, detail="El médico no presta este servicio")
    starts_at = as_utc(starts_at)
    ends_at = starts_at + timedelta(minutes=service.duration_minutes)
    if starts_at <= datetime.now(timezone.utc):
        raise HTTPException(status_code=422, detail="La cita debe estar en el futuro")
    if not is_within_schedule(db, doctor_id, starts_at, ends_at):
        raise HTTPException(status_code=409, detail="El horario está fuera de la agenda del médico")
    if not is_slot_available(db, doctor_id, starts_at, ends_at):
        raise HTTPException(status_code=409, detail="El horario no está disponible")
    return patient, doctor, service, starts_at, ends_at


@router.get("", response_model=list[AppointmentResponse])
def list_appointments(
    user: CurrentUser,
    db: Session = Depends(get_db),
    target_date: date | None = Query(default=None, alias="date"),
    status_filter: AppointmentStatus | None = Query(default=None, alias="status"),
) -> list[Appointment]:
    query = select(Appointment).order_by(Appointment.starts_at)
    if user.role == Role.PATIENT:
        query = query.where(Appointment.patient_id == user.patient_id)
    elif user.role == Role.DOCTOR:
        query = query.where(Appointment.doctor_id == user.doctor_id)
    if target_date:
        start = datetime.combine(target_date, time.min, tzinfo=BUSINESS_TZ).astimezone(timezone.utc)
        end = start + timedelta(days=1)
        query = query.where(Appointment.starts_at >= start, Appointment.starts_at < end)
    if status_filter:
        query = query.where(Appointment.status == status_filter)
    return list(db.scalars(query).all())


@router.post("", response_model=AppointmentResponse, status_code=status.HTTP_201_CREATED)
def create_appointment(
    payload: AppointmentCreate, user: CurrentUser, db: Session = Depends(get_db)
) -> Appointment:
    patient_id = user.patient_id if user.role == Role.PATIENT else payload.patient_id
    if not patient_id:
        raise HTTPException(status_code=422, detail="Debe indicar el paciente")
    patient, doctor, service, starts_at, ends_at = validate_appointment(
        db, patient_id, payload.doctor_id, payload.service_id, payload.site_id, payload.starts_at
    )
    appointment = Appointment(
        patient_id=patient.id,
        doctor_id=doctor.id,
        service_id=service.id,
        site_id=payload.site_id,
        starts_at=starts_at,
        ends_at=ends_at,
        status=AppointmentStatus.REQUESTED
        if user.role == Role.PATIENT
        else AppointmentStatus.CONFIRMED,
        reason=payload.reason,
        created_by_user_id=user.id,
    )
    db.add(appointment)
    try:
        db.flush()
        history = AppointmentStatusHistory(
            appointment_id=appointment.id,
            from_status=None,
            to_status=appointment.status.value,
            reason="Creación de la cita",
            changed_by_user_id=user.id,
        )
        db.add(history)
        record_audit(
            db,
            user,
            "create",
            "appointment",
            appointment.id,
            after={"status": appointment.status.value, "starts_at": starts_at},
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409, detail="El horario fue ocupado por otra solicitud"
        ) from exc
    db.refresh(appointment)
    return appointment


@router.get("/{appointment_id}", response_model=AppointmentResponse)
def get_appointment(
    appointment_id: int, user: CurrentUser, db: Session = Depends(get_db)
) -> Appointment:
    appointment = get_appointment_or_404(db, appointment_id)
    if not can_access(appointment, user):
        raise HTTPException(status_code=403, detail="No puede consultar esta cita")
    return appointment


@router.post("/{appointment_id}/status", response_model=AppointmentResponse)
def change_status(
    appointment_id: int,
    payload: AppointmentStatusChange,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> Appointment:
    appointment = get_appointment_or_404(db, appointment_id)
    if not can_access(appointment, user):
        raise HTTPException(status_code=403, detail="No puede modificar esta cita")
    if user.role == Role.PATIENT and payload.status != AppointmentStatus.CANCELLED:
        raise HTTPException(status_code=403, detail="El paciente solo puede cancelar su cita")
    if (
        user.role == Role.PATIENT
        and payload.status == AppointmentStatus.CANCELLED
        and appointment.starts_at - datetime.now(timezone.utc) < PATIENT_CUTOFF
    ):
        raise HTTPException(
            status_code=403, detail="La cancelación debe solicitarse con 24 horas de anticipación"
        )
    if user.role == Role.DOCTOR and payload.status not in (
        AppointmentStatus.COMPLETED,
        AppointmentStatus.NO_SHOW,
    ):
        raise HTTPException(status_code=403, detail="El médico solo puede cerrar la atención")
    if (
        appointment.status in (AppointmentStatus.COMPLETED, AppointmentStatus.NO_SHOW)
        and payload.status != appointment.status
    ):
        raise HTTPException(status_code=409, detail="La cita ya fue cerrada")
    allowed = {
        AppointmentStatus.REQUESTED: {AppointmentStatus.CONFIRMED, AppointmentStatus.CANCELLED},
        AppointmentStatus.CONFIRMED: {
            AppointmentStatus.CANCELLED,
            AppointmentStatus.COMPLETED,
            AppointmentStatus.NO_SHOW,
        },
        AppointmentStatus.CANCELLED: set(),
        AppointmentStatus.COMPLETED: set(),
        AppointmentStatus.NO_SHOW: set(),
    }
    if payload.status not in allowed[AppointmentStatus(appointment.status)]:
        raise HTTPException(status_code=409, detail="Transición de estado no permitida")
    before = (
        appointment.status.value
        if isinstance(appointment.status, AppointmentStatus)
        else str(appointment.status)
    )
    appointment.status = payload.status
    db.add(
        AppointmentStatusHistory(
            appointment_id=appointment.id,
            from_status=before,
            to_status=payload.status.value,
            reason=payload.reason,
            changed_by_user_id=user.id,
        )
    )
    record_audit(
        db,
        user,
        "status_change",
        "appointment",
        appointment.id,
        before={"status": before},
        after={"status": payload.status.value},
    )
    db.commit()
    db.refresh(appointment)
    return appointment


@router.post("/{appointment_id}/reschedule", response_model=AppointmentResponse)
def reschedule(
    appointment_id: int,
    payload: AppointmentReschedule,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> Appointment:
    appointment = get_appointment_or_404(db, appointment_id)
    if not can_access(appointment, user):
        raise HTTPException(status_code=403, detail="No puede modificar esta cita")
    if appointment.status in (
        AppointmentStatus.COMPLETED,
        AppointmentStatus.NO_SHOW,
        AppointmentStatus.CANCELLED,
    ):
        raise HTTPException(status_code=409, detail="La cita no puede reprogramarse")
    if (
        user.role == Role.PATIENT
        and appointment.starts_at - datetime.now(timezone.utc) < PATIENT_CUTOFF
    ):
        raise HTTPException(
            status_code=403, detail="El cambio debe solicitarse con 24 horas de anticipación"
        )
    starts_at = as_utc(payload.starts_at)
    ends_at = starts_at + (appointment.ends_at - appointment.starts_at)
    if starts_at <= datetime.now(timezone.utc):
        raise HTTPException(status_code=422, detail="La nueva fecha debe estar en el futuro")
    if not is_within_schedule(db, appointment.doctor_id, starts_at, ends_at):
        raise HTTPException(
            status_code=409, detail="El nuevo horario está fuera de la agenda del médico"
        )
    if not is_slot_available(db, appointment.doctor_id, starts_at, ends_at):
        raise HTTPException(status_code=409, detail="El nuevo horario no está disponible")
    before = {"starts_at": appointment.starts_at, "ends_at": appointment.ends_at}
    appointment.starts_at, appointment.ends_at = starts_at, ends_at
    record_audit(
        db,
        user,
        "reschedule",
        "appointment",
        appointment.id,
        before=before,
        after={"starts_at": starts_at, "ends_at": ends_at},
    )
    db.commit()
    db.refresh(appointment)
    return appointment


@router.get("/{appointment_id}/history", response_model=list[AppointmentHistoryResponse])
def appointment_history(
    appointment_id: int, user: CurrentUser, db: Session = Depends(get_db)
) -> list[AppointmentStatusHistory]:
    appointment = get_appointment_or_404(db, appointment_id)
    if not can_access(appointment, user):
        raise HTTPException(status_code=403, detail="No puede consultar este historial")
    return list(
        db.scalars(
            select(AppointmentStatusHistory)
            .where(AppointmentStatusHistory.appointment_id == appointment_id)
            .order_by(AppointmentStatusHistory.changed_at)
        ).all()
    )
