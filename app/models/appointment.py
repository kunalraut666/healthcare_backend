from sqlalchemy import Column, Integer, String, Float, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base

class Appointment(Base):
    __tablename__ = "appointments"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("healthcare_users.id"))
    doctor_id = Column(Integer, ForeignKey("healthcare_users.id"))
    appointment_datetime = Column(DateTime, default=datetime.utcnow)
    reason = Column(Text)
    status = Column(String, default="scheduled")  # scheduled, completed, cancelled

    patient = relationship("User", back_populates="appointments_as_patient", foreign_keys=[patient_id])
    doctor = relationship("User", back_populates="appointments_as_doctor", foreign_keys=[doctor_id])
