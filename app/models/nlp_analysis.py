# app/models/nlp_analysis.py
from sqlalchemy import Column, Integer, Text, DateTime, ForeignKey, JSON, Enum
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from app.core.database import Base
from app.models.user import User                # <-- important

class AnalysisStatus(str, enum.Enum):
    draft = "draft"
    reviewed = "reviewed"
    final = "final"

class NLPAnalysis(Base):
    __tablename__ = "nlp_analysis"

    id = Column(Integer, primary_key=True)

    # ✅ bind to actual User.id column instead of "users.id" string
    patient_id = Column(Integer, ForeignKey(User.id), nullable=False)
    created_by = Column(Integer, ForeignKey(User.id), nullable=False)

    # keep your record link too
    record_id = Column(Integer, ForeignKey("medical_records.id", ondelete="CASCADE"), nullable=True)

    source_text = Column(Text, nullable=False)
    entities = Column(JSON, nullable=False, default=list)
    keywords = Column(JSON, nullable=False, default=list)
    sentiment = Column(JSON, nullable=False, default=dict)
    summary = Column(Text, nullable=False, default="")
    status = Column(Enum(AnalysisStatus), default=AnalysisStatus.draft, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # relationships (note explicit foreign_keys)
    patient = relationship("User", foreign_keys=[patient_id])
    creator = relationship("User", foreign_keys=[created_by])
    record  = relationship("MedicalRecord", back_populates="nlp_analysis", uselist=False)
