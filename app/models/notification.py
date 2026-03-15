from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base
from app.models.user import User

class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey(User.id), nullable=False)   # doctor who receives
    type = Column(String(50), nullable=False)                         # e.g. 'nlp_review'
    title = Column(String(200), nullable=False)
    message = Column(Text, nullable=False)
    ref_type = Column(String(50), nullable=True)                      # 'nlp_analysis'
    ref_id = Column(Integer, nullable=True)                           # analysis id
    is_read = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User")
