from __future__ import annotations

import argparse
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select

from confianza_ips_backend.db import Base, SessionLocal, engine
from confianza_ips_backend.models import (
    Appointment,
    AppointmentStatus,
    AppointmentStatusHistory,
    ClinicalEncounter,
    ClinicalNote,
    Doctor,
    DoctorSchedule,
    DoctorService,
    DoctorSpecialty,
    Institution,
    Patient,
    Role,
    Service,
    Site,
    Specialty,
    User,
)
from confianza_ips_backend.security import hash_password

DEMO_PASSWORD = "Confianza123!"
BUSINESS_TZ = ZoneInfo("America/Bogota")


def demo_appointment_specs(
    today: date, patients: list[Patient], doctors: list[Doctor], services: dict[str, Service]
) -> tuple[tuple[Patient, Doctor, Service, datetime, AppointmentStatus, str], ...]:
    """Build a deterministic, varied appointment timeline around the seed date."""

    def local_start(day_offset: int, hour: int) -> datetime:
        local_date = today + timedelta(days=day_offset)
        return datetime.combine(local_date, time(hour), tzinfo=BUSINESS_TZ).astimezone(UTC)

    return (
        (
            patients[0],
            doctors[0],
            services["Consulta general"],
            local_start(-1, 9),
            AppointmentStatus.COMPLETED,
            "Control preventivo",
        ),
        (
            patients[1],
            doctors[1],
            services["Consulta pediátrica"],
            local_start(-3, 10),
            AppointmentStatus.NO_SHOW,
            "Seguimiento de crecimiento",
        ),
        (
            patients[0],
            doctors[0],
            services["Consulta general"],
            local_start(-6, 11),
            AppointmentStatus.CANCELLED,
            "Cambio de disponibilidad",
        ),
        (
            patients[1],
            doctors[1],
            services["Consulta pediátrica"],
            local_start(-10, 8),
            AppointmentStatus.COMPLETED,
            "Valoración de seguimiento",
        ),
        (
            patients[0],
            doctors[1],
            services["Consulta pediátrica"],
            local_start(-15, 14),
            AppointmentStatus.CONFIRMED,
            "Consulta de control",
        ),
        (
            patients[1],
            doctors[0],
            services["Consulta general"],
            local_start(1, 9),
            AppointmentStatus.REQUESTED,
            "Solicitud de nueva cita",
        ),
        (
            patients[0],
            doctors[0],
            services["Consulta general"],
            local_start(3, 15),
            AppointmentStatus.CONFIRMED,
            "Control preventivo futuro",
        ),
    )


def seed(create_schema: bool = False) -> None:
    if create_schema:
        Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        institution = db.scalar(select(Institution).where(Institution.name == "Confianza IPS"))
        if not institution:
            institution = Institution(name="Confianza IPS", document_number="900000000-1")
            db.add(institution)
            db.flush()
        site = db.scalar(select(Site).where(Site.institution_id == institution.id))
        if not site:
            site = Site(
                institution_id=institution.id,
                name="Sede Central",
                address="Carrera 10 # 20-30",
                city="Bogotá",
            )
            db.add(site)

        specialties = {}
        for name in ("Medicina general", "Pediatría", "Medicina interna"):
            specialty = db.scalar(select(Specialty).where(Specialty.name == name))
            if not specialty:
                specialty = Specialty(name=name)
                db.add(specialty)
                db.flush()
            specialties[name] = specialty

        services = {}
        for name, duration in (
            ("Consulta general", 30),
            ("Consulta pediátrica", 40),
            ("Control de medicina interna", 45),
        ):
            service = db.scalar(select(Service).where(Service.name == name))
            if not service:
                service = Service(
                    name=name,
                    description="Servicio ficticio para demostración",
                    duration_minutes=duration,
                )
                db.add(service)
                db.flush()
            services[name] = service

        doctors = []
        for license_number, first_name, last_name, email, specialty_name, service_name in (
            (
                "RM-10001",
                "Laura",
                "Gómez",
                "laura.medica@confianza.demo",
                "Medicina general",
                "Consulta general",
            ),
            (
                "RM-10002",
                "Andrés",
                "Pérez",
                "andres.medico@confianza.demo",
                "Pediatría",
                "Consulta pediátrica",
            ),
        ):
            doctor = db.scalar(select(Doctor).where(Doctor.license_number == license_number))
            if not doctor:
                doctor = Doctor(
                    license_number=license_number,
                    first_name=first_name,
                    last_name=last_name,
                    email=email,
                    phone="3000000000",
                )
                db.add(doctor)
                db.flush()
            if not db.scalar(
                select(DoctorSpecialty).where(
                    DoctorSpecialty.doctor_id == doctor.id,
                    DoctorSpecialty.specialty_id == specialties[specialty_name].id,
                )
            ):
                db.add(
                    DoctorSpecialty(
                        doctor_id=doctor.id, specialty_id=specialties[specialty_name].id
                    )
                )
            if not db.scalar(
                select(DoctorService).where(
                    DoctorService.doctor_id == doctor.id,
                    DoctorService.service_id == services[service_name].id,
                )
            ):
                db.add(DoctorService(doctor_id=doctor.id, service_id=services[service_name].id))
            if not db.scalar(select(DoctorSchedule).where(DoctorSchedule.doctor_id == doctor.id)):
                db.add(
                    DoctorSchedule(
                        doctor_id=doctor.id, weekday=0, start_time=time(8), end_time=time(16)
                    )
                )
                db.add(
                    DoctorSchedule(
                        doctor_id=doctor.id, weekday=2, start_time=time(8), end_time=time(16)
                    )
                )
            doctors.append(doctor)

        patients = []
        for document, first_name, last_name, email in (
            ("100000001", "Mariana", "Rojas", "mariana.paciente@confianza.demo"),
            ("100000002", "Carlos", "Torres", "carlos.paciente@confianza.demo"),
        ):
            patient = db.scalar(select(Patient).where(Patient.document_number == document))
            if not patient:
                patient = Patient(
                    document_type="CC",
                    document_number=document,
                    first_name=first_name,
                    last_name=last_name,
                    birth_date=date(1995, 4, 12),
                    email=email,
                    phone="3100000000",
                    address="Calle 1 # 2-3",
                    city="Bogotá",
                    eps="EPS Confianza Ficticia",
                    emergency_name="Contacto Demo",
                    emergency_phone="3200000000",
                )
                db.add(patient)
                db.flush()
            patients.append(patient)

        accounts = (
            ("admin@confianza.demo", "Administración Confianza", Role.ADMIN, None, None),
            ("recepcion@confianza.demo", "Recepción Confianza", Role.RECEPTIONIST, None, None),
            ("laura.medica@confianza.demo", "Dra. Laura Gómez", Role.DOCTOR, None, doctors[0].id),
            (
                "mariana.paciente@confianza.demo",
                "Mariana Rojas",
                Role.PATIENT,
                patients[0].id,
                None,
            ),
        )
        for email, full_name, role, patient_id, doctor_id in accounts:
            user = db.scalar(select(User).where(User.email == email))
            if not user:
                db.add(
                    User(
                        email=email,
                        full_name=full_name,
                        password_hash=hash_password(DEMO_PASSWORD),
                        role=role,
                        patient_id=patient_id,
                        doctor_id=doctor_id,
                    )
                )
        db.flush()
        admin_user = db.scalar(select(User).where(User.email == "admin@confianza.demo"))
        today = datetime.now(UTC).astimezone(BUSINESS_TZ).date()
        demo_appointments = demo_appointment_specs(today, patients, doctors, services)
        for patient, doctor, service, starts_at, appointment_status, reason in demo_appointments:
            existing = db.scalar(
                select(Appointment).where(
                    Appointment.patient_id == patient.id,
                    Appointment.starts_at == starts_at,
                )
            )
            if not existing:
                appointment = Appointment(
                    patient_id=patient.id,
                    doctor_id=doctor.id,
                    service_id=service.id,
                    site_id=site.id,
                    starts_at=starts_at,
                    ends_at=starts_at + timedelta(minutes=service.duration_minutes),
                    status=appointment_status,
                    reason=reason,
                    created_by_user_id=admin_user.id,
                )
                db.add(appointment)
                db.flush()
                db.add(
                    AppointmentStatusHistory(
                        appointment_id=appointment.id,
                        from_status=None,
                        to_status=appointment_status.value,
                        reason="Registro inicial de demostración",
                        changed_by_user_id=admin_user.id,
                    )
                )
                if appointment_status == AppointmentStatus.COMPLETED:
                    encounter = ClinicalEncounter(
                        appointment_id=appointment.id,
                        patient_id=patient.id,
                        doctor_id=doctor.id,
                    )
                    db.add(encounter)
                    db.flush()
                    db.add(
                        ClinicalNote(
                            encounter_id=encounter.id,
                            version=1,
                            note_type="evolution",
                            content="Motivo: Seguimiento\nObservación: Evolución estable en escenario ficticio.\nEvolución: Continuar controles según agenda.",
                            created_by_user_id=admin_user.id,
                        )
                    )
        db.commit()
        print(f"Seed completado con {len(demo_appointments)} escenarios de citas.")
        print(f"Todas las cuentas demo usan la contraseña: {DEMO_PASSWORD}")
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Carga datos ficticios e idempotentes de Confianza"
    )
    parser.add_argument(
        "--create-schema", action="store_true", help="Crea tablas para un entorno local vacío"
    )
    args = parser.parse_args()
    seed(create_schema=args.create_schema)
