from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ...application.exceptions import DatabaseNotReadyError


def assert_database_ready(db: Session) -> None:
    """Checks connectivity and the minimum schema required by the API."""
    try:
        db.execute(text("SELECT 1"))
        db.execute(text("SELECT 1 FROM users LIMIT 1"))
    except SQLAlchemyError as exc:
        raise DatabaseNotReadyError from exc
