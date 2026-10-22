import os
from datetime import date, time

os.environ.setdefault("DATABASE_URL", "sqlite:///./test-suite.db")
os.environ.setdefault("JWT_SECRET", "test-secret-with-at-least-32-characters")
os.environ.setdefault("WAYLO_TOTP_SECRET", "JBSWY3DPEHPK3PXP")
os.environ.setdefault("WAYLO_JWT_SECRET", "test-waylo-secret-with-at-least-32-characters")
os.environ.setdefault("CORS_ORIGINS", "http://localhost:5173")
os.environ.setdefault("APP_ENV", "test")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from confianza_ips_backend.db import Base, get_db
from confianza_ips_backend.main import app
from confianza_ips_backend.models import (
    Doctor,
    DoctorSchedule,
    DoctorService,
    Institution,
    Patient,
    Role,
    Service,
    Site,
    User,
)
from confianza_ips_backend.security import hash_password


@pytest.fixture()
def client(tmp_path, monkeypatch):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    db = session_factory()
    institution = Institution(name="Confianza Test", document_number="900000000-9")
    db.add(institution)
    db.flush()
    site = Site(institution_id=institution.id, name="Sede Test", address="Calle 1", city="Bogotá")
    patient = Patient(
        document_type="CC",
        document_number="123",
        first_name="Ana",
        last_name="Prueba",
        birth_date=date(1990, 1, 1),
        email="ana@confianza.demo",
        phone="3000000",
        address="Calle 1",
        city="Bogotá",
        eps="EPS Test",
        emergency_name="Contacto",
        emergency_phone="3000001",
    )
    doctor = Doctor(
        license_number="TEST-1",
        first_name="Médico",
        last_name="Prueba",
        email="doctor@confianza.demo",
        phone="3000002",
    )
    service = Service(name="Consulta Test", description="Servicio de prueba", duration_minutes=30)
    db.add_all([site, patient, doctor, service])
    db.flush()
    db.add_all(
        [
            User(
                email="admin@confianza.demo",
                full_name="Admin Test",
                password_hash=hash_password("Password123!"),
                role=Role.ADMIN,
            ),
            User(
                email="patient@confianza.demo",
                full_name="Ana Prueba",
                password_hash=hash_password("Password123!"),
                role=Role.PATIENT,
                patient_id=patient.id,
            ),
            User(
                email="doctor@confianza.demo",
                full_name="Médico Prueba",
                password_hash=hash_password("Password123!"),
                role=Role.DOCTOR,
                doctor_id=doctor.id,
            ),
        ]
    )
    db.add(DoctorService(doctor_id=doctor.id, service_id=service.id))
    db.add_all(
        [
            DoctorSchedule(
                doctor_id=doctor.id, weekday=weekday, start_time=time(8), end_time=time(16)
            )
            for weekday in range(7)
        ]
    )
    db.commit()

    def override_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as test_client:
        test_client.test_ids = {
            "patient": patient.id,
            "doctor": doctor.id,
            "service": service.id,
            "site": site.id,
        }
        yield test_client
    app.dependency_overrides.clear()
    db.close()
    engine.dispose()


def login(client: TestClient, email: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "Password123!"})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}
