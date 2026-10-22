from types import SimpleNamespace

import pytest
from sqlalchemy.exc import ProgrammingError

from confianza_ips_backend.application.exceptions import (
    DatabaseNotReadyError,
    InvalidCredentialsError,
)
from confianza_ips_backend.application.services import authentication as authentication_module
from confianza_ips_backend.application.services.authentication import AuthenticationService


class FakeDatabase:
    def __init__(self) -> None:
        self.commit_count = 0
        self.rollback_count = 0

    def commit(self) -> None:
        self.commit_count += 1

    def rollback(self) -> None:
        self.rollback_count += 1


class FakeUsers:
    def __init__(self, user=None, error: Exception | None = None) -> None:
        self.user = user
        self.error = error

    def find_by_email(self, _email: str):
        if self.error:
            raise self.error
        return self.user


def demo_user():
    return SimpleNamespace(
        id=1,
        active=True,
        password_hash="hashed-password",
        session_version=0,
    )


def test_login_returns_token_and_audits_authenticated_user(monkeypatch) -> None:
    db = FakeDatabase()
    user = demo_user()
    audit = []
    monkeypatch.setattr(authentication_module, "verify_password", lambda *_args: True)
    monkeypatch.setattr(
        authentication_module, "create_access_token", lambda _user: ("access-token", 900)
    )
    monkeypatch.setattr(
        authentication_module,
        "record_audit",
        lambda *_args, **_kwargs: audit.append("login"),
    )

    result = AuthenticationService(FakeUsers(user), db).login("ADMIN@DEMO.COM", "password")

    assert result.access_token == "access-token"
    assert result.expires_in == 900
    assert audit == ["login"]
    assert db.commit_count == 1


def test_login_rejects_invalid_credentials_without_committing(monkeypatch) -> None:
    db = FakeDatabase()
    monkeypatch.setattr(authentication_module, "verify_password", lambda *_args: False)

    with pytest.raises(InvalidCredentialsError):
        AuthenticationService(FakeUsers(demo_user()), db).login("user@demo.com", "wrong")

    assert db.commit_count == 0
    assert db.rollback_count == 0


def test_login_translates_missing_schema_into_database_not_ready() -> None:
    db = FakeDatabase()
    error = ProgrammingError("SELECT", {}, RuntimeError("relation users does not exist"))

    with pytest.raises(DatabaseNotReadyError):
        AuthenticationService(FakeUsers(error=error), db).login("user@demo.com", "password")

    assert db.rollback_count == 1
