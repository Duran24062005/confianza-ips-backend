from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..audit import record_audit
from ..db import get_db
from ..models import Doctor, DoctorService, DoctorSpecialty, Role, Service, Site, Specialty, User
from ..schemas import (
    DoctorCreate,
    DoctorResponse,
    DoctorStatusChange,
    ServiceCreate,
    ServiceResponse,
    SiteResponse,
    SpecialtyCreate,
    SpecialtyResponse,
)
from ..security import CurrentUser, require_roles

router = APIRouter(tags=["Catálogos"])
admin = require_roles(Role.ADMIN)


@router.get("/sites", response_model=list[SiteResponse])
def list_sites(_: CurrentUser, db: Session = Depends(get_db)) -> list[Site]:
    return list(db.scalars(select(Site).where(Site.active.is_(True)).order_by(Site.name)).all())


@router.get("/specialties", response_model=list[SpecialtyResponse])
def list_specialties(_: CurrentUser, db: Session = Depends(get_db)) -> list[Specialty]:
    return list(
        db.scalars(
            select(Specialty).where(Specialty.active.is_(True)).order_by(Specialty.name)
        ).all()
    )


@router.post("/specialties", response_model=SpecialtyResponse, status_code=status.HTTP_201_CREATED)
def create_specialty(
    payload: SpecialtyCreate, user: User = Depends(admin), db: Session = Depends(get_db)
) -> Specialty:
    specialty = Specialty(name=payload.name.strip())
    db.add(specialty)
    db.flush()
    record_audit(db, user, "create", "specialty", specialty.id, after=payload.model_dump())
    db.commit()
    db.refresh(specialty)
    return specialty


@router.get("/services", response_model=list[ServiceResponse])
def list_services(_: CurrentUser, db: Session = Depends(get_db)) -> list[Service]:
    return list(
        db.scalars(select(Service).where(Service.active.is_(True)).order_by(Service.name)).all()
    )


@router.post("/services", response_model=ServiceResponse, status_code=status.HTTP_201_CREATED)
def create_service(
    payload: ServiceCreate, user: User = Depends(admin), db: Session = Depends(get_db)
) -> Service:
    service = Service(**payload.model_dump())
    db.add(service)
    db.flush()
    record_audit(db, user, "create", "service", service.id, after=payload.model_dump())
    db.commit()
    db.refresh(service)
    return service


@router.get("/doctors", response_model=list[DoctorResponse])
def list_doctors(_: CurrentUser, db: Session = Depends(get_db)) -> list[Doctor]:
    return list(
        db.scalars(select(Doctor).where(Doctor.active.is_(True)).order_by(Doctor.last_name)).all()
    )


@router.post("/doctors", response_model=DoctorResponse, status_code=status.HTTP_201_CREATED)
def create_doctor(
    payload: DoctorCreate, user: User = Depends(admin), db: Session = Depends(get_db)
) -> Doctor:
    doctor = Doctor(
        license_number=payload.license_number,
        first_name=payload.first_name,
        last_name=payload.last_name,
        email=payload.email,
        phone=payload.phone,
    )
    db.add(doctor)
    db.flush()
    for specialty_id in payload.specialty_ids:
        if not db.get(Specialty, specialty_id):
            raise HTTPException(
                status_code=404, detail=f"Especialidad {specialty_id} no encontrada"
            )
        doctor.specialties.append(DoctorSpecialty(specialty_id=specialty_id))
    for service_id in payload.service_ids:
        if not db.get(Service, service_id):
            raise HTTPException(status_code=404, detail=f"Servicio {service_id} no encontrado")
        doctor.services.append(DoctorService(service_id=service_id))
    record_audit(db, user, "create", "doctor", doctor.id, after=payload.model_dump())
    db.commit()
    db.refresh(doctor)
    return doctor


@router.patch("/doctors/{doctor_id}/status", response_model=DoctorResponse)
def change_doctor_status(
    doctor_id: int,
    payload: DoctorStatusChange,
    user: User = Depends(admin),
    db: Session = Depends(get_db),
) -> Doctor:
    doctor = db.get(Doctor, doctor_id)
    if not doctor:
        raise HTTPException(status_code=404, detail="Médico no encontrado")
    before = {"active": doctor.active}
    doctor.active = payload.active
    record_audit(
        db,
        user,
        "activate" if payload.active else "deactivate",
        "doctor",
        doctor.id,
        before=before,
        after={"active": payload.active},
    )
    db.commit()
    db.refresh(doctor)
    return doctor
