from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from datetime import datetime
import os, re, json, logging

from app.schemas.disease_trend import (
    DiseaseTrendCreate,
    DiseaseTrendResponse,
    DiseasePredictionInput,
    DiseasePredictionOutput,
)
from app.models.disease_trend import DiseaseTrend
from app.core.database import get_db
from app.core.config import OPENAI_API_KEY, OPENAI_MODEL

from openai import OpenAI

router = APIRouter()

# ---------- LABEL MAP (0..40) ----------
LABEL_MAP = {
    "LABEL_0": "Paroxysmal Positional Vertigo (Vertigo)",
    "LABEL_1": "AIDS",
    "LABEL_2": "Acne",
    "LABEL_3": "Alcoholic hepatitis",
    "LABEL_4": "Allergy",
    "LABEL_5": "Arthritis",
    "LABEL_6": "Bronchial Asthma",
    "LABEL_7": "Cervical spondylosis",
    "LABEL_8": "Chicken pox",
    "LABEL_9": "Chronic cholestasis",
    "LABEL_10": "Common Cold",
    "LABEL_11": "Dengue",
    "LABEL_12": "Diabetes",
    "LABEL_13": "Dimorphic hemorrhoids (piles)",
    "LABEL_14": "Drug Reaction",
    "LABEL_15": "Fungal infection",
    "LABEL_16": "GERD",
    "LABEL_17": "Gastroenteritis",
    "LABEL_18": "Heart attack",
    "LABEL_19": "Hepatitis B",
    "LABEL_20": "Hepatitis C",
    "LABEL_21": "Hepatitis D",
    "LABEL_22": "Hepatitis E",
    "LABEL_23": "Hypertension",
    "LABEL_24": "Hyperthyroidism",
    "LABEL_25": "Hypoglycemia",
    "LABEL_26": "Hypothyroidism",
    "LABEL_27": "Impetigo",
    "LABEL_28": "Jaundice",
    "LABEL_29": "Malaria",
    "LABEL_30": "Migraine",
    "LABEL_31": "Osteoarthritis",
    "LABEL_32": "Paralysis (brain hemorrhage)",
    "LABEL_33": "Peptic ulcer disease",
    "LABEL_34": "Pneumonia",
    "LABEL_35": "Psoriasis",
    "LABEL_36": "Tuberculosis",
    "LABEL_37": "Typhoid",
    "LABEL_38": "Urinary tract infection",
    "LABEL_39": "Varicose veins",
    "LABEL_40": "Hepatitis A",
} 
LABELS_ALLOWED = list(LABEL_MAP.keys())

# ===== OpenAI helper =====
def _openai_client() -> OpenAI:
    key = OPENAI_API_KEY 
    if not key:
        raise RuntimeError("OPENAI_API_KEY not set")
    return OpenAI(api_key=key)

def oa_json_completion(system_prompt: str, user_prompt: str, max_tokens_out: int = 220) -> Dict[str, Any]:
    model = OPENAI_MODEL
    client = _openai_client()

    def call(sp: str, up: str) -> str:
        resp = client.chat.completions.create(
            model=model,
            temperature=0,
            max_tokens=max_tokens_out,
            messages=[
                {"role": "system", "content": sp},
                {"role": "user", "content": up}
            ],
        )
        return resp.choices[0].message.content or ""

    def extract_json(s: str) -> Optional[Dict[str, Any]]:
        m = re.search(r"\{.*\}", s, flags=re.S)
        if not m: return None
        try:
            return json.loads(m.group(0))
        except Exception:
            return None

    text = call(system_prompt, user_prompt)
    data = extract_json(text)
    if data is not None:
        return data

    strong = system_prompt + "\nReturn STRICT JSON only. No prose."
    text2 = call(strong, user_prompt)
    data2 = extract_json(text2)
    return data2 or {"error": "parse_failed"}

def human_label(label: Optional[str]) -> Optional[str]:
    if not label:
        return None
    return LABEL_MAP.get(label, label)

def _predict_with_openai(symptoms: List[str], vitals: Dict[str, Any]) -> Dict[str, Any]:
    """
    Quick classifier via OpenAI.
    Output (STRICT JSON):
    {
      "top_label": "LABEL_12",
      "top_confidence": 0.92,
      "candidates": [{"label": "LABEL_12", "score": 0.92}, ...]
    }
    """
    sys = (
        "You are a clinical triage classifier. "
        "Classify patient symptoms (and optional vitals) into ONE of the allowed disease labels. "
        "Choose labels ONLY from the provided list. "
        "Return STRICT JSON: {\"top_label\": string, \"top_confidence\": 0..1, \"candidates\": [{\"label\": string, \"score\": 0..1}]}. "
        "No extra text."
    )
    user = f"""
    ALLOWED_LABELS:
    {json.dumps(LABELS_ALLOWED)}

    SYMPTOMS (comma separated):
    {", ".join(symptoms) if symptoms else "none"}

    VITALS (may be empty):
    {json.dumps(vitals, ensure_ascii=False)}

    INSTRUCTIONS:
    - Consider symptoms and vitals.
    - Pick the most likely top_label from ALLOWED_LABELS.
    - Provide up to 5 candidates sorted by score (desc).
    - Scores must be between 0 and 1.
    - If uncertain, still choose the best label with lower confidence.
    - Output STRICT JSON only.
    """
    data = oa_json_completion(sys, user, max_tokens_out=200)
    if "error" in data:
        raise RuntimeError("OpenAI output parse failed")

    top_label = str(data.get("top_label", "")).strip()
    top_conf = float(data.get("top_confidence", 0.0))
    candidates = data.get("candidates") or []

    if top_label not in LABELS_ALLOWED:
        inv = {v.lower(): k for k, v in LABEL_MAP.items()}
        guess = inv.get(top_label.lower())
        if guess:
            top_label = guess
        else:
            valid_cands = [c for c in candidates if isinstance(c, dict) and c.get("label") in LABELS_ALLOWED]
            if valid_cands:
                top_label = valid_cands[0]["label"]
                top_conf = float(valid_cands[0].get("score", 0.0))
            else:
                raise RuntimeError("Model returned invalid label set")

    norm_cands = []
    if isinstance(candidates, list):
        for c in candidates:
            if not isinstance(c, dict):
                continue
            lbl = str(c.get("label", "")).strip()
            sc = float(c.get("score", 0.0))
            if lbl in LABELS_ALLOWED:
                norm_cands.append({"label": lbl, "score": sc})
    if not norm_cands:
        norm_cands = [{"label": top_label, "score": top_conf}]

    return {
        "top_label": top_label,
        "top_confidence": float(top_conf),
        "candidates": norm_cands[:5],
    }

# -------------------- Endpoints --------------------

@router.post("/predict", response_model=DiseasePredictionOutput)
async def predict_disease(input_data: DiseasePredictionInput, db: Session = Depends(get_db)):
    symptoms = input_data.symptoms or []
    vitals = {
        "age": input_data.age,
        "blood_pressure": input_data.blood_pressure,
        "heart_rate": input_data.heart_rate,
        "temperature": input_data.temperature,
        "oxygen_saturation": input_data.oxygen_saturation,
    }

    if not symptoms and not any(v is not None for v in vitals.values()):
        raise HTTPException(status_code=400, detail="Provide at least symptoms or one vital.")

    try:
        result = _predict_with_openai(symptoms, vitals)
        raw_label = result["top_label"]
        confidence = round(float(result["top_confidence"]), 4)
        predicted_disease = human_label(raw_label) or raw_label

        mapped_candidates = [
            {
                "label": human_label(c["label"]) or c["label"],
                "score": round(float(c.get("score", 0.0)), 4),
            }
            for c in result["candidates"]
        ]

        alt_list = []
        for c in mapped_candidates[1:]:
            alt_list.append({"condition": c["label"], "confidence": c["score"]})

        trend_data = {
            "raw_label": raw_label,
            "mapped_label": predicted_disease,
            "confidence": confidence,
            "symptoms": symptoms,
            "vitals": vitals,
            "candidates": mapped_candidates,
            "predicted_at": datetime.utcnow().isoformat(),
            "model": os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        }

        new_entry = DiseaseTrend(
            disease=predicted_disease,
            age_group=str(input_data.age) if input_data.age is not None else "unknown",
            region="unknown",
            trend_data=trend_data,
        )
        db.add(new_entry)
        db.commit()
        db.refresh(new_entry)

        return {
            "predicted_disease": predicted_disease,
            "confidence": confidence,
            "alternativeDiagnoses": alt_list,
            "candidates": mapped_candidates,
        }

    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=f"Prediction temporarily unavailable: {str(e)}")
    except Exception as e:
        logging.exception("Prediction failure")
        raise HTTPException(status_code=500, detail=f"Prediction failed: {str(e)}")

@router.post("/", response_model=DiseaseTrendResponse)
def create_trend(data: DiseaseTrendCreate, db: Session = Depends(get_db)):
    new_trend = DiseaseTrend(**data.dict())
    db.add(new_trend)
    db.commit()
    db.refresh(new_trend)
    return new_trend

@router.get("/", response_model=List[DiseaseTrendResponse])
def get_all_trends(db: Session = Depends(get_db)):
    return db.query(DiseaseTrend).all()

@router.get("/{trend_id}", response_model=DiseaseTrendResponse)
def get_trend(trend_id: int, db: Session = Depends(get_db)):
    trend = db.query(DiseaseTrend).get(trend_id)
    if not trend:
        raise HTTPException(status_code=404, detail="Trend not found")
    return trend

@router.put("/{trend_id}", response_model=DiseaseTrendResponse)
def update_trend(trend_id: int, data: DiseaseTrendCreate, db: Session = Depends(get_db)):
    trend = db.query(DiseaseTrend).get(trend_id)
    if not trend:
        raise HTTPException(status_code=404, detail="Trend not found")
    for key, value in data.dict().items():
        setattr(trend, key, value)
    db.commit()
    db.refresh(trend)
    return trend

@router.delete("/{trend_id}")
def delete_trend(trend_id: int, db: Session = Depends(get_db)):
    trend = db.query(DiseaseTrend).get(trend_id)
    if not trend:
        raise HTTPException(status_code=404, detail="Trend not found")
    db.delete(trend)
    db.commit()
    return {"message": "Deleted successfully"}
