from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class AIPredictionBase(BaseModel):
    input_data: str
    prediction_result: str
    confidence: Optional[float] = None

class AIPredictionCreate(AIPredictionBase):
    patient_id: int

class AIPredictionResponse(AIPredictionBase):
    id: int
    predicted_at: datetime
    patient_id: int

    class Config:
        from_attributes = True

class AIPredictionUpdate(BaseModel):
    input_data: Optional[str] = None
    prediction_result: Optional[str] = None
    confidence: Optional[float] = None
