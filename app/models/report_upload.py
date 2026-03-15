# app/models/report_upload.py
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base

class ReportUpload(Base):
    __tablename__ = "report_uploads"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("healthcare_users.id"), nullable=False)
    uploaded_by_id = Column(Integer, ForeignKey("healthcare_users.id"), nullable=False)
    report_type = Column(String(100), nullable=False)
    file_path = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    uploaded_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    is_shared = Column(Boolean, nullable=False, default=False)
    shared_at = Column(DateTime, nullable=True)

    # IMPORTANT: foreign_keys specify karo
    patient = relationship(
        "User",
        foreign_keys=[patient_id],
        back_populates="patient_reports",
    )
    uploaded_by = relationship(
        "User",
        foreign_keys=[uploaded_by_id],
        back_populates="uploaded_reports",
    )
