from typing import Protocol

from ..models import User


class UserReader(Protocol):
    """Port required by authentication to locate an account."""

    def find_by_email(self, email: str) -> User | None: ...
