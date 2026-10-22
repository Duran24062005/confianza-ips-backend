from datetime import date, datetime, time

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from .domain.types import AppointmentStatus, Role


class APIModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class UserResponse(APIModel):
    id: int
    email: EmailStr
    full_name: str
    role: Role
    active: bool
    patient_id: int | None = None
    doctor_id: int | None = None


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=160)
    password: str = Field(min_length=8)
    role: Role
    patient_id: int | None = None
    doctor_id: int | None = None


class PatientCreate(BaseModel):
    document_type: str = Field(min_length=2, max_length=20)
    document_number: str = Field(min_length=3, max_length=40)
    first_name: str = Field(min_length=2, max_length=80)
    last_name: str = Field(min_length=2, max_length=80)
    birth_date: date
    email: EmailStr
    phone: str = Field(min_length=7, max_length=40)
    address: str = Field(min_length=3, max_length=240)
    city: str = Field(min_length=2, max_length=100)
    eps: str = Field(min_length=2, max_length=120)
    emergency_name: str = Field(min_length=2, max_length=160)
    emergency_phone: str = Field(min_length=7, max_length=40)


class PatientUpdate(PatientCreate):
    pass


class PatientResponse(PatientCreate, APIModel):
    id: int
    active: bool
    created_at: datetime
    updated_at: datetime


class SpecialtyResponse(APIModel):
    id: int
    name: str
    active: bool


class SiteResponse(APIModel):
    id: int
    name: str
    address: str
    city: str
    active: bool


class SpecialtyCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)


class ServiceResponse(APIModel):
    id: int
    name: str
    description: str
    duration_minutes: int
    active: bool


class ServiceCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    description: str = ""
    duration_minutes: int = Field(default=30, ge=10, le=240)


class DoctorCreate(BaseModel):
    license_number: str = Field(min_length=3, max_length=60)
    first_name: str = Field(min_length=2, max_length=80)
    last_name: str = Field(min_length=2, max_length=80)
    email: EmailStr
    phone: str = Field(min_length=7, max_length=40)
    specialty_ids: list[int] = []
    service_ids: list[int] = []


class DoctorResponse(APIModel):
    id: int
    license_number: str
    first_name: str
    last_name: str
    email: EmailStr
    phone: str
    active: bool


class DoctorStatusChange(BaseModel):
    active: bool


class ScheduleCreate(BaseModel):
    weekday: int = Field(ge=0, le=6)
    start_time: time
    end_time: time


class ScheduleResponse(ScheduleCreate, APIModel):
    id: int
    doctor_id: int
    active: bool


class BlockCreate(BaseModel):
    starts_at: datetime
    ends_at: datetime
    reason: str = Field(min_length=2, max_length=240)


class BlockResponse(BlockCreate, APIModel):
    id: int
    doctor_id: int
    active: bool


class AvailabilitySlot(BaseModel):
    starts_at: datetime
    ends_at: datetime
    doctor_id: int
    service_id: int


class AppointmentCreate(BaseModel):
    patient_id: int | None = None
    doctor_id: int
    service_id: int
    site_id: int
    starts_at: datetime
    reason: str = Field(default="", max_length=500)


class AppointmentResponse(APIModel):
    id: int
    patient_id: int
    doctor_id: int
    service_id: int
    site_id: int
    starts_at: datetime
    ends_at: datetime
    status: AppointmentStatus
    reason: str
    created_at: datetime


class AppointmentStatusChange(BaseModel):
    status: AppointmentStatus
    reason: str = Field(default="", max_length=240)


class AppointmentReschedule(BaseModel):
    starts_at: datetime
    reason: str = Field(default="", max_length=240)


class AppointmentHistoryResponse(APIModel):
    id: int
    appointment_id: int
    from_status: str | None
    to_status: str
    reason: str
    changed_by_user_id: int
    changed_at: datetime


class ClinicalEncounterCreate(BaseModel):
    reason: str = Field(min_length=2, max_length=500)
    observation: str = Field(min_length=2, max_length=4000)
    evolution: str = Field(default="", max_length=4000)


class ClinicalEncounterResponse(APIModel):
    id: int
    appointment_id: int
    patient_id: int
    doctor_id: int
    occurred_at: datetime
    created_at: datetime


class ClinicalNoteResponse(APIModel):
    id: int
    encounter_id: int
    version: int
    note_type: str
    content: str
    supersedes_id: int | None
    created_by_user_id: int
    created_at: datetime


class AuthorizationCreate(BaseModel):
    patient_id: int
    service_id: int
    notes: str = Field(default="", max_length=2000)


class AuthorizationResponse(APIModel):
    id: int
    patient_id: int
    service_id: int
    status: str
    notes: str
    created_at: datetime
    updated_at: datetime


class DocumentResponse(APIModel):
    id: int
    patient_id: int
    appointment_id: int | None
    document_type: str
    title: str
    content: str
    created_at: datetime


class AuditResponse(APIModel):
    id: int
    actor_user_id: int | None
    action: str
    resource_type: str
    resource_id: str
    before_json: str | None
    after_json: str | None
    created_at: datetime


class DashboardResponse(BaseModel):
    active_patients: int
    inactive_patients: int
    active_doctors: int
    appointments_today: int
    pending_appointments: int
    confirmed_appointments: int
    cancelled_appointments: int
    upcoming_appointments: int
