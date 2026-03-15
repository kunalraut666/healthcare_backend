# app/schemas/report_upload.py
from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class ReportUploadCreate(BaseModel):
    # doctor: must send patient_id; patient: ignored (backend sets self)
    patient_id: Optional[int] = None
    report_type: str
    description: Optional[str] = None
    share_now: Optional[bool] = False   # NEW

class ReportUploadResponse(BaseModel):
    id: int
    patient_id: int
    report_type: str
    uploaded_by_id: int
    uploaded_at: datetime
    report_url: str
    description: Optional[str] = None
    is_shared: bool                    # NEW
    shared_at: Optional[datetime] = None

    class Config:
        from_attributes = True
