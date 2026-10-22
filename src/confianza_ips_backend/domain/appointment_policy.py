from collections.abc import Mapping
from datetime import datetime, timedelta, timezone

from .types import AppointmentStatus, Role

ACTIVE_APPOINTMENT_STATUSES = frozenset(
    {AppointmentStatus.REQUESTED.value, AppointmentStatus.CONFIRMED.value}
)
PATIENT_CANCELLATION_CUTOFF = timedelta(hours=24)

ALLOWED_STATUS_TRANSITIONS: Mapping[AppointmentStatus, frozenset[AppointmentStatus]] = {
    AppointmentStatus.REQUESTED: frozenset(
        {AppointmentStatus.CONFIRMED, AppointmentStatus.CANCELLED}
    ),
    AppointmentStatus.CONFIRMED: frozenset(
        {
            AppointmentStatus.CANCELLED,
            AppointmentStatus.COMPLETED,
            AppointmentStatus.NO_SHOW,
        }
    ),
    AppointmentStatus.CANCELLED: frozenset(),
    AppointmentStatus.COMPLETED: frozenset(),
    AppointmentStatus.NO_SHOW: frozenset(),
}


def status_value(status: AppointmentStatus | str) -> str:
    return status.value if isinstance(status, AppointmentStatus) else str(status)


def is_closed(status: AppointmentStatus | str) -> bool:
    return status_value(status) in {
        AppointmentStatus.COMPLETED.value,
        AppointmentStatus.NO_SHOW.value,
    }


def can_transition(current: AppointmentStatus, target: AppointmentStatus) -> bool:
    return target in ALLOWED_STATUS_TRANSITIONS[AppointmentStatus(current)]


def is_patient_within_cutoff(starts_at: datetime, now: datetime | None = None) -> bool:
    current_time = now or datetime.now(timezone.utc)
    return starts_at - current_time < PATIENT_CANCELLATION_CUTOFF


def can_access_appointment(
    role: Role,
    user_patient_id: int | None,
    user_doctor_id: int | None,
    appointment_patient_id: int,
    appointment_doctor_id: int,
) -> bool:
    return (
        role in (Role.ADMIN, Role.RECEPTIONIST)
        or (role == Role.PATIENT and user_patient_id == appointment_patient_id)
        or (role == Role.DOCTOR and user_doctor_id == appointment_doctor_id)
    )
