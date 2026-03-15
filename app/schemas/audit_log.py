from pydantic import BaseModel
from datetime import datetime

class AuditLogBase(BaseModel):
    action: str
    table_name: str
    record_id: int

class AuditLogCreate(AuditLogBase):
    user_id: int

class AuditLogResponse(AuditLogBase):
    id: int
    timestamp: datetime
    user_id: int

    class Config:
        from_attributes = True
