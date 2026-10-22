from sqlalchemy import select
from sqlalchemy.orm import Session

from ...models import User


class SqlAlchemyUserRepository:
    """Persistence adapter used by the authentication application service."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def find_by_email(self, email: str) -> User | None:
        return self._db.scalar(select(User).where(User.email == email))
