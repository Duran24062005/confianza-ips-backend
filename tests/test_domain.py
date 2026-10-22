from datetime import datetime, timedelta, timezone

from confianza_ips_backend.domain.appointment_policy import (
    ACTIVE_APPOINTMENT_STATUSES,
    can_access_appointment,
    can_transition,
    is_patient_within_cutoff,
)
from confianza_ips_backend.domain.types import AppointmentStatus, Role


def test_active_appointment_statuses_are_persisted_values() -> None:
    assert ACTIVE_APPOINTMENT_STATUSES == {"requested", "confirmed"}


def test_appointment_status_policy_rejects_closed_transitions() -> None:
    assert can_transition(AppointmentStatus.REQUESTED, AppointmentStatus.CONFIRMED)
    assert not can_transition(AppointmentStatus.COMPLETED, AppointmentStatus.CANCELLED)


def test_patient_access_is_scoped_to_the_appointment_patient() -> None:
    assert can_access_appointment(Role.PATIENT, 10, None, 10, 20)
    assert not can_access_appointment(Role.PATIENT, 11, None, 10, 20)
    assert can_access_appointment(Role.DOCTOR, None, 20, 10, 20)


def test_patient_cancellation_cutoff_is_calculated_from_utc() -> None:
    now = datetime.now(timezone.utc)

    assert is_patient_within_cutoff(now + timedelta(hours=23), now)
    assert not is_patient_within_cutoff(now + timedelta(hours=25), now)
