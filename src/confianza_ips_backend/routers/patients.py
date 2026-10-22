from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..audit import record_audit
from ..db import get_db
from ..models import Appointment, Patient, Role, User
from ..schemas import PatientCreate, PatientResponse, PatientUpdate
from ..security import CurrentUser, require_roles

router = APIRouter(prefix="/patients", tags=["Pacientes"])
staff = require_roles(Role.ADMIN, Role.RECEPTIONIST)
patient_reader = require_roles(Role.ADMIN, Role.RECEPTIONIST, Role.DOCTOR)


def _doctor_can_access_patient(db: Session, user: User, patient_id: int) -> bool:
    if user.role != Role.DOCTOR or user.doctor_id is None:
        return user.role != Role.DOCTOR
    return (
        db.scalar(
            select(Appointment.id)
            .where(
                Appointment.patient_id == patient_id,
                Appointment.doctor_id == user.doctor_id,
            )
            .limit(1)
        )
        is not None
    )


def _patient_query(db: Session, user: User, search: str | None, active: bool | None):
    query = select(Patient).order_by(Patient.last_name, Patient.first_name)
    if user.role == Role.DOCTOR:
        query = (
            query.join(Appointment, Appointment.patient_id == Patient.id)
            .where(Appointment.doctor_id == user.doctor_id)
            .distinct()
        )
    if active is not None:
        query = query.where(Patient.active == active)
    if search:
        term = f"%{search.strip()}%"
        query = query.where(
            or_(
                Patient.first_name.ilike(term),
                Patient.last_name.ilike(term),
                Patient.document_number.ilike(term),
            )
        )
    return query


@router.get("", response_model=list[PatientResponse])
def list_patients(
    user: User = Depends(patient_reader),
    db: Session = Depends(get_db),
    search: str | None = Query(default=None, max_length=80),
    active: bool | None = None,
) -> list[Patient]:
    return list(db.scalars(_patient_query(db, user, search, active)).all())


@router.post("", response_model=PatientResponse, status_code=status.HTTP_201_CREATED)
def create_patient(
    payload: PatientCreate, user: User = Depends(staff), db: Session = Depends(get_db)
) -> Patient:
    existing = db.scalar(
        select(Patient).where(
            Patient.document_type == payload.document_type,
            Patient.document_number == payload.document_number,
        )
    )
    if existing:
        raise HTTPException(status_code=409, detail="Ya existe un paciente con ese documento")
    patient = Patient(**payload.model_dump())
    db.add(patient)
    db.flush()
    record_audit(db, user, "create", "patient", patient.id, after=payload.model_dump(mode="json"))
    db.commit()
    db.refresh(patient)
    return patient


@router.get("/me", response_model=PatientResponse)
def get_my_patient(user: CurrentUser, db: Session = Depends(get_db)) -> Patient:
    if user.role != Role.PATIENT or not user.patient_id:
        raise HTTPException(status_code=403, detail="El usuario no es un paciente")
    patient = db.get(Patient, user.patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Paciente no encontrado")
    return patient


@router.patch("/me", response_model=PatientResponse)
def update_my_patient(
    payload: PatientUpdate, user: CurrentUser, db: Session = Depends(get_db)
) -> Patient:
    if user.role != Role.PATIENT or not user.patient_id:
        raise HTTPException(status_code=403, detail="El usuario no es un paciente")
    patient = db.get(Patient, user.patient_id)
    if not patient or not patient.active:
        raise HTTPException(status_code=404, detail="Paciente no encontrado")
    before = {field: getattr(patient, field) for field in payload.model_fields}
    for field, value in payload.model_dump().items():
        setattr(patient, field, value)
    record_audit(
        db, user, "update", "patient", patient.id, before=before, after=payload.model_dump()
    )
    db.commit()
    db.refresh(patient)
    return patient


@router.get("/{patient_id}", response_model=PatientResponse)
def get_patient(patient_id: int, user: CurrentUser, db: Session = Depends(get_db)) -> Patient:
    if user.role == Role.PATIENT and user.patient_id != patient_id:
        raise HTTPException(status_code=403, detail="No puede consultar este paciente")
    if user.role == Role.DOCTOR and not _doctor_can_access_patient(db, user, patient_id):
        raise HTTPException(status_code=403, detail="No puede consultar este paciente")
    patient = db.get(Patient, patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Paciente no encontrado")
    return patient


@router.put("/{patient_id}", response_model=PatientResponse)
def update_patient(
    patient_id: int,
    payload: PatientUpdate,
    user: User = Depends(staff),
    db: Session = Depends(get_db),
) -> Patient:
    patient = db.get(Patient, patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Paciente no encontrado")
    before = {field: getattr(patient, field) for field in payload.model_fields}
    for field, value in payload.model_dump().items():
        setattr(patient, field, value)
    record_audit(
        db, user, "update", "patient", patient.id, before=before, after=payload.model_dump()
    )
    db.commit()
    db.refresh(patient)
    return patient


@router.patch("/{patient_id}/status", response_model=PatientResponse)
def change_patient_status(
    patient_id: int,
    active: bool,
    user: User = Depends(require_roles(Role.ADMIN)),
    db: Session = Depends(get_db),
) -> Patient:
    patient = db.get(Patient, patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Paciente no encontrado")
    before = {"active": patient.active}
    patient.active = active
    record_audit(
        db,
        user,
        "activate" if active else "deactivate",
        "patient",
        patient.id,
        before=before,
        after={"active": active},
    )
    db.commit()
    db.refresh(patient)
    return patient
