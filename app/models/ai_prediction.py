from sqlalchemy import Column, Integer, String, Float, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base

class AIPrediction(Base):
    __tablename__ = "ai_predictions"

    id = Column(Integer, primary_key=True)
    patient_id = Column(Integer, ForeignKey("healthcare_users.id"))
    input_features = Column(JSON)
    predicted_disease = Column(String)
    prediction_score = Column(Float)
    model_version = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

    patient = relationship("User", back_populates="predictions")
