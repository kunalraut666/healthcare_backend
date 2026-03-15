from sqlalchemy import Column, Integer, String, Float, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base


class AccessControl(Base):
    __tablename__ = "access_controls"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("healthcare_users.id"))
    access_level = Column(String, nullable=False)  # read, write, delete
    module = Column(String, nullable=False)  # e.g., MedicalRecord, UserManagement
    granted_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="access_controls")
