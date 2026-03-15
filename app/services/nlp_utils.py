# app/services/nlp_utils.py
from typing import List, Dict, Any
from collections import Counter
import re

# --- Heuristics/regex ---
POSITIVE_WORDS = {"improved", "stable", "normal", "good", "better", "no", "negative"}
NEGATIVE_WORDS = {"elevated", "high", "abnormal", "worse", "positive", "critical", "pain", "infection", "severe"}

STOP_WORDS = {"the","and","of","to","a","in","is","with","for","on","patient","mg","daily","bpm","mmhg"}

MEDICINE_PATTERN = r"\b([A-Za-z][A-Za-z0-9\-]{2,})(?:\s?(?:\d{1,4})(?:mg|mcg|g|ml))\b"
BP_PATTERN = r"\b(\d{2,3})/(\d{2,3})\s?(?:mmhg)?\b"
HR_PATTERN = r"\b(?:hr|heart\s*rate)\s*[:\-]?\s*(\d{2,3})\b"
TEMP_PATTERN = r"\b(\d{2,3}(?:\.\d)?)\s?(?:°?\s?[cf]|celsius|fahrenheit)\b"

def extract_keywords(text: str) -> List[str]:
    words = re.findall(r"\w+", text.lower())
    freq = Counter(w for w in words if w not in STOP_WORDS)
    return [w for w, _ in freq.most_common(10)]

def heuristic_sentiment(text: str):
    from app.schemas.nlp_text import SentimentResult
    words = re.findall(r"\w+", text.lower())
    freq = Counter(words)
    pos = sum(freq[w] for w in POSITIVE_WORDS if w in freq)
    neg = sum(freq[w] for w in NEGATIVE_WORDS if w in freq)
    score = 0.0
    label = "neutral"
    if pos > neg:
        score = min(1.0, (pos - neg) / max(1, pos + neg))
        label = "positive"
    elif neg > pos:
        score = -min(1.0, (neg - pos) / max(1, pos + neg))
        label = "negative"
    conf = min(0.99, 0.5 + (abs(score) * 0.5))
    return SentimentResult(score=round(score,2), label=label, confidence=round(conf,2))

def add_vitals_and_meds(text: str, entities: list):
    from app.schemas.nlp_text import NamedEntity
    for m in re.finditer(BP_PATTERN, text, flags=re.I):
        entities.append(NamedEntity(text=m.group(0), type="vital_sign", confidence=0.98))
    for m in re.finditer(HR_PATTERN, text, flags=re.I):
        entities.append(NamedEntity(text=m.group(0), type="vital_sign", confidence=0.95))
    for m in re.finditer(TEMP_PATTERN, text, flags=re.I):
        entities.append(NamedEntity(text=m.group(0), type="vital_sign", confidence=0.92))
    for m in re.finditer(MEDICINE_PATTERN, text, flags=re.I):
        entities.append(NamedEntity(text=m.group(0), type="medication", confidence=0.92))

def dedup_entities(entities: list):
    seen = set(); out = []
    for e in entities:
        key = (e.text.lower(), e.type)
        if key not in seen:
            seen.add(key); out.append(e)
    return out[:20]

def heuristic_summary(text: str) -> str:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return " ".join(parts[:2]) if parts else text[:300]
