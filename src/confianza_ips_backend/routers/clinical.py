from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..audit import record_audit
from ..db import get_db
from ..models import (
    Appointment,
    AppointmentStatus,
    ClinicalEncounter,
    ClinicalNote,
    Role,
)
from ..schemas import ClinicalEncounterCreate, ClinicalEncounterResponse, ClinicalNoteResponse
from ..security import CurrentUser

router = APIRouter(prefix="/clinical", tags=["Historia clínica simulada"])


@router.post("/appointments/{appointment_id}/encounter", response_model=ClinicalEncounterResponse)
def create_encounter(
    appointment_id: int,
    payload: ClinicalEncounterCreate,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> ClinicalEncounter:
    if user.role != Role.DOCTOR:
        raise HTTPException(status_code=403, detail="Solo un médico puede registrar la atención")
    appointment = db.get(Appointment, appointment_id)
    if not appointment or appointment.doctor_id != user.doctor_id:
        raise HTTPException(status_code=404, detail="Atención no encontrada")
    if appointment.status != AppointmentStatus.COMPLETED:
        raise HTTPException(status_code=409, detail="La cita debe estar completada")
    if db.scalar(
        select(ClinicalEncounter).where(ClinicalEncounter.appointment_id == appointment_id)
    ):
        raise HTTPException(status_code=409, detail="La atención ya tiene historia clínica")
    encounter = ClinicalEncounter(
        appointment_id=appointment.id,
        patient_id=appointment.patient_id,
        doctor_id=appointment.doctor_id,
    )
    db.add(encounter)
    db.flush()
    note = ClinicalNote(
        encounter_id=encounter.id,
        version=1,
        note_type="evolution",
        content=f"Motivo: {payload.reason}\nObservación: {payload.observation}\nEvolución: {payload.evolution}",
        created_by_user_id=user.id,
    )
    db.add(note)
    record_audit(db, user, "create", "clinical_encounter", encounter.id, after=payload.model_dump())
    db.commit()
    db.refresh(encounter)
    return encounter


@router.get("/patients/{patient_id}", response_model=list[ClinicalNoteResponse])
def list_patient_notes(
    patient_id: int, user: CurrentUser, db: Session = Depends(get_db)
) -> list[ClinicalNote]:
    if user.role == Role.PATIENT and user.patient_id != patient_id:
        raise HTTPException(status_code=403, detail="No puede consultar esta historia")
    if user.role not in (Role.ADMIN, Role.DOCTOR, Role.PATIENT):
        raise HTTPException(status_code=403, detail="Permisos insuficientes")
    if user.role == Role.DOCTOR:
        query = (
            select(ClinicalNote)
            .join(ClinicalEncounter)
            .where(
                ClinicalEncounter.patient_id == patient_id,
                ClinicalEncounter.doctor_id == user.doctor_id,
            )
        )
    else:
        query = (
            select(ClinicalNote)
            .join(ClinicalEncounter)
            .where(ClinicalEncounter.patient_id == patient_id)
        )
    return list(db.scalars(query.order_by(ClinicalNote.created_at.desc())).all())
