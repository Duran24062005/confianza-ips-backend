import importlib.util
from datetime import date, time
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from confianza_ips_backend.db import Base
from confianza_ips_backend.domain.types import AppointmentStatus
from confianza_ips_backend.models import Doctor, DoctorSchedule, Patient, Service

BUSINESS_TZ = ZoneInfo("America/Bogota")

seed_spec = importlib.util.spec_from_file_location(
    "confianza_seed", Path(__file__).parents[1] / "scripts" / "seed.py"
)
assert seed_spec and seed_spec.loader
seed_module = importlib.util.module_from_spec(seed_spec)
seed_spec.loader.exec_module(seed_module)
demo_appointment_specs = seed_module.demo_appointment_specs
ensure_demo_schedules = seed_module.ensure_demo_schedules


def test_demo_seed_covers_all_appointment_states_in_the_analytics_period() -> None:
    patients = [
        Patient(
            id=1,
            document_type="CC",
            document_number="1",
            first_name="Ana",
            last_name="Demo",
            birth_date=date(1990, 1, 1),
            email="ana@test.demo",
            phone="3000000",
            address="Calle 1",
            city="Bogotá",
            eps="EPS",
            emergency_name="Contacto",
            emergency_phone="3000001",
        ),
        Patient(
            id=2,
            document_type="CC",
            document_number="2",
            first_name="Carlos",
            last_name="Demo",
            birth_date=date(1990, 1, 1),
            email="carlos@test.demo",
            phone="3000002",
            address="Calle 2",
            city="Bogotá",
            eps="EPS",
            emergency_name="Contacto",
            emergency_phone="3000003",
        ),
    ]
    doctors = [
        Doctor(
            id=1,
            license_number="DOC-1",
            first_name="Laura",
            last_name="Demo",
            email="laura@test.demo",
            phone="3000004",
        ),
        Doctor(
            id=2,
            license_number="DOC-2",
            first_name="Andrés",
            last_name="Demo",
            email="andres@test.demo",
            phone="3000005",
        ),
    ]
    services = {
        "Consulta general": Service(
            id=1, name="Consulta general", description="", duration_minutes=30
        ),
        "Consulta pediátrica": Service(
            id=2, name="Consulta pediátrica", description="", duration_minutes=40
        ),
    }

    specs = demo_appointment_specs(date(2026, 10, 22), patients, doctors, services)
    statuses = {item[4] for item in specs}
    offsets = {(item[3].astimezone(BUSINESS_TZ).date() - date(2026, 10, 22)).days for item in specs}

    assert statuses == {
        AppointmentStatus.REQUESTED,
        AppointmentStatus.CONFIRMED,
        AppointmentStatus.COMPLETED,
        AppointmentStatus.CANCELLED,
        AppointmentStatus.NO_SHOW,
    }
    assert min(offsets) >= -30
    assert max(offsets) <= 90


def test_demo_schedule_seed_is_complete_and_idempotent() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as db:
            doctor = Doctor(
                license_number="SEED-1",
                first_name="Demo",
                last_name="Doctor",
                email="seed@confianza.demo",
                phone="3000000",
            )
            db.add(doctor)
            db.flush()

            db.add(
                DoctorSchedule(
                    doctor_id=doctor.id,
                    weekday=0,
                    start_time=time(8),
                    end_time=time(16),
                )
            )
            db.flush()
            ensure_demo_schedules(db, doctor.id)
            ensure_demo_schedules(db, doctor.id)
            db.commit()

            schedules = db.scalars(
                select(DoctorSchedule).where(DoctorSchedule.doctor_id == doctor.id)
            ).all()
            assert len(schedules) == 7
            assert {schedule.weekday for schedule in schedules} == set(range(7))
            assert {
                (schedule.start_time.hour, schedule.end_time.hour) for schedule in schedules
            } == {(8, 16)}
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()
