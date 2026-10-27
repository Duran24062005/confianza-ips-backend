from confianza_ips_backend.models import Role


def registration_payload() -> dict[str, str]:
    return {
        "document_type": "CC",
        "document_number": "900000001",
        "first_name": "Lucía",
        "last_name": "Prueba",
        "birth_date": "1994-03-16",
        "email": "lucia.nueva@confianza.demo",
        "phone": "3000000123",
        "address": "Calle Demo 12",
        "city": "Bogotá",
        "eps": "EPS Confianza Ficticia",
        "emergency_name": "Contacto Prueba",
        "emergency_phone": "3000000456",
        "password": "Password123!",
    }


def test_public_registration_creates_a_patient_account_and_returns_a_session(client) -> None:
    response = client.post("/api/v1/auth/register", json=registration_payload())

    assert response.status_code == 201, response.text
    token = response.json()["access_token"]
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200, me.text
    assert me.json()["role"] == Role.PATIENT.value
    assert me.json()["patient_id"] is not None


def test_public_registration_rejects_duplicate_email_and_document(client) -> None:
    first = client.post("/api/v1/auth/register", json=registration_payload())
    assert first.status_code == 201, first.text

    duplicate_email = client.post("/api/v1/auth/register", json=registration_payload())
    assert duplicate_email.status_code == 409
    assert duplicate_email.json()["detail"] == "Ya existe un usuario con ese correo"

    different_email = {**registration_payload(), "email": "otra@confianza.demo"}
    duplicate_document = client.post("/api/v1/auth/register", json=different_email)
    assert duplicate_document.status_code == 409
    assert duplicate_document.json()["detail"] == "Ya existe un paciente con ese documento"
