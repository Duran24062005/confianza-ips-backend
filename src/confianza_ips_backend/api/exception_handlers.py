import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError, ProgrammingError

from ..application.exceptions import DatabaseNotReadyError, InvalidCredentialsError

logger = logging.getLogger(__name__)
DATABASE_NOT_READY_DETAIL = (
    "La base de datos no está disponible o no tiene las migraciones aplicadas. "
    "Ejecuta `uv run alembic upgrade head` antes de iniciar el servicio."
)


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(DatabaseNotReadyError, database_not_ready_handler)
    app.add_exception_handler(InvalidCredentialsError, invalid_credentials_handler)
    app.add_exception_handler(OperationalError, database_error_handler)
    app.add_exception_handler(ProgrammingError, database_error_handler)


async def invalid_credentials_handler(
    _request: Request, _exc: InvalidCredentialsError
) -> JSONResponse:
    return JSONResponse(
        status_code=401,
        headers={"WWW-Authenticate": "Bearer"},
        content={"detail": "Credenciales inválidas"},
    )


async def database_not_ready_handler(_request: Request, exc: DatabaseNotReadyError) -> JSONResponse:
    logger.warning("Database readiness check failed: %s", exc.__cause__ or exc)
    return JSONResponse(
        status_code=503,
        content={"code": "DATABASE_NOT_READY", "detail": DATABASE_NOT_READY_DETAIL},
    )


async def database_error_handler(_request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Database operation failed", exc_info=exc)
    return JSONResponse(
        status_code=503,
        content={"code": "DATABASE_NOT_READY", "detail": DATABASE_NOT_READY_DETAIL},
    )
