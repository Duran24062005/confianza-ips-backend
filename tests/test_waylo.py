from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import jwt
from conftest import future_schedule_start, login

from confianza_ips_backend.application.services.waylo import (
    current_totp,
    verify_totp,
)
from confianza_ips_backend.config import get_settings
from confianza_ips_backend.routers import waylo as waylo_router


def waylo_request(client):
    code_response = client.get(
        "/api/v1/integrations/waylo/code",
        headers=login(client, "admin@confianza.demo"),
    )
    assert code_response.status_code == 200, code_response.text
    return {
        "full_name": "  ANA   PRUEBA ",
        "email": "PATIENT@CONFIANZA.DEMO",
        "code": code_response.json()["code"],
    }


def issue_waylo_token(client):
    response = client.post("/api/v1/integrations/waylo/token", json=waylo_request(client))
    assert response.status_code == 200, response.text
    return response.json()


def test_totp_matches_rfc6238_vector_and_accepts_adjacent_window() -> None:
    at = datetime.fromtimestamp(59, tz=timezone.utc)
    secret = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"
    assert current_totp(secret, 30, at) == "287082"
    assert verify_totp(secret, "287082", 30, at)
    assert verify_totp(secret, "287082", 30, at + timedelta(seconds=30))
    assert not verify_totp(secret, "287082", 30, at + timedelta(seconds=60))


def test_waylo_code_is_admin_only_and_does_not_expose_secret(client):
    response = client.get(
        "/api/v1/integrations/waylo/code",
        headers=login(client, "admin@confianza.demo"),
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body["code"]) == 6
    assert body["interval_seconds"] == 60
    assert "secret" not in body

    forbidden = client.get(
        "/api/v1/integrations/waylo/code",
        headers=login(client, "patient@confianza.demo"),
    )
    assert forbidden.status_code == 403


def test_waylo_token_returns_user_and_patient_and_is_scoped(client):
    issued = issue_waylo_token(client)
    assert issued["expires_in"] == 900
    assert issued["user"]["email"] == "patient@confianza.demo"
    assert issued["patient"]["first_name"] == "Ana"

    payload = jwt.decode(
        issued["access_token"],
        get_settings().waylo_jwt_secret,
        algorithms=["HS256"],
        audience="waylo",
    )
    assert payload["aud"] == "waylo"
    assert payload["scope"] == "waylo:read"
    assert payload["typ"] == "waylo"

    headers = {"Authorization": f"Bearer {issued['access_token']}"}
    profile = client.get("/api/v1/integrations/waylo/me", headers=headers)
    assert profile.status_code == 200
    assert profile.json()["patient"]["id"] == issued["patient"]["id"]
    assert client.get("/api/v1/integrations/waylo/appointments", headers=headers).status_code == 200

    internal_route = client.get("/api/v1/patients/me", headers=headers)
    assert internal_route.status_code == 401


def test_waylo_appointments_are_limited_to_the_linked_patient(client):
    admin_headers = login(client, "admin@confianza.demo")
    future = future_schedule_start(3).isoformat()
    created = client.post(
        "/api/v1/appointments",
        json={
            "patient_id": client.test_ids["patient"],
            "doctor_id": client.test_ids["doctor"],
            "service_id": client.test_ids["service"],
            "site_id": client.test_ids["site"],
            "starts_at": future,
        },
        headers=admin_headers,
    )
    assert created.status_code == 201, created.text

    issued = issue_waylo_token(client)
    headers = {"Authorization": f"Bearer {issued['access_token']}"}
    appointments = client.get("/api/v1/integrations/waylo/appointments", headers=headers)
    assert appointments.status_code == 200
    assert [item["id"] for item in appointments.json()] == [created.json()["id"]]
    history = client.get(
        f"/api/v1/integrations/waylo/appointments/{created.json()['id']}/history",
        headers=headers,
    )
    assert history.status_code == 200

    write_attempt = client.post(
        "/api/v1/appointments",
        json={
            "patient_id": client.test_ids["patient"],
            "doctor_id": client.test_ids["doctor"],
            "service_id": client.test_ids["service"],
            "site_id": client.test_ids["site"],
            "starts_at": future_schedule_start(5).isoformat(),
        },
        headers=headers,
    )
    assert write_attempt.status_code == 401


def test_waylo_invalid_credentials_are_generic_and_rate_limited(client):
    request = waylo_request(client)
    request["full_name"] = "Otra Persona"
    for _ in range(5):
        response = client.post("/api/v1/integrations/waylo/token", json=request)
        assert response.status_code == 401
        assert response.json()["detail"] == "Credenciales inválidas"

    limited = client.post("/api/v1/integrations/waylo/token", json=request)
    assert limited.status_code == 429
    assert "Retry-After" in limited.headers


def test_waylo_returns_503_when_not_configured(client, monkeypatch):
    monkeypatch.setattr(
        waylo_router,
        "get_settings",
        lambda: SimpleNamespace(waylo_totp_secret="", waylo_jwt_secret=""),
    )
    response = client.get(
        "/api/v1/integrations/waylo/code",
        headers=login(client, "admin@confianza.demo"),
    )
    assert response.status_code == 503


def test_waylo_token_rejects_non_patient_identity(client):
    request = waylo_request(client)
    request["email"] = "admin@confianza.demo"
    request["full_name"] = "Administración Confianza"
    response = client.post("/api/v1/integrations/waylo/token", json=request)
    assert response.status_code == 401
