from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from .api.exception_handlers import register_exception_handlers
from .config import get_settings
from .db import get_db
from .infrastructure.persistence.readiness import assert_database_ready
from .routers import admin as admin_router
from .routers import (
    agent,
    appointments,
    auth,
    authorizations,
    catalog,
    clinical,
    documents,
    patients,
    schedules,
    users,
)

settings = get_settings()

app = FastAPI(
    title="Confianza IPS API",
    version="0.1.0",
    description="API institucional ficticia para demostrar operaciones administrativas y clínicas.",
    docs_url="/docs" if settings.app_env != "production" else None,
    redoc_url="/redoc" if settings.app_env != "production" else None,
)
register_exception_handlers(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.get("/health", tags=["Sistema"])
def health() -> dict[str, str]:
    return {"status": "ok", "service": "confianza-ips-backend"}


@app.get("/health/ready", tags=["Sistema"])
def readiness(db: Session = Depends(get_db)) -> dict[str, str]:
    assert_database_ready(db)
    return {"status": "ready", "service": "confianza-ips-backend"}


app.include_router(auth.router, prefix="/api/v1")
app.include_router(patients.router, prefix="/api/v1")
app.include_router(catalog.router, prefix="/api/v1")
app.include_router(schedules.router, prefix="/api/v1")
app.include_router(appointments.router, prefix="/api/v1")
app.include_router(clinical.router, prefix="/api/v1")
app.include_router(admin_router.router, prefix="/api/v1")
app.include_router(authorizations.router, prefix="/api/v1")
app.include_router(documents.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")
app.include_router(agent.router, prefix="/api/v1")
