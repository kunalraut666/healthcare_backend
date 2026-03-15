from sqlalchemy import Column, Integer, String, Float, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base
from app.models.medical_record import MedicalRecord
from app.models.report_upload import ReportUpload

class User(Base):
    __tablename__ = "healthcare_users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    password = Column(String, nullable=False)
    role = Column(String, nullable=False)  # patient, doctor, admin
    mobile = Column(String(15))
    gender = Column(String(10))
    dob = Column(String(20))
    created_at = Column(DateTime, default=datetime.utcnow)

    # Existing relationships
    profile = relationship("PatientProfile", back_populates="user", uselist=False)

    medical_records = relationship("MedicalRecord", back_populates="patient", foreign_keys=[MedicalRecord.patient_id])
    predictions = relationship("AIPrediction", back_populates="patient")
    logs = relationship("AuditLog", back_populates="user")

    # New relationships
    appointments_as_patient = relationship("Appointment", back_populates="patient", foreign_keys="Appointment.patient_id")
    appointments_as_doctor = relationship("Appointment", back_populates="doctor", foreign_keys="Appointment.doctor_id")
    uploaded_reports = relationship("ReportUpload", back_populates="uploaded_by", cascade="all, delete-orphan")
    access_controls = relationship("AccessControl", back_populates="user")

    # Reports jisme user patient hai
    patient_reports = relationship(
        "ReportUpload",
        foreign_keys=[ReportUpload.patient_id],
        back_populates="patient",
    )

    # Reports jise user (doctor/admin) ne upload kiya
    uploaded_reports = relationship(
        "ReportUpload",
        foreign_keys=[ReportUpload.uploaded_by_id],
        back_populates="uploaded_by",
        cascade="all, delete-orphan",
    )