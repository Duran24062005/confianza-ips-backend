import pytest
from pydantic import ValidationError

from confianza_ips_backend.schemas import ServiceCreate, UserUpdate


def test_user_update_normalizes_whitespace() -> None:
    assert UserUpdate(full_name="  Ana   María  ").full_name == "Ana María"


@pytest.mark.parametrize("value", ["", " ", "A", "x" * 161])
def test_user_update_rejects_invalid_names(value: str) -> None:
    with pytest.raises(ValidationError):
        UserUpdate(full_name=value)


def test_service_create_applies_safe_duration_default_and_bounds() -> None:
    assert ServiceCreate(name="Consulta").duration_minutes == 30
    assert ServiceCreate(name="Consulta", duration_minutes=240).duration_minutes == 240

    with pytest.raises(ValidationError):
        ServiceCreate(name="Consulta", duration_minutes=9)
