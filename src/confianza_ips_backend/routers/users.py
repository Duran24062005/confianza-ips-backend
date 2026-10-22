from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..audit import record_audit
from ..db import get_db
from ..models import Doctor, Patient, Role, User
from ..schemas import UserCreate, UserResponse
from ..security import hash_password, require_roles

router = APIRouter(prefix="/users", tags=["Usuarios"])
admin = require_roles(Role.ADMIN)


@router.get("", response_model=list[UserResponse])
def list_users(_: User = Depends(admin), db: Session = Depends(get_db)) -> list[User]:
    return list(db.scalars(select(User).order_by(User.full_name)).all())


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate, actor: User = Depends(admin), db: Session = Depends(get_db)
) -> User:
    email = payload.email.lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(status_code=409, detail="Ya existe un usuario con ese correo")
    if payload.patient_id and not db.get(Patient, payload.patient_id):
        raise HTTPException(status_code=404, detail="Paciente no encontrado")
    if payload.doctor_id and not db.get(Doctor, payload.doctor_id):
        raise HTTPException(status_code=404, detail="Médico no encontrado")
    user = User(
        email=email,
        full_name=payload.full_name,
        password_hash=hash_password(payload.password),
        role=payload.role,
        patient_id=payload.patient_id,
        doctor_id=payload.doctor_id,
    )
    db.add(user)
    db.flush()
    record_audit(
        db, actor, "create", "user", user.id, after={"email": user.email, "role": str(user.role)}
    )
    db.commit()
    db.refresh(user)
    return user
