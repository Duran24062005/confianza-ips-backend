from types import SimpleNamespace

import jwt
import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from confianza_ips_backend import security
from confianza_ips_backend.domain.types import Role


def test_password_hash_round_trip() -> None:
    hashed = security.hash_password("Confianza123!")

    assert hashed != "Confianza123!"
    assert security.verify_password("Confianza123!", hashed)
    assert not security.verify_password("otra-clave", hashed)


def test_access_token_contains_identity_and_expiration(monkeypatch) -> None:
    monkeypatch.setattr(
        security, "get_settings", lambda: SimpleNamespace(jwt_secret="test-secret-with-at-least-32-characters", jwt_expire_minutes=30)
    )
    user = SimpleNamespace(id=7, role=Role.DOCTOR, session_version=3)

    token, expires_in = security.create_access_token(user)
    payload = jwt.decode(token, "test-secret-with-at-least-32-characters", algorithms=["HS256"])

    assert expires_in == 1800
    assert payload["sub"] == "7"
    assert payload["role"] == "doctor"
    assert payload["session_version"] == 3


def test_agent_token_is_scoped_to_an_active_patient_and_marks_the_request_channel(monkeypatch) -> None:
    monkeypatch.setattr(
        security,
        "get_settings",
        lambda: SimpleNamespace(
            jwt_secret="test-secret-with-at-least-32-characters",
            jwt_expire_minutes=30,
            agent_jwt_secret="agent-secret-with-at-least-32-characters",
            agent_token_expire_minutes=15,
        ),
    )
    user = SimpleNamespace(id=7, role=Role.PATIENT, patient_id=12, active=True, session_version=3)
    patient = SimpleNamespace(id=12, active=True)
    db = SimpleNamespace(get=lambda _model, identifier: patient if identifier == 12 else user)
    request = SimpleNamespace(state=SimpleNamespace())
    token, expires_in = security.create_agent_access_token(user)

    result = security.get_current_user(
        HTTPAuthorizationCredentials(scheme="Bearer", credentials=token),
        db,
        request,
    )

    assert result is user
    assert expires_in == 900
    assert request.state.auth_channel == "agent"
    assert security.is_agent_request(request)
    assert security.auth_metadata(request, source="test") == {"channel": "agent", "source": "test"}


def test_internal_channel_rejects_agent_tokens_and_stale_sessions(monkeypatch) -> None:
    monkeypatch.setattr(
        security,
        "get_settings",
        lambda: SimpleNamespace(
            jwt_secret="test-secret-with-at-least-32-characters",
            jwt_expire_minutes=30,
            agent_jwt_secret="agent-secret-with-at-least-32-characters",
            agent_token_expire_minutes=15,
        ),
    )
    user = SimpleNamespace(id=7, role=Role.DOCTOR, patient_id=None, active=True, session_version=3)
    db = SimpleNamespace(get=lambda _model, _identifier: user)
    normal_token, _ = security.create_access_token(user)
    agent_token, _ = security.create_agent_access_token(user)

    with pytest.raises(HTTPException, match="Token inválido"):
        security.get_internal_user(
            HTTPAuthorizationCredentials(scheme="Bearer", credentials=agent_token),
            db,
        )

    stale_user = SimpleNamespace(id=7, role=Role.DOCTOR, patient_id=None, active=True, session_version=4)
    stale_db = SimpleNamespace(get=lambda _model, _identifier: stale_user)
    with pytest.raises(HTTPException, match="Sesión no válida"):
        security.get_internal_user(
            HTTPAuthorizationCredentials(scheme="Bearer", credentials=normal_token),
            stale_db,
        )


def test_agent_token_cannot_access_an_inactive_patient(monkeypatch) -> None:
    monkeypatch.setattr(
        security,
        "get_settings",
        lambda: SimpleNamespace(
            jwt_secret="test-secret-with-at-least-32-characters",
            jwt_expire_minutes=30,
            agent_jwt_secret="agent-secret-with-at-least-32-characters",
            agent_token_expire_minutes=15,
        ),
    )
    user = SimpleNamespace(id=7, role=Role.PATIENT, patient_id=12, active=True, session_version=3)
    inactive_patient = SimpleNamespace(id=12, active=False)
    db = SimpleNamespace(get=lambda _model, identifier: inactive_patient if identifier == 12 else user)
    token, _ = security.create_agent_access_token(user)

    with pytest.raises(HTTPException, match="Sesión no válida"):
        security.get_current_user(
            HTTPAuthorizationCredentials(scheme="Bearer", credentials=token),
            db,
        )


def test_get_current_user_rejects_missing_and_invalid_credentials(monkeypatch) -> None:
    monkeypatch.setattr(
        security, "get_settings", lambda: SimpleNamespace(jwt_secret="test-secret-with-at-least-32-characters", jwt_expire_minutes=30)
    )
    db = SimpleNamespace(get=lambda _model, _user_id: None)

    with pytest.raises(HTTPException, match="Autenticación requerida"):
        security.get_current_user(None, db)

    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="not-a-token")
    with pytest.raises(HTTPException, match="Token inválido"):
        security.get_current_user(credentials, db)


def test_role_dependency_allows_only_configured_roles() -> None:
    dependency = security.require_roles(Role.ADMIN)
    admin = SimpleNamespace(role=Role.ADMIN)
    receptionist = SimpleNamespace(role=Role.RECEPTIONIST)

    assert dependency(admin) is admin
    with pytest.raises(HTTPException, match="Permisos insuficientes"):
        dependency(receptionist)
