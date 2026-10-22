from datetime import date, datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from confianza_ips_backend.db import Base
from confianza_ips_backend.domain.types import AppointmentStatus
from confianza_ips_backend.models import (
    Appointment,
    Doctor,
    Institution,
    Patient,
    Role,
    Service,
    Site,
    User,
)
from confianza_ips_backend.routers.admin import dashboard_analytics


def _appointment(*, patient_id: int, doctor_id: int, service_id: int, site_id: int, creator_id: int, starts_at: datetime, status: AppointmentStatus) -> Appointment:
    return Appointment(
        patient_id=patient_id,
        doctor_id=doctor_id,
        service_id=service_id,
        site_id=site_id,
        created_by_user_id=creator_id,
        starts_at=starts_at,
        ends_at=starts_at + timedelta(minutes=30),
        status=status,
        reason="Prueba unitaria",
    )


def test_dashboard_analytics_aggregates_statuses_services_and_role_scope() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    now = datetime.now(timezone.utc)
    with Session(engine) as db:
        institution = Institution(name="IPS Test", document_number="900000000-1")
        patient = Patient(document_type="CC", document_number="123", first_name="Ana", last_name="Demo", birth_date=date(1990, 1, 1), email="ana@test.demo", phone="3000000", address="Calle 1", city="Bogotá", eps="EPS", emergency_name="Contacto", emergency_phone="3000001")
        doctor = Doctor(license_number="DOC-1", first_name="Laura", last_name="Médica", email="laura@test.demo", phone="3000002")
        service = Service(name="Consulta general", description="", duration_minutes=30)
        db.add_all([institution, patient, doctor, service])
        db.flush()
        site = Site(institution_id=institution.id, name="Sede", address="Calle 1", city="Bogotá")
        admin = User(email="admin@test.demo", full_name="Admin", password_hash="hash", role=Role.ADMIN)
        doctor_user = User(email="doctor@test.demo", full_name="Doctor", password_hash="hash", role=Role.DOCTOR, doctor_id=doctor.id)
        patient_user = User(email="patient@test.demo", full_name="Patient", password_hash="hash", role=Role.PATIENT, patient_id=patient.id)
        db.add_all([site, admin, doctor_user, patient_user])
        db.flush()
        db.add_all([
            _appointment(patient_id=patient.id, doctor_id=doctor.id, service_id=service.id, site_id=site.id, creator_id=admin.id, starts_at=now - timedelta(days=1), status=AppointmentStatus.COMPLETED),
            _appointment(patient_id=patient.id, doctor_id=doctor.id, service_id=service.id, site_id=site.id, creator_id=admin.id, starts_at=now - timedelta(days=2), status=AppointmentStatus.NO_SHOW),
            _appointment(patient_id=patient.id, doctor_id=doctor.id, service_id=service.id, site_id=site.id, creator_id=admin.id, starts_at=now + timedelta(days=1), status=AppointmentStatus.CONFIRMED),
        ])
        db.commit()

        global_data = dashboard_analytics(admin, db, days=7)
        doctor_data = dashboard_analytics(doctor_user, db, days=7)
        patient_data = dashboard_analytics(patient_user, db, days=7)

    assert global_data.scope == "global"
    assert global_data.summary.active_patients == 1
    assert global_data.summary.completed_appointments == 1
    assert global_data.summary.no_show_appointments == 1
    assert global_data.summary.attendance_rate == 50.0
    assert global_data.summary.upcoming_appointments == 1
    assert global_data.service_breakdown[0].service_name == "Consulta general"
    assert len(global_data.trend) == 7
    assert doctor_data.scope == "doctor"
    assert doctor_data.summary.active_patients is None
    assert patient_data.scope == "patient"
    assert patient_data.summary.active_doctors is None
