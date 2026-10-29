import jwt
import pytest
from conftest import BUSINESS_TZ, future_schedule_start, login

from confianza_ips_backend.config import get_settings

pytestmark = pytest.mark.integration


def activation_code(client):
    response = client.post(
        "/api/v1/integrations/agent/activation-code",
        headers=login(client, "patient@confianza.demo"),
    )
    assert response.status_code == 200, response.text
    return response.json()


def agent_request(code: str, **overrides):
    payload = {
        "document_type": "CC",
        "document_number": "123",
        "eps": "EPS Test",
        "activation_code": code,
    }
    payload.update(overrides)
    return payload


def issue_agent_token(client):
    code = activation_code(client)
    response = client.post(
        "/api/v1/integrations/agent/token",
        json=agent_request(code["code"]),
        headers={"X-Confianza-Agent-Key": "test-agent-api-key"},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_activation_code_is_patient_only_and_single_use(client):
    code = activation_code(client)
    assert len(code["code"]) == 6
    assert code["expires_in"] == 300
    assert code["single_use"] is True

    forbidden = client.post(
        "/api/v1/integrations/agent/activation-code",
        headers=login(client, "admin@confianza.demo"),
    )
    assert forbidden.status_code == 403

    issued = client.post(
        "/api/v1/integrations/agent/token",
        json=agent_request(code["code"]),
        headers={"X-Confianza-Agent-Key": "test-agent-api-key"},
    )
    assert issued.status_code == 200, issued.text
    reused = client.post(
        "/api/v1/integrations/agent/token",
        json=agent_request(code["code"]),
        headers={"X-Confianza-Agent-Key": "test-agent-api-key"},
    )
    assert reused.status_code == 401


def test_generating_a_new_activation_code_revokes_the_previous_one(client):
    previous = activation_code(client)
    current = activation_code(client)

    revoked = client.post(
        "/api/v1/integrations/agent/token",
        json=agent_request(previous["code"]),
        headers={"X-Confianza-Agent-Key": "test-agent-api-key"},
    )
    assert revoked.status_code == 401

    issued = client.post(
        "/api/v1/integrations/agent/token",
        json=agent_request(current["code"]),
        headers={"X-Confianza-Agent-Key": "test-agent-api-key"},
    )
    assert issued.status_code == 200, issued.text


def test_activation_code_requires_an_active_patient(client):
    admin_headers = login(client, "admin@confianza.demo")
    deactivated = client.patch("/api/v1/patients/1/status?active=false", headers=admin_headers)
    assert deactivated.status_code == 200

    response = client.post(
        "/api/v1/integrations/agent/activation-code",
        headers=login(client, "patient@confianza.demo"),
    )
    assert response.status_code == 403


def test_agent_token_has_patient_scope_and_uses_internal_patient_routes(client):
    issued = issue_agent_token(client)
    payload = jwt.decode(
        issued["access_token"],
        get_settings().agent_jwt_secret,
        algorithms=["HS256"],
        audience="agent",
    )
    assert payload["aud"] == "agent"
    assert payload["scope"] == "agent:patient"
    assert payload["typ"] == "agent"
    assert issued["expires_in"] == 30 * 24 * 60 * 60
    assert issued["identity"] == {
        "user_id": 2,
        "patient_id": 1,
        "full_name": "Ana Prueba",
        "eps": "EPS Test",
    }

    headers = {"Authorization": f"Bearer {issued['access_token']}"}
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 200
    assert client.get("/api/v1/patients/me", headers=headers).status_code == 200
    assert client.get("/api/v1/appointments", headers=headers).status_code == 200
    assert client.get("/api/v1/dashboard/analytics?days=7", headers=headers).status_code == 200
    assert client.get("/api/v1/patients?active=true", headers=headers).status_code == 403
    assert client.get("/api/v1/audit", headers=headers).status_code == 403


def test_agent_can_find_create_reschedule_and_cancel_own_appointment(client):
    issued = issue_agent_token(client)
    headers = {"Authorization": f"Bearer {issued['access_token']}"}
    starts_at = future_schedule_start(3)
    availability = client.get(
        f"/api/v1/availability?doctor_id=1&service_id=1&date={starts_at.astimezone(BUSINESS_TZ).date().isoformat()}",
        headers=headers,
    )
    assert availability.status_code == 200, availability.text
    assert availability.json()

    created = client.post(
        "/api/v1/appointments",
        json={
            "patient_id": 999,
            "doctor_id": 1,
            "service_id": 1,
            "site_id": 1,
            "starts_at": starts_at.isoformat(),
            "reason": "Solicitud desde el agente",
        },
        headers=headers,
    )
    assert created.status_code == 201, created.text
    assert created.json()["patient_id"] == 1

    rescheduled = client.post(
        f"/api/v1/appointments/{created.json()['id']}/reschedule",
        json={
            "starts_at": future_schedule_start(6).isoformat(),
            "reason": "Cambio de horario desde el agente",
        },
        headers=headers,
    )
    assert rescheduled.status_code == 200, rescheduled.text
    assert rescheduled.json()["starts_at"] != starts_at.isoformat()

    cancelled = client.post(
        f"/api/v1/appointments/{rescheduled.json()['id']}/status",
        json={"status": "cancelled", "reason": "Cancelación desde el agente"},
        headers=headers,
    )
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["status"] == "cancelled"


def test_agent_token_rejects_wrong_identity_and_api_key(client):
    code = activation_code(client)
    wrong_eps = client.post(
        "/api/v1/integrations/agent/token",
        json=agent_request(code["code"], eps="Otra EPS"),
        headers={"X-Confianza-Agent-Key": "test-agent-api-key"},
    )
    assert wrong_eps.status_code == 401
    wrong_key = client.post(
        "/api/v1/integrations/agent/token",
        json=agent_request(code["code"]),
        headers={"X-Confianza-Agent-Key": "otra-clave"},
    )
    assert wrong_key.status_code == 401


def test_agent_exchange_is_rate_limited(client):
    code = activation_code(client)
    request = agent_request(code["code"], eps="Otra EPS")
    headers = {"X-Confianza-Agent-Key": "test-agent-api-key"}
    for _ in range(5):
        response = client.post("/api/v1/integrations/agent/token", json=request, headers=headers)
        assert response.status_code == 401

    limited = client.post("/api/v1/integrations/agent/token", json=request, headers=headers)
    assert limited.status_code == 429
    assert "Retry-After" in limited.headers


def test_agent_token_is_invalid_after_patient_deactivation(client):
    issued = issue_agent_token(client)
    admin_headers = login(client, "admin@confianza.demo")
    deactivated = client.patch(
        "/api/v1/patients/1/status?active=false", headers=admin_headers
    )
    assert deactivated.status_code == 200

    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {issued['access_token']}"},
    )
    assert response.status_code == 401
