from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Index
from sqlalchemy.orm import relationship
from datetime import datetime, timedelta
from app.core.database import Base

class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("healthcare_users.id"), nullable=False)
    token_hash = Column(String(128), nullable=False, index=True)   # sha256 hex
    user_agent = Column(String(200), nullable=True)
    ip = Column(String(64), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    revoked = Column(Boolean, default=False, nullable=False)

    user = relationship("User")

Index("ix_refresh_valid", RefreshToken.user_id, RefreshToken.token_hash, RefreshToken.revoked)
