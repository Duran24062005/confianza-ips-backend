from __future__ import annotations

from datetime import date, datetime, time, timezone
from enum import Enum

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    Time,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Role(str, Enum):
    ADMIN = "admin"
    RECEPTIONIST = "receptionist"
    DOCTOR = "doctor"
    PATIENT = "patient"


class AppointmentStatus(str, Enum):
    REQUESTED = "requested"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    NO_SHOW = "no_show"


class Institution(Base):
    __tablename__ = "institutions"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160), unique=True)
    document_number: Mapped[str | None] = mapped_column(String(40), unique=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    sites: Mapped[list[Site]] = relationship(
        back_populates="institution", cascade="all, delete-orphan"
    )


class Site(Base):
    __tablename__ = "sites"
    id: Mapped[int] = mapped_column(primary_key=True)
    institution_id: Mapped[int] = mapped_column(ForeignKey("institutions.id"))
    name: Mapped[str] = mapped_column(String(160))
    address: Mapped[str] = mapped_column(String(240))
    city: Mapped[str] = mapped_column(String(100), default="Bogotá")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    institution: Mapped[Institution] = relationship(back_populates="sites")


class Patient(Base):
    __tablename__ = "patients"
    __table_args__ = (
        UniqueConstraint("document_type", "document_number", name="uq_patient_document"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    document_type: Mapped[str] = mapped_column(String(20))
    document_number: Mapped[str] = mapped_column(String(40))
    first_name: Mapped[str] = mapped_column(String(80))
    last_name: Mapped[str] = mapped_column(String(80))
    birth_date: Mapped[date] = mapped_column(Date)
    email: Mapped[str] = mapped_column(String(160))
    phone: Mapped[str] = mapped_column(String(40))
    address: Mapped[str] = mapped_column(String(240))
    city: Mapped[str] = mapped_column(String(100))
    eps: Mapped[str] = mapped_column(String(120))
    emergency_name: Mapped[str] = mapped_column(String(160))
    emergency_phone: Mapped[str] = mapped_column(String(40))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class Doctor(Base):
    __tablename__ = "doctors"
    id: Mapped[int] = mapped_column(primary_key=True)
    license_number: Mapped[str] = mapped_column(String(60), unique=True)
    first_name: Mapped[str] = mapped_column(String(80))
    last_name: Mapped[str] = mapped_column(String(80))
    email: Mapped[str] = mapped_column(String(160))
    phone: Mapped[str] = mapped_column(String(40))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    specialties: Mapped[list[DoctorSpecialty]] = relationship(
        back_populates="doctor", cascade="all, delete-orphan"
    )
    services: Mapped[list[DoctorService]] = relationship(
        back_populates="doctor", cascade="all, delete-orphan"
    )
    schedules: Mapped[list[DoctorSchedule]] = relationship(
        back_populates="doctor", cascade="all, delete-orphan"
    )


class Specialty(Base):
    __tablename__ = "specialties"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Service(Base):
    __tablename__ = "services"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160), unique=True)
    description: Mapped[str] = mapped_column(Text, default="")
    duration_minutes: Mapped[int] = mapped_column(Integer, default=30)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class DoctorSpecialty(Base):
    __tablename__ = "doctor_specialties"
    doctor_id: Mapped[int] = mapped_column(ForeignKey("doctors.id"), primary_key=True)
    specialty_id: Mapped[int] = mapped_column(ForeignKey("specialties.id"), primary_key=True)
    doctor: Mapped[Doctor] = relationship(back_populates="specialties")
    specialty: Mapped[Specialty] = relationship()


class DoctorService(Base):
    __tablename__ = "doctor_services"
    doctor_id: Mapped[int] = mapped_column(ForeignKey("doctors.id"), primary_key=True)
    service_id: Mapped[int] = mapped_column(ForeignKey("services.id"), primary_key=True)
    doctor: Mapped[Doctor] = relationship(back_populates="services")
    service: Mapped[Service] = relationship()


class DoctorSchedule(Base):
    __tablename__ = "doctor_schedules"
    id: Mapped[int] = mapped_column(primary_key=True)
    doctor_id: Mapped[int] = mapped_column(ForeignKey("doctors.id"))
    weekday: Mapped[int] = mapped_column(Integer)
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time] = mapped_column(Time)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    doctor: Mapped[Doctor] = relationship(back_populates="schedules")


class ScheduleBlock(Base):
    __tablename__ = "schedule_blocks"
    id: Mapped[int] = mapped_column(primary_key=True)
    doctor_id: Mapped[int] = mapped_column(ForeignKey("doctors.id"))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    reason: Mapped[str] = mapped_column(String(240))
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Appointment(Base):
    __tablename__ = "appointments"
    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"))
    doctor_id: Mapped[int] = mapped_column(ForeignKey("doctors.id"))
    service_id: Mapped[int] = mapped_column(ForeignKey("services.id"))
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id"))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[AppointmentStatus] = mapped_column(
        String(20), default=AppointmentStatus.REQUESTED
    )
    reason: Mapped[str] = mapped_column(String(500), default="")
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )
    patient: Mapped[Patient] = relationship()
    doctor: Mapped[Doctor] = relationship()
    service: Mapped[Service] = relationship()
    site: Mapped[Site] = relationship()


class AppointmentStatusHistory(Base):
    __tablename__ = "appointment_status_history"
    id: Mapped[int] = mapped_column(primary_key=True)
    appointment_id: Mapped[int] = mapped_column(ForeignKey("appointments.id"))
    from_status: Mapped[str | None] = mapped_column(String(20))
    to_status: Mapped[str] = mapped_column(String(20))
    reason: Mapped[str] = mapped_column(String(240), default="")
    changed_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ClinicalEncounter(Base):
    __tablename__ = "clinical_encounters"
    id: Mapped[int] = mapped_column(primary_key=True)
    appointment_id: Mapped[int] = mapped_column(ForeignKey("appointments.id"), unique=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"))
    doctor_id: Mapped[int] = mapped_column(ForeignKey("doctors.id"))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ClinicalNote(Base):
    __tablename__ = "clinical_notes"
    id: Mapped[int] = mapped_column(primary_key=True)
    encounter_id: Mapped[int] = mapped_column(ForeignKey("clinical_encounters.id"))
    version: Mapped[int] = mapped_column(Integer, default=1)
    note_type: Mapped[str] = mapped_column(String(40), default="evolution")
    content: Mapped[str] = mapped_column(Text)
    supersedes_id: Mapped[int | None] = mapped_column(ForeignKey("clinical_notes.id"))
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class Authorization(Base):
    __tablename__ = "authorizations"
    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"))
    service_id: Mapped[int] = mapped_column(ForeignKey("services.id"))
    status: Mapped[str] = mapped_column(String(30), default="requested")
    notes: Mapped[str] = mapped_column(Text, default="")
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class Document(Base):
    __tablename__ = "documents"
    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"))
    appointment_id: Mapped[int | None] = mapped_column(ForeignKey("appointments.id"))
    document_type: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(180))
    content: Mapped[str] = mapped_column(Text)
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(80))
    resource_type: Mapped[str] = mapped_column(String(80))
    resource_id: Mapped[str] = mapped_column(String(80))
    before_json: Mapped[str | None] = mapped_column(Text)
    after_json: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(160), unique=True)
    full_name: Mapped[str] = mapped_column(String(160))
    password_hash: Mapped[str] = mapped_column(String(300))
    role: Mapped[Role] = mapped_column(String(30))
    patient_id: Mapped[int | None] = mapped_column(ForeignKey("patients.id"), unique=True)
    doctor_id: Mapped[int | None] = mapped_column(ForeignKey("doctors.id"), unique=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    session_version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
