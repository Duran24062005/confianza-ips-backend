import json
from types import SimpleNamespace

import pytest
from sqlalchemy.exc import SQLAlchemyError

from confianza_ips_backend.application.exceptions import DatabaseNotReadyError
from confianza_ips_backend.audit import record_audit
from confianza_ips_backend.config import Settings
from confianza_ips_backend.infrastructure.persistence.readiness import assert_database_ready
from confianza_ips_backend.infrastructure.persistence.repositories import SqlAlchemyUserRepository


class FakeDatabase:
    def __init__(self, result=None, error: Exception | None = None) -> None:
        self.result = result
        self.error = error
        self.added = []
        self.executed = []

    def add(self, value) -> None:
        self.added.append(value)

    def execute(self, statement):
        self.executed.append(str(statement))
        if self.error:
            raise self.error
        return self.result

    def scalar(self, statement):
        self.executed.append(str(statement))
        return self.result


def test_settings_parse_multiple_cors_origins() -> None:
    settings = Settings(cors_origins="http://localhost:5173, https://demo.example")

    assert settings.cors_origins_list == ["http://localhost:5173", "https://demo.example"]


def test_record_audit_serializes_json_and_supports_system_events() -> None:
    db = FakeDatabase()
    actor = SimpleNamespace(id=4)

    event = record_audit(db, actor, "update", "user", 9, before={"name": "A"}, after={"name": "B"})
    system_event = record_audit(db, None, "read", "health", "ready", metadata={"source": "test"})

    assert event.actor_user_id == 4
    assert json.loads(event.before_json) == {"name": "A"}
    assert json.loads(event.after_json) == {"name": "B"}
    assert system_event.actor_user_id is None
    assert json.loads(system_event.metadata_json) == {"source": "test"}
    assert db.added == [event, system_event]


def test_readiness_checks_database_and_translates_sql_errors() -> None:
    ready_db = FakeDatabase()
    assert assert_database_ready(ready_db) is None
    assert len(ready_db.executed) == 2

    with pytest.raises(DatabaseNotReadyError):
        assert_database_ready(FakeDatabase(error=SQLAlchemyError("database unavailable")))


def test_user_repository_delegates_email_lookup_to_session() -> None:
    user = SimpleNamespace(email="admin@demo.test")
    db = FakeDatabase(result=user)

    result = SqlAlchemyUserRepository(db).find_by_email("admin@demo.test")

    assert result is user
    assert len(db.executed) == 1
