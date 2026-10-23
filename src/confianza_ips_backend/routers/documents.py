from html import escape

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from ..audit import record_audit
from ..db import get_db
from ..models import Appointment, Document, Patient, Role
from ..schemas import DocumentResponse
from ..security import CurrentUser, auth_metadata

router = APIRouter(prefix="/documents", tags=["Documentos ficticios"])


@router.post(
    "/appointments/{appointment_id}/confirmation",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_appointment_confirmation(
    appointment_id: int,
    user: CurrentUser,
    request: Request,
    db: Session = Depends(get_db),
) -> Document:
    appointment = db.get(Appointment, appointment_id)
    if not appointment:
        raise HTTPException(status_code=404, detail="Cita no encontrada")
    allowed = (
        user.role in (Role.ADMIN, Role.RECEPTIONIST) or user.patient_id == appointment.patient_id
    )
    if not allowed:
        raise HTTPException(status_code=403, detail="No puede generar este documento")
    patient = db.get(Patient, appointment.patient_id)
    content = (
        "DOCUMENTO DE DEMOSTRACIÓN — SIN VALIDEZ INSTITUCIONAL REAL\n\n"
        f"Paciente: {escape(patient.first_name + ' ' + patient.last_name)}\n"
        f"Cita: {appointment.starts_at.isoformat()}\n"
        f"Estado: {appointment.status.value if hasattr(appointment.status, 'value') else appointment.status}\n"
    )
    document = Document(
        patient_id=patient.id,
        appointment_id=appointment.id,
        document_type="appointment_confirmation",
        title="Constancia ficticia de cita",
        content=content,
        created_by_user_id=user.id,
    )
    db.add(document)
    db.flush()
    record_audit(
        db,
        user,
        "create",
        "document",
        document.id,
        after={"appointment_id": appointment.id},
        metadata=auth_metadata(request),
    )
    db.commit()
    db.refresh(document)
    return document
