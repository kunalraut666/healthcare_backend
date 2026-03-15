# app/schemas/report_qa.py
from pydantic import BaseModel
from datetime import datetime
from typing import Optional, Literal

QAStatus = Literal["pending_review", "approved", "rejected"]

class QAAskIn(BaseModel):
    report_id: int
    question: str

class QAOut(BaseModel):
    id: int
    report_id: int
    question: str
    draft_answer: Optional[str] = None
    final_answer: Optional[str] = None
    status: QAStatus
    clinical_summary: Optional[str] = None
    treatment_suggestions: Optional[str] = None
    monitoring_plan: Optional[str] = None
    side_effects: Optional[str] = None
    red_flags: Optional[str] = None
    follow_up: Optional[str] = None
    created_by_id: int
    reviewed_by_id: Optional[int] = None
    created_at: datetime
    reviewed_at: Optional[datetime] = None

    class Config:
        from_attributes = True

