import pytest
from conftest import future_schedule_start, login

pytestmark = pytest.mark.integration


def patient_payload(document_number: str) -> dict[str, str]:
    return {
        "document_type": "CC",
        "document_number": document_number,
        "first_name": "Paciente",
        "last_name": "No Autorizado",
        "birth_date": "1992-05-12",
        "email": f"{document_number}@confianza.demo",
        "phone": "3100000000",
        "address": "Calle 1 # 2-3",
        "city": "Bogotá",
        "eps": "EPS Test",
        "emergency_name": "Contacto Test",
        "emergency_phone": "3200000000",
    }


def create_doctor_appointment(client, patient_id: int) -> int:
    starts_at = future_schedule_start()
    response = client.post(
        "/api/v1/appointments",
        json={
            "patient_id": patient_id,
            "doctor_id": client.test_ids["doctor"],
            "service_id": client.test_ids["service"],
            "site_id": client.test_ids["site"],
            "starts_at": starts_at.isoformat(),
            "reason": "Consulta autorizada",
        },
        headers=login(client, "admin@confianza.demo"),
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_doctor_patient_access_is_scoped_to_own_appointments(client):
    unrelated = client.post(
        "/api/v1/patients",
        json=patient_payload("999999999"),
        headers=login(client, "admin@confianza.demo"),
    )
    assert unrelated.status_code == 201, unrelated.text
    unrelated_id = unrelated.json()["id"]
    create_doctor_appointment(client, client.test_ids["patient"])

    doctor_headers = login(client, "doctor@confianza.demo")
    listed = client.get("/api/v1/patients?active=true", headers=doctor_headers)
    assert listed.status_code == 200, listed.text
    assert [patient["id"] for patient in listed.json()] == [client.test_ids["patient"]]

    own = client.get(f"/api/v1/patients/{client.test_ids['patient']}", headers=doctor_headers)
    assert own.status_code == 200, own.text
    forbidden = client.get(f"/api/v1/patients/{unrelated_id}", headers=doctor_headers)
    assert forbidden.status_code == 403


def test_patient_cannot_use_the_staff_patient_collection(client):
    response = client.get(
        "/api/v1/patients?active=true",
        headers=login(client, "patient@confianza.demo"),
    )
    assert response.status_code == 403
