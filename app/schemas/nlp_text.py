from pydantic import BaseModel
from typing import List, Literal

class NLPTextAnalysisRequest(BaseModel):
    text: str

class NamedEntity(BaseModel):
    text: str
    type: Literal["condition", "symptom", "medication", "vital_sign", "other"]
    confidence: float

class SentimentResult(BaseModel):
    score: float
    label: Literal["positive", "neutral", "negative"]
    confidence: float

class NLPTextAnalysisResponse(BaseModel):
    entities: List[NamedEntity]
    keywords: List[str]
    sentiment: SentimentResult
    summary: str
