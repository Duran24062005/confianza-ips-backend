from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..audit import record_audit
from ..db import get_db
from ..models import Doctor, DoctorSchedule, Role, ScheduleBlock, Service, User
from ..schemas import AvailabilitySlot, BlockCreate, BlockResponse, ScheduleCreate, ScheduleResponse
from ..security import CurrentUser, require_roles

router = APIRouter(tags=["Agendas"])
admin = require_roles(Role.ADMIN)
staff = require_roles(Role.ADMIN, Role.RECEPTIONIST)
BUSINESS_TZ = ZoneInfo("America/Bogota")
ACTIVE_APPOINTMENT_STATUSES = ("requested", "confirmed")


def as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=BUSINESS_TZ)
    return value.astimezone(timezone.utc)


@router.get("/doctors/{doctor_id}/schedules", response_model=list[ScheduleResponse])
def list_schedules(
    doctor_id: int, _: CurrentUser, db: Session = Depends(get_db)
) -> list[DoctorSchedule]:
    return list(
        db.scalars(
            select(DoctorSchedule)
            .where(DoctorSchedule.doctor_id == doctor_id, DoctorSchedule.active.is_(True))
            .order_by(DoctorSchedule.weekday, DoctorSchedule.start_time)
        ).all()
    )


@router.post(
    "/doctors/{doctor_id}/schedules",
    response_model=ScheduleResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_schedule(
    doctor_id: int,
    payload: ScheduleCreate,
    user: User = Depends(admin),
    db: Session = Depends(get_db),
) -> DoctorSchedule:
    if not db.get(Doctor, doctor_id):
        raise HTTPException(status_code=404, detail="Médico no encontrado")
    if payload.start_time >= payload.end_time:
        raise HTTPException(
            status_code=422, detail="El horario debe tener una hora final posterior"
        )
    schedule = DoctorSchedule(doctor_id=doctor_id, **payload.model_dump())
    db.add(schedule)
    db.flush()
    record_audit(db, user, "create", "doctor_schedule", schedule.id, after=payload.model_dump())
    db.commit()
    db.refresh(schedule)
    return schedule


@router.get("/doctors/{doctor_id}/blocks", response_model=list[BlockResponse])
def list_blocks(
    doctor_id: int, _: CurrentUser, db: Session = Depends(get_db)
) -> list[ScheduleBlock]:
    return list(
        db.scalars(
            select(ScheduleBlock).where(
                ScheduleBlock.doctor_id == doctor_id, ScheduleBlock.active.is_(True)
            )
        ).all()
    )


@router.post(
    "/doctors/{doctor_id}/blocks", response_model=BlockResponse, status_code=status.HTTP_201_CREATED
)
def create_block(
    doctor_id: int,
    payload: BlockCreate,
    user: User = Depends(admin),
    db: Session = Depends(get_db),
) -> ScheduleBlock:
    if not db.get(Doctor, doctor_id):
        raise HTTPException(status_code=404, detail="Médico no encontrado")
    starts_at, ends_at = as_utc(payload.starts_at), as_utc(payload.ends_at)
    if starts_at >= ends_at:
        raise HTTPException(status_code=422, detail="El bloqueo debe tener un rango válido")
    block = ScheduleBlock(
        doctor_id=doctor_id, starts_at=starts_at, ends_at=ends_at, reason=payload.reason
    )
    db.add(block)
    db.flush()
    record_audit(
        db, user, "create", "schedule_block", block.id, after=payload.model_dump(mode="json")
    )
    db.commit()
    db.refresh(block)
    return block


def is_slot_available(db: Session, doctor_id: int, starts_at: datetime, ends_at: datetime) -> bool:
    from ..models import Appointment

    blocked = db.scalar(
        select(ScheduleBlock.id).where(
            ScheduleBlock.doctor_id == doctor_id,
            ScheduleBlock.active.is_(True),
            ScheduleBlock.starts_at < ends_at,
            ScheduleBlock.ends_at > starts_at,
        )
    )
    if blocked:
        return False
    occupied = db.scalar(
        select(Appointment.id).where(
            Appointment.doctor_id == doctor_id,
            Appointment.status.in_(ACTIVE_APPOINTMENT_STATUSES),
            Appointment.starts_at < ends_at,
            Appointment.ends_at > starts_at,
        )
    )
    return occupied is None


def is_within_schedule(db: Session, doctor_id: int, starts_at: datetime, ends_at: datetime) -> bool:
    local_start = starts_at.astimezone(BUSINESS_TZ)
    local_end = ends_at.astimezone(BUSINESS_TZ)
    if local_start.date() != local_end.date():
        return False
    schedules = db.scalars(
        select(DoctorSchedule).where(
            DoctorSchedule.doctor_id == doctor_id,
            DoctorSchedule.weekday == local_start.weekday(),
            DoctorSchedule.active.is_(True),
        )
    ).all()
    return any(
        schedule.start_time <= local_start.time() and schedule.end_time >= local_end.time()
        for schedule in schedules
    )


@router.get("/availability", response_model=list[AvailabilitySlot])
def availability(
    doctor_id: int,
    service_id: int,
    target_date: date = Query(alias="date"),
    _: CurrentUser = None,
    db: Session = Depends(get_db),
) -> list[AvailabilitySlot]:
    doctor = db.get(Doctor, doctor_id)
    service = db.get(Service, service_id)
    if not doctor or not doctor.active or not service or not service.active:
        raise HTTPException(status_code=404, detail="Médico o servicio no encontrado")
    schedules = db.scalars(
        select(DoctorSchedule).where(
            DoctorSchedule.doctor_id == doctor_id,
            DoctorSchedule.weekday == target_date.weekday(),
            DoctorSchedule.active.is_(True),
        )
    ).all()
    slots: list[AvailabilitySlot] = []
    for schedule in schedules:
        cursor = datetime.combine(target_date, schedule.start_time, tzinfo=BUSINESS_TZ)
        end_of_schedule = datetime.combine(target_date, schedule.end_time, tzinfo=BUSINESS_TZ)
        while cursor + timedelta(minutes=service.duration_minutes) <= end_of_schedule:
            starts_at = cursor.astimezone(timezone.utc)
            ends_at = (cursor + timedelta(minutes=service.duration_minutes)).astimezone(
                timezone.utc
            )
            if starts_at > datetime.now(timezone.utc) and is_slot_available(
                db, doctor_id, starts_at, ends_at
            ):
                slots.append(
                    AvailabilitySlot(
                        starts_at=starts_at,
                        ends_at=ends_at,
                        doctor_id=doctor_id,
                        service_id=service_id,
                    )
                )
            cursor += timedelta(minutes=service.duration_minutes)
    return slots
