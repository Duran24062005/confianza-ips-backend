from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..api.dependencies import AuthenticationServiceDependency
from ..audit import record_audit
from ..db import get_db
from ..models import Patient, Role, User
from ..schemas import (
    LoginRequest,
    PatientRegistrationRequest,
    TokenResponse,
    UserResponse,
    UserUpdate,
)
from ..security import CurrentUser, auth_metadata, hash_password, is_agent_request

router = APIRouter(prefix="/auth", tags=["Autenticación"])


@router.post("/login", response_model=TokenResponse)
def login(
    payload: LoginRequest,
    authentication: AuthenticationServiceDependency,
) -> TokenResponse:
    result = authentication.login(payload.email, payload.password)
    return TokenResponse(access_token=result.access_token, expires_in=result.expires_in)


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(
    payload: PatientRegistrationRequest,
    request: Request,
    authentication: AuthenticationServiceDependency,
    db: Session = Depends(get_db),
) -> TokenResponse:
    """Create a synthetic patient and its patient-only account for the demo."""
    email = payload.email.lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Ya existe un usuario con ese correo"
        )
    if db.scalar(
        select(Patient).where(
            Patient.document_type == payload.document_type,
            Patient.document_number == payload.document_number,
        )
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe un paciente con ese documento",
        )

    patient = Patient(**payload.model_dump(exclude={"password"}))
    patient.email = email
    db.add(patient)
    db.flush()

    user = User(
        email=email,
        full_name=f"{patient.first_name.strip()} {patient.last_name.strip()}",
        password_hash=hash_password(payload.password),
        role=Role.PATIENT,
        patient_id=patient.id,
    )
    db.add(user)
    db.flush()
    record_audit(
        db,
        user,
        "register",
        "user",
        user.id,
        after={"email": user.email, "role": str(user.role), "patient_id": patient.id},
        metadata=auth_metadata(request),
    )
    db.commit()

    result = authentication.login(email, payload.password)
    return TokenResponse(access_token=result.access_token, expires_in=result.expires_in)


@router.get("/me", response_model=UserResponse)
def me(user: CurrentUser) -> User:
    return user


@router.patch("/me", response_model=UserResponse)
def update_me(
    payload: UserUpdate, user: CurrentUser, request: Request, db: Session = Depends(get_db)
) -> User:
    before = {"full_name": user.full_name}
    user.full_name = payload.full_name.strip()
    record_audit(
        db,
        user,
        "update",
        "user",
        user.id,
        before=before,
        after={"full_name": user.full_name},
        metadata=auth_metadata(request),
    )
    db.commit()
    db.refresh(user)
    return user


@router.post("/logout")
def logout(
    user: CurrentUser,
    request: Request,
    authentication: AuthenticationServiceDependency,
) -> dict[str, str]:
    if is_agent_request(request):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="El token del agente no puede cerrar la sesión interna",
        )
    authentication.logout(user)
    return {"message": "Sesión cerrada"}
