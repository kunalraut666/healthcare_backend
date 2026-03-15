from pydantic import BaseModel, Field
from typing import List, Literal, Optional
from app.schemas.nlp_text import NamedEntity, SentimentResult

class PatientAnalyzeRequest(BaseModel):
    text: str = Field(..., min_length=1, description="raw medical text")
    patient_id: Optional[int] = None  # doctor/admin can set target

class NLPAnalysisOut(BaseModel):
    id: int
    patient_id: int
    source_text: str
    entities: List[NamedEntity]
    keywords: List[str]
    sentiment: SentimentResult
    summary: str
    status: Literal["draft","reviewed","final"]

    class Config:
        from_attributes = True

class TriageResult(BaseModel):
    level: Literal["normal", "needs_review", "critical"]
    reasons: List[str] = []
    confidence: float = 0.8

class PatientAnalyzeRequest(BaseModel):
    text: str = Field(..., min_length=1, description="raw medical text")
    patient_id: Optional[int] = None  # doctor/admin can target a patient

class NLPAnalysisOut(BaseModel):
    id: int
    patient_id: int
    source_text: str
    entities: List[NamedEntity]
    keywords: List[str]
    sentiment: SentimentResult
    summary: str
    status: Literal["draft","reviewed","final"]
    triage: Optional[TriageResult] = None   # <-- NEW (for UI)

    class Config:
        from_attributes = True

class NLPAnalysisUpdateHITL(BaseModel):
    entities: Optional[List[NamedEntity]] = None
    keywords: Optional[List[str]] = None
    sentiment: Optional[SentimentResult] = None
    summary: Optional[str] = None
    status: Optional[Literal["draft","reviewed","final"]] = None