# app/schemas/appointment.py
from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class AppointmentBase(BaseModel):
    appointment_datetime: datetime
    reason: str

class AppointmentCreate(AppointmentBase):
    # Make patient_id optional — server will derive from token for patient users
    patient_id: Optional[int] = None
    doctor_id: int

class AppointmentUpdate(BaseModel):
    appointment_datetime: Optional[datetime] = None
    reason: Optional[str] = None
    status: Optional[str] = None  # scheduled, completed, cancelled

class AppointmentResponse(AppointmentBase):
    id: int
    patient_id: int
    doctor_id: int
    status: str
    patient_name: Optional[str] = None
    doctor_name: Optional[str] = None

    model_config = {"from_attributes": True, "extra": "ignore"}

