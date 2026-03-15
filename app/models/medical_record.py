# app/models/medical_record.py
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base

class MedicalRecord(Base):
    __tablename__ = "medical_records"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("healthcare_users.id"), nullable=False)
    doctor_id = Column(Integer, ForeignKey("healthcare_users.id"), nullable=True)

    record_type = Column(String, default="consultation")  # consultation, lab, scan, report
    report_text = Column(Text, nullable=True)
    diagnosis = Column(String, nullable=True)
    prescription = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    patient = relationship("User", foreign_keys=[patient_id])
    doctor = relationship("User", foreign_keys=[doctor_id])

    nlp_analysis = relationship("NLPAnalysis", back_populates="record", uselist=False, cascade="all, delete-orphan")
    source_upload_id = Column(Integer, nullable=True, unique=True)  # snapshot origin (report_uploads.id)

    __table_args__ = (
        UniqueConstraint("source_upload_id", name="uq_medrec_source_upload"),
        Index("ix_medrec_patient_created", "patient_id", "created_at"),
    )