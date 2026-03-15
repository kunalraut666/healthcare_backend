# app/schemas/medical_record.py
from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class MedicalRecordBase(BaseModel):
    record_type: Optional[str] = "consultation"
    report_text: Optional[str] = None
    diagnosis: Optional[str] = None
    prescription: Optional[str] = None

class MedicalRecordCreate(MedicalRecordBase):
    patient_id: int
    doctor_id: Optional[int] = None

class MedicalRecordUpdate(BaseModel):
    record_type: Optional[str] = None
    report_text: Optional[str] = None
    diagnosis: Optional[str] = None
    prescription: Optional[str] = None

class MedicalRecordResponse(BaseModel):
    id: int
    patient_id: int
    doctor_id: Optional[int] = None
    record_type: Optional[str] = None
    report_text: Optional[str] = None
    diagnosis: Optional[str] = None
    prescription: Optional[str] = None
    created_at: Optional[datetime] = None

    # NEW
    source_upload_id: Optional[int] = None
    file_url: Optional[str] = None

    class Config:
        from_attributes = True
