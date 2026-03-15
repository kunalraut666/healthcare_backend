# app/schemas/user.py
from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from typing import Optional
from enum import Enum

class Gender(str, Enum):
    male = "male"
    female = "female"
    other = "other"

class UserRole(str, Enum):
    patient = "patient"
    doctor = "doctor"
    admin = "admin"

class UserBase(BaseModel):
    name: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    role: UserRole
    mobile: Optional[str] = Field(None, min_length=10, max_length=15)
    dob: Optional[str]
    gender: Optional[Gender]

class UserCreate(UserBase):
    password: str = Field(..., min_length=6)

class UserLoginRequest(BaseModel):
    email: EmailStr
    password: str

# Pydantic v2-compatible response model
class UserResponse(UserBase):
    id: int
    created_at: datetime

    # Pydantic v2: allow creation from ORM objects (attribute access)
    model_config = {
        "from_attributes": True,
        # optional: ignore extra attributes if they exist
        "extra": "ignore",
    }
