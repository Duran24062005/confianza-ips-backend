from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..audit import record_audit
from ..db import get_db
from ..models import Authorization, Patient, Role, Service, User
from ..schemas import AuthorizationCreate, AuthorizationResponse
from ..security import require_roles

router = APIRouter(prefix="/authorizations", tags=["Autorizaciones"])
staff = require_roles(Role.ADMIN, Role.RECEPTIONIST)


@router.get("", response_model=list[AuthorizationResponse])
def list_authorizations(
    _: User = Depends(staff), db: Session = Depends(get_db)
) -> list[Authorization]:
    return list(db.scalars(select(Authorization).order_by(Authorization.created_at.desc())).all())


@router.post("", response_model=AuthorizationResponse, status_code=status.HTTP_201_CREATED)
def create_authorization(
    payload: AuthorizationCreate, user: User = Depends(staff), db: Session = Depends(get_db)
) -> Authorization:
    if not db.get(Patient, payload.patient_id) or not db.get(Service, payload.service_id):
        raise HTTPException(status_code=404, detail="Paciente o servicio no encontrado")
    authorization = Authorization(**payload.model_dump(), created_by_user_id=user.id)
    db.add(authorization)
    db.flush()
    record_audit(db, user, "create", "authorization", authorization.id, after=payload.model_dump())
    db.commit()
    db.refresh(authorization)
    return authorization


@router.patch("/{authorization_id}/status", response_model=AuthorizationResponse)
def update_authorization_status(
    authorization_id: int,
    status_value: str,
    user: User = Depends(staff),
    db: Session = Depends(get_db),
) -> Authorization:
    authorization = db.get(Authorization, authorization_id)
    if not authorization:
        raise HTTPException(status_code=404, detail="Autorización no encontrada")
    if status_value not in {"requested", "approved", "rejected", "completed"}:
        raise HTTPException(status_code=422, detail="Estado de autorización inválido")
    before = {"status": authorization.status}
    authorization.status = status_value
    record_audit(
        db,
        user,
        "status_change",
        "authorization",
        authorization.id,
        before=before,
        after={"status": status_value},
    )
    db.commit()
    db.refresh(authorization)
    return authorization
