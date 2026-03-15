# app/models/report_qa.py
from sqlalchemy import Column, Integer, Text, DateTime, ForeignKey, Enum
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from app.core.database import Base

class QAStatus(str, enum.Enum):
    pending_review = "pending_review"
    approved = "approved"
    rejected = "rejected"

class ReportQA(Base):
    __tablename__ = "report_qas"

    id = Column(Integer, primary_key=True, index=True)

    # NOTE: keep same FK names as your DB; add ondelete if you like
    report_id = Column(Integer, ForeignKey("report_uploads.id"), nullable=False)

    question = Column(Text, nullable=False)
    draft_answer = Column(Text, nullable=False)
    final_answer = Column(Text, nullable=True)
    status = Column(Enum(QAStatus), default=QAStatus.pending_review, nullable=False)

    # NEW — structured fields (present in DB but missing in model)
    clinical_summary       = Column(Text, nullable=True)
    treatment_suggestions  = Column(Text, nullable=True)
    monitoring_plan        = Column(Text, nullable=True)
    side_effects           = Column(Text, nullable=True)
    red_flags              = Column(Text, nullable=True)
    follow_up              = Column(Text, nullable=True)

    created_by_id = Column(Integer, ForeignKey("healthcare_users.id"), nullable=False)
    reviewed_by_id = Column(Integer, ForeignKey("healthcare_users.id"), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    reviewed_at = Column(DateTime, nullable=True)

    # Optional: relationships (safe to keep)
    report = relationship("ReportUpload")
    created_by = relationship("User", foreign_keys=[created_by_id])
    reviewed_by = relationship("User", foreign_keys=[reviewed_by_id])
