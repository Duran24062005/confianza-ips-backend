from dataclasses import dataclass

from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.orm import Session

from ...audit import record_audit
from ...models import User
from ...security import create_access_token, verify_password
from ..exceptions import DatabaseNotReadyError, InvalidCredentialsError
from ..ports import UserReader


@dataclass(frozen=True)
class AuthenticationResult:
    access_token: str
    expires_in: int


class AuthenticationService:
    """Coordinates login and logout without exposing persistence to the router."""

    def __init__(self, users: UserReader, db: Session) -> None:
        self._users = users
        self._db = db

    def login(self, email: str, password: str) -> AuthenticationResult:
        try:
            user = self._users.find_by_email(email.lower())
            if not user or not user.active or not verify_password(password, user.password_hash):
                raise InvalidCredentialsError
            token, expires_in = create_access_token(user)
            record_audit(self._db, user, "login", "user", user.id)
            self._db.commit()
        except InvalidCredentialsError:
            raise
        except (OperationalError, ProgrammingError) as exc:
            self._db.rollback()
            raise DatabaseNotReadyError from exc
        return AuthenticationResult(access_token=token, expires_in=expires_in)

    def logout(self, user: User) -> None:
        try:
            user.session_version += 1
            record_audit(self._db, user, "logout", "user", user.id)
            self._db.commit()
        except (OperationalError, ProgrammingError) as exc:
            self._db.rollback()
            raise DatabaseNotReadyError from exc
