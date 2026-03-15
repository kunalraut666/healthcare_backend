from sqlalchemy import Column, Integer, String, JSON, DateTime
from datetime import datetime
from app.core.database import Base

class DiseaseTrend(Base):
    __tablename__ = "disease_trends"

    id = Column(Integer, primary_key=True)
    disease = Column(String)
    age_group = Column(String)
    region = Column(String)
    trend_data = Column(JSON)
    last_updated = Column(DateTime, default=datetime.utcnow)
