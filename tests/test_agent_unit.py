from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import jwt
import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from starlette.requests import Request

from confianza_ips_backend import security
from confianza_ips_backend.application.services.agent import (
    activation_digest,
    generate_activation_code,
    normalize_identity,
    verify_activation_code,
)
from confianza_ips_backend.db import Base
from confianza_ips_backend.models import AgentAuthAttempt, Patient, Role
from confianza_ips_backend.routers import agent
from confianza_ips_backend.schemas import AgentTokenRequest

AGENT_SECRET = "unit-agent-activation-secret"
AGENT_JWT_SECRET = "unit-agent-jwt-secret-with-at-least-32-characters"


def test_identity_normalization_is_case_insensitive_and_collapses_whitespace() -> None:
    assert normalize_identity("  EPS   Confianza FICTICIA ") == "eps confianza ficticia"


def test_activation_digest_verification_never_requires_plaintext_storage() -> None:
    digest = activation_digest("123456", AGENT_SECRET)

    assert digest != "123456"
    assert len(digest) == 64
    assert verify_activation_code("123456", digest, AGENT_SECRET)
    assert not verify_activation_code("654321", digest, AGENT_SECRET)
    assert not verify_activation_code("123456", digest, "another-secret")


def test_activation_code_generation_is_six_digits(monkeypatch) -> None:
    monkeypatch.setattr(
        "confianza_ips_backend.application.services.agent.secrets.randbelow",
        lambda _limit: 7,
    )

    assert generate_activation_code() == "000007"


def test_agent_token_request_normalizes_identity_fields() -> None:
    payload = AgentTokenRequest(
        document_type=" CC ",
        document_number=" 100   000 001 ",
        eps=" EPS   Confianza ",
        activation_code="123456",
    )

    assert payload.document_type == "CC"
    assert payload.document_number == "100 000 001"
    assert payload.eps == "EPS Confianza"


def test_agent_access_token_contains_explicit_scope_and_audience(monkeypatch) -> None:
    monkeypatch.setattr(
        security,
        "get_settings",
        lambda: SimpleNamespace(
            agent_jwt_secret=AGENT_JWT_SECRET,
            agent_token_expire_minutes=15,
        ),
    )
    user = SimpleNamespace(id=7, session_version=3)

    token, expires_in = security.create_agent_access_token(user)
    payload = jwt.decode(token, AGENT_JWT_SECRET, algorithms=["HS256"], audience="agent")

    assert expires_in == 900
    assert payload["sub"] == "7"
    assert payload["typ"] == "agent"
    assert payload["aud"] == "agent"
    assert payload["scope"] == "agent:patient"
    assert payload["session_version"] == 3


def test_agent_token_is_accepted_only_for_active_patient_and_internal_channel_rejects_it(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        security,
        "get_settings",
        lambda: SimpleNamespace(
            jwt_secret="unit-internal-secret-with-at-least-32-characters",
            agent_jwt_secret=AGENT_JWT_SECRET,
            agent_token_expire_minutes=15,
        ),
    )
    user = SimpleNamespace(
        id=7,
        patient_id=11,
        role=Role.PATIENT,
        active=True,
        session_version=3,
    )
    patient_record = SimpleNamespace(id=11, active=True)

    def get(model, _identifier):
        return patient_record if model is Patient else user

    db = SimpleNamespace(get=get)
    token, _ = security.create_agent_access_token(user)
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    request = Request({"type": "http", "headers": [], "client": ("127.0.0.1", 1)})

    assert security.get_current_user(credentials, db, request) is user
    assert request.state.auth_channel == "agent"
    with pytest.raises(HTTPException, match="Token inválido"):
        security.get_internal_user(credentials, db)

    patient_record.active = False
    with pytest.raises(HTTPException, match="Sesión no válida"):
        security.get_current_user(credentials, db)


def test_agent_token_rejects_wrong_scope_and_session_version(monkeypatch) -> None:
    monkeypatch.setattr(
        security,
        "get_settings",
        lambda: SimpleNamespace(
            jwt_secret="unit-internal-secret-with-at-least-32-characters",
            agent_jwt_secret=AGENT_JWT_SECRET,
            agent_token_expire_minutes=15,
        ),
    )
    user = SimpleNamespace(
        id=7,
        patient_id=11,
        role=Role.PATIENT,
        active=True,
        session_version=4,
    )
    patient_record = SimpleNamespace(id=11, active=True)
    db = SimpleNamespace(get=lambda model, _identifier: patient_record if model is Patient else user)

    wrong_scope = jwt.encode(
        {
            "sub": "7",
            "typ": "agent",
            "aud": "agent",
            "scope": "agent:admin",
            "session_version": 4,
            "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
        },
        AGENT_JWT_SECRET,
        algorithm="HS256",
    )
    with pytest.raises(HTTPException, match="Token inválido"):
        security.get_current_user(
            HTTPAuthorizationCredentials(scheme="Bearer", credentials=wrong_scope), db
        )

    expired_session = jwt.encode(
        {
            "sub": "7",
            "typ": "agent",
            "aud": "agent",
            "scope": "agent:patient",
            "session_version": 3,
            "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
        },
        AGENT_JWT_SECRET,
        algorithm="HS256",
    )
    with pytest.raises(HTTPException, match="Sesión no válida"):
        security.get_current_user(
            HTTPAuthorizationCredentials(scheme="Bearer", credentials=expired_session), db
        )


def test_rate_limit_counts_only_recent_failed_attempts() -> None:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        now = datetime.now(timezone.utc)
        fingerprint = agent._fingerprint("same-document", AGENT_SECRET)
        for _ in range(agent.RATE_LIMIT_MAX_ATTEMPTS):
            db.add(
                AgentAuthAttempt(
                    document_fingerprint=fingerprint,
                    eps_fingerprint="eps",
                    ip_fingerprint="ip",
                    client_fingerprint="client",
                    attempted_at=now,
                    succeeded=False,
                )
            )
        db.add(
            AgentAuthAttempt(
                document_fingerprint=fingerprint,
                eps_fingerprint="eps",
                ip_fingerprint="ip",
                client_fingerprint="client",
                attempted_at=now,
                succeeded=True,
            )
        )
        db.add(
            AgentAuthAttempt(
                document_fingerprint=fingerprint,
                eps_fingerprint="eps",
                ip_fingerprint="ip",
                client_fingerprint="client",
                attempted_at=now - timedelta(minutes=6),
                succeeded=False,
            )
        )
        db.commit()

        assert agent._is_rate_limited(
            db, ((AgentAuthAttempt.document_fingerprint, fingerprint),), now
        )

        db.query(AgentAuthAttempt).delete()
        db.commit()
        assert not agent._is_rate_limited(
            db, ((AgentAuthAttempt.document_fingerprint, fingerprint),), now
        )

    engine.dispose()


def test_missing_agent_configuration_is_rejected(monkeypatch) -> None:
    monkeypatch.setattr(
        agent,
        "get_settings",
        lambda: SimpleNamespace(
            agent_api_key="",
            agent_activation_secret="configured",
            agent_jwt_secret="configured",
        ),
    )

    with pytest.raises(HTTPException) as error:
        agent._require_configuration()

    assert error.value.status_code == 503
