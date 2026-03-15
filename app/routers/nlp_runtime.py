# app/routers/nlp.py  — OpenAI integrated (text-only)

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
from collections import Counter
import json, re

from app.core.database import get_db
from app.dependencies.roles import get_current_user
from app.models.user import User

from app.schemas.nlp_text import (
    NLPTextAnalysisRequest,
    NLPTextAnalysisResponse,
    NamedEntity,
    SentimentResult,
)

from app.services.nlp_utils import (
  extract_keywords, heuristic_sentiment, add_vitals_and_meds,
  dedup_entities, heuristic_summary
)

# 👉 OpenAI wrapper you already use in report_qa
from app.core.llm import chat_json

router = APIRouter()


# -------------------- OpenAI prompt + JSON extraction --------------------
ALLOWED_TYPES = {"condition","symptom","medication","vital_sign","other"}

SYSTEM_INSTRUCT = (
    "You are a medical NLP assistant. Given clinical text, extract:\n"
    "1) entities: list of {text, type in [condition,symptom,medication,vital_sign,other], confidence (0..1)}\n"
    "2) keywords: 5-10 important lowercase keywords\n"
    "3) sentiment: {label in [positive,neutral,negative], score -1..1, confidence 0..1}\n"
    "4) summary: 2 concise sentences.\n"
    "Respond with STRICT JSON ONLY matching this schema:\n"
    "{\n"
    '  \"entities\": [{\"text\":\"...\", \"type\":\"condition|symptom|medication|vital_sign|other\", \"confidence\":0.95}],\n'
    '  \"keywords\": [\"...\"],\n'
    '  \"sentiment\": {\"score\": 0.2, \"label\": \"neutral\", \"confidence\": 0.78},\n'
    '  \"summary\": \"...\" \n'
    "}\n"
)

def openai_analyze(text: str) -> dict | None:
    # Text could be long; OpenAI tokens are limited — trim safely
    trimmed = text if len(text) <= 32000 else text[:32000]
    try:
        out = chat_json(SYSTEM_INSTRUCT, trimmed, max_tokens=400)
        if not isinstance(out, dict):
            return None

        # sanitize
        ents = []
        for e in out.get("entities", []):
            t = str(e.get("type","other")).lower()
            if t not in ALLOWED_TYPES: t = "other"
            conf = float(e.get("confidence", 0.9))
            ents.append({"text": str(e.get("text","")).strip(), "type": t, "confidence": conf})
        out["entities"] = ents

        kw = [str(k).lower() for k in (out.get("keywords") or [])][:10]
        out["keywords"] = kw

        sent = out.get("sentiment") or {}
        s_score = float(sent.get("score", 0.0))
        s_label = str(sent.get("label","neutral")).lower()
        s_conf = float(sent.get("confidence", 0.7))
        if s_label not in {"positive","neutral","negative"}:
            s_label = "neutral"
        out["sentiment"] = {
            "score": round(max(-1.0, min(1.0, s_score)), 2),
            "label": s_label,
            "confidence": round(max(0.0, min(1.0, s_conf)), 2),
        }

        out["summary"] = str(out.get("summary","")).strip()
        return out
    except Exception:
        return None

# -------------------- Endpoint (TEXT ONLY) --------------------
@router.post("/analyze-text", response_model=NLPTextAnalysisResponse)
def analyze_text(
    body: NLPTextAnalysisRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    text = (body.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="text is required")

    # 1) Try OpenAI
    data = openai_analyze(text)

    if data is None:
        # 2) Fallback: heuristics
        entities = []
        add_vitals_and_meds(text, entities)
        entities = dedup_entities(entities)
        keywords = extract_keywords(text)[:8]
        sentiment = heuristic_sentiment(text)
        summary = heuristic_summary(text)

        return NLPTextAnalysisResponse(
            entities=entities,
            keywords=keywords,
            sentiment=sentiment,
            summary=summary
        )

    # 3) Augment LLM entities with regex vitals/meds
    ents = [NamedEntity(**e) for e in data.get("entities", [])]
    add_vitals_and_meds(text, ents)
    ents = dedup_entities(ents)

    return NLPTextAnalysisResponse(
        entities=ents,
        keywords=(data.get("keywords") or [])[:8],
        sentiment=SentimentResult(**data.get("sentiment")),
        summary=data.get("summary") or heuristic_summary(text),
    )
