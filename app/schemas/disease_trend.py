# 📁 app/schemas/disease_trend.py
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from datetime import datetime

class DiseaseTrendBase(BaseModel):
    disease: str
    age_group: str
    region: str
    trend_data: Dict[str, Any]  # {"confidence": 0.97, "symptoms": [...], "vitals": {...}}

class DiseaseTrendCreate(DiseaseTrendBase):
    pass

class DiseaseTrendResponse(DiseaseTrendBase):
    id: int
    recorded_at: datetime

    class Config:
        from_attributes = True  # pydantic v2 me from_attributes ki jagah

# 🧠 For prediction input/output
class DiseasePredictionInput(BaseModel):
    symptoms: List[str]
    age: Optional[int] = None
    blood_pressure: Optional[str] = None   # "120/80"
    heart_rate: Optional[int] = None       # bpm
    temperature: Optional[float] = None    # Fahrenheit
    oxygen_saturation: Optional[float] = None  # %

class DiseasePredictionOutput(BaseModel):
    predicted_disease: str
    confidence: float
