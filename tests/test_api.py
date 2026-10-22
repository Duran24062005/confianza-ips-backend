from datetime import datetime, timedelta, timezone

from conftest import login

from confianza_ips_backend.api.dependencies import get_authentication_service
from confianza_ips_backend.application.exceptions import DatabaseNotReadyError
from confianza_ips_backend.main import app


def test_health_and_auth(client):
    assert client.get("/health").json()["status"] == "ok"
    assert client.get("/health/ready").json()["status"] == "ready"
    headers = login(client, "admin@confianza.demo")
    response = client.get("/api/v1/auth/me", headers=headers)
    assert response.status_code == 200
    assert response.json()["role"] == "admin"


def test_login_returns_503_when_database_is_not_ready(client):
    class BrokenAuthenticationService:
        def login(self, email: str, password: str):
            raise DatabaseNotReadyError

    app.dependency_overrides[get_authentication_service] = lambda: BrokenAuthenticationService()
    try:
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "admin@confianza.demo", "password": "Password123!"},
        )
    finally:
        app.dependency_overrides.pop(get_authentication_service, None)
    assert response.status_code == 503
    assert response.json()["code"] == "DATABASE_NOT_READY"


def test_patient_can_only_read_own_profile(client):
    headers = login(client, "patient@confianza.demo")
    own = client.get("/api/v1/patients/me", headers=headers)
    assert own.status_code == 200
    other = client.get("/api/v1/patients/999", headers=headers)
    assert other.status_code == 403


def test_admin_can_deactivate_patient_and_audit_it(client):
    headers = login(client, "admin@confianza.demo")
    patient_id = client.test_ids["patient"]
    response = client.patch(f"/api/v1/patients/{patient_id}/status?active=false", headers=headers)
    assert response.status_code == 200
    assert response.json()["active"] is False
    audit = client.get("/api/v1/audit", headers=headers)
    assert audit.status_code == 200
    assert any(
        event["resource_type"] == "patient" and event["action"] == "deactivate"
        for event in audit.json()
    )


def test_patient_request_is_always_scoped_to_own_patient(client):
    headers = login(client, "patient@confianza.demo")
    future = (datetime.now(timezone.utc) + timedelta(days=3)).isoformat()
    payload = {
        "patient_id": 999,
        "doctor_id": client.test_ids["doctor"],
        "service_id": client.test_ids["service"],
        "site_id": client.test_ids["site"],
        "starts_at": future,
    }
    response = client.post("/api/v1/appointments", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    assert response.json()["patient_id"] == client.test_ids["patient"]


def test_admin_can_create_and_cancel_appointment(client):
    headers = login(client, "admin@confianza.demo")
    future = (datetime.now(timezone.utc) + timedelta(days=3)).isoformat()
    payload = {
        "patient_id": client.test_ids["patient"],
        "doctor_id": client.test_ids["doctor"],
        "service_id": client.test_ids["service"],
        "site_id": client.test_ids["site"],
        "starts_at": future,
        "reason": "Control de prueba",
    }
    created = client.post("/api/v1/appointments", json=payload, headers=headers)
    assert created.status_code == 201, created.text
    appointment_id = created.json()["id"]
    cancelled = client.post(
        f"/api/v1/appointments/{appointment_id}/status",
        json={"status": "cancelled", "reason": "Prueba de cancelación"},
        headers=headers,
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"
    history = client.get(f"/api/v1/appointments/{appointment_id}/history", headers=headers)
    assert history.status_code == 200
    assert [event["to_status"] for event in history.json()] == ["confirmed", "cancelled"]


def test_occupied_slot_returns_conflict(client):
    headers = login(client, "admin@confianza.demo")
    future = (datetime.now(timezone.utc) + timedelta(days=3)).isoformat()
    payload = {
        "patient_id": client.test_ids["patient"],
        "doctor_id": client.test_ids["doctor"],
        "service_id": client.test_ids["service"],
        "site_id": client.test_ids["site"],
        "starts_at": future,
    }
    first = client.post("/api/v1/appointments", json=payload, headers=headers)
    second = client.post("/api/v1/appointments", json=payload, headers=headers)
    assert first.status_code == 201
    assert second.status_code == 409
