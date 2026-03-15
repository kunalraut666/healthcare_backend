from pydantic import BaseModel, Field
from typing import Optional

class PatientProfileCreate(BaseModel):
    user_id: int
    age: int = Field(..., ge=0, le=120)
    gender: str
    blood_type: Optional[str] = None
    address: Optional[str] = None

class PatientProfileUpdate(BaseModel):
    age: Optional[int] = Field(None, ge=0, le=120)
    gender: Optional[str]
    blood_type: Optional[str]
    address: Optional[str]

class PatientProfileResponse(PatientProfileCreate):
    id: int

    class Config:
        from_attributes = True
