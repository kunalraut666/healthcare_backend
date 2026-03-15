from sqlalchemy import Column, Integer, String, Float, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base

class PatientProfile(Base):
    __tablename__ = "patient_profiles"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("healthcare_users.id"))
    blood_group = Column(String(5))
    weight = Column(Float)
    height = Column(Float)
    allergies = Column(Text)
    existing_conditions = Column(Text)
    medications = Column(Text)
    emergency_contact = Column(String(15))

    user = relationship("User", back_populates="profile")