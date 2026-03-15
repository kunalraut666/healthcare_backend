from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional, List
import json, re

from app.core.database import get_db
from app.models.nlp_analysis import NLPAnalysis, AnalysisStatus
from app.schemas.nlp_analysis import (
    PatientAnalyzeRequest,
    NLPAnalysisOut,
    NLPAnalysisUpdateHITL,
    TriageResult,                 # NEW
)
from app.schemas.nlp_text import NamedEntity, SentimentResult
from app.models.user import User
from app.dependencies.roles import get_current_user, role_required
from app.services import nlp_utils as NU
from app.core.llm import chat_json  # already used in doctor flow
from app.models.notification import Notification
from app.utils.notify import create_notification_once


# optional audit log; ignore if not present
try:
    from app.models.audit_log import AuditLog
except Exception:
    AuditLog = None

try:
    from app.models.appointment import Appointment
except Exception:
    Appointment = None

router = APIRouter()

ALLOWED_TYPES = {"condition", "symptom", "medication", "vital_sign", "other"}

SYSTEM_INSTRUCT = """You are a medical NLP assistant. Given clinical text, extract:
1) entities: list of {text, type in [condition,symptom,medication,vital_sign,other], confidence (0..1)}
2) keywords: 5-10 important lowercase keywords
3) sentiment: {label in [positive,neutral,negative], score -1..1, confidence 0..1}
4) summary: 2 concise sentences.
Respond with STRICT JSON ONLY matching this schema:
{
  "entities": [{"text":"...", "type":"condition|symptom|medication|vital_sign|other", "confidence":0.95}],
  "keywords": ["..."],
  "sentiment": {"score": 0.2, "label": "neutral", "confidence": 0.78},
  "summary": "..."
}
"""

# ------------------ Helpers ------------------

def _find_target_doctors(db: Session, patient_id: int) -> list[int]:
    # 1) recent appointments
    if Appointment:
        since = datetime.utcnow() - timedelta(days=90)
        q = (db.query(Appointment.doctor_id)
               .filter(
                   Appointment.patient_id==patient_id,
                   Appointment.appointment_datetime >= since,
                   Appointment.status.in_(["scheduled","completed"])
               ).distinct())
        ids = [row[0] for row in q.all() if row[0]]
        if ids:
            return ids
    # 2) fallback: all doctors
    return [u.id for u in db.query(User).filter(User.role=="doctor").all()]

def _notify_doctors(db: Session, doctor_ids: list[int], analysis_id: int, triage_level: str, patient_name: str|None=None):
    title = "NLP review requested" if triage_level=="needs_review" else "Critical NLP alert"
    for did in doctor_ids:
        # DEDUP: same (user_id,type,ref_type,ref_id) ko last N seconds me repeat na bhejo
        create_notification_once(
            db,
            user_id=did,
            type="nlp_review",
            title=title,
            message=f"Patient NLP analysis requires review (triage: {triage_level}). {('Patient: '+patient_name) if patient_name else ''}".strip(),
            ref_type="nlp_analysis",
            ref_id=analysis_id,
            dedup_seconds=180,  # 3 min good default
        )

def _log_review_request(db: Session, user_id: int, analysis_id: int, patient_id: int, auto_level: str):
    """Try to write an audit log regardless of differing schema. If fields don't match, skip silently."""
    if not AuditLog:
        return
    msg = f"analysis_id={analysis_id} patient_id={patient_id}; auto={auto_level}"

    # try a few common shapes
    candidates = [
        dict(user_id=user_id, action="nlp_review_requested", details=msg),
        dict(user_id=user_id, action="nlp_review_requested", description=msg),
        dict(user_id=user_id, action="nlp_review_requested", message=msg),
        dict(user_id=user_id, event="nlp_review_requested", description=msg),
        dict(user_id=user_id, action="nlp_review_requested", data={"analysis_id": analysis_id, "patient_id": patient_id, "auto": auto_level}),
    ]
    for payload in candidates:
        try:
            rec = AuditLog(**payload)  # type: ignore
            db.add(rec)
            db.commit()
            return
        except TypeError:
            db.rollback()
        except Exception:
            db.rollback()
            return


def _openai_analyze(text: str) -> Optional[dict]:
    trimmed = text if len(text) <= 32000 else text[:32000]
    try:
        out = chat_json(SYSTEM_INSTRUCT, trimmed, max_tokens=400)
        if not isinstance(out, dict):
            return None

        # sanitize LLM output
        ents = []
        for e in out.get("entities", []):
            t = str(e.get("type", "other")).lower()
            if t not in ALLOWED_TYPES:
                t = "other"
            conf = float(e.get("confidence", 0.9))
            ents.append({"text": str(e.get("text", "")).strip(), "type": t, "confidence": conf})
        out["entities"] = ents

        kw = [str(k).lower() for k in (out.get("keywords") or [])][:10]
        out["keywords"] = kw

        sent = out.get("sentiment") or {}
        s_score = float(sent.get("score", 0.0))
        s_label = str(sent.get("label", "neutral")).lower()
        s_conf = float(sent.get("confidence", 0.7))
        if s_label not in {"positive", "neutral", "negative"}:
            s_label = "neutral"
        out["sentiment"] = {
            "score": max(-1.0, min(1.0, s_score)),
            "label": s_label,
            "confidence": max(0.0, min(1.0, s_conf)),
        }

        out["summary"] = str(out.get("summary", "")).strip()
        return out
    except Exception:
        return None


def _analyze_text_like_doctor(text: str):
    data = _openai_analyze(text)
    if data is None:
        # heuristics fallback
        ents: List[NamedEntity] = []
        NU.add_vitals_and_meds(text, ents)
        ents = NU.dedup_entities(ents)
        keywords = NU.extract_keywords(text)[:8]
        sentiment = NU.heuristic_sentiment(text)
        summary = NU.heuristic_summary(text)
        return ents, keywords, sentiment, summary

    ents = [NamedEntity(**e) for e in data.get("entities", [])]
    NU.add_vitals_and_meds(text, ents)
    ents = NU.dedup_entities(ents)
    return (
        ents,
        (data.get("keywords") or [])[:8],
        SentimentResult(**data.get("sentiment")),
        data.get("summary") or NU.heuristic_summary(text),
    )

# ---- Auto-triage ----

CRITICAL_KWS = {
    "chest pain","shortness of breath","severe pain","severe bleeding",
    "unconscious","stroke","heart attack","hemorrhage","suicidal"
}
REVIEW_KWS = {"infection","worsening","elevated","abnormal","positive","palpitations","syncope"}

def _extract_vitals_for_triage(text: str):
    bp = re.search(r"\b(\d{2,3})/(\d{2,3})\s?(?:mmhg)?\b", text, flags=re.I)
    hr = re.search(r"(?:^|\b)(?:hr|heart\s*rate)\s*[:\-]?\s*(\d{2,3})\b", text, flags=re.I)
    temp = re.search(r"\b(\d{2,3}(?:\.\d)?)\s?(?:°?\s?[cf]|celsius|fahrenheit)\b", text, flags=re.I)
    sbp = dbp = None
    if bp: sbp, dbp = int(bp.group(1)), int(bp.group(2))
    hr_v = int(hr.group(1)) if hr else None
    t = None
    if temp:
        val = float(temp.group(1))
        is_f = re.search(r"f(ahrenheit)?\b", temp.group(0), re.I)
        t = (val - 32) * 5/9 if is_f else val
    return sbp, dbp, hr_v, t

def _auto_triage(text: str, keywords: List[str], sentiment: SentimentResult) -> TriageResult:
    reasons = []
    sbp, dbp, hr, tc = _extract_vitals_for_triage(text)

    if sbp and dbp and (sbp >= 160 or dbp >= 100):
        reasons.append(f"High BP {sbp}/{dbp} mmHg")
    if hr and (hr >= 120 or hr <= 45):
        reasons.append(f"Abnormal HR {hr}")
    if tc and tc >= 39.5:
        reasons.append(f"High temperature {tc:.1f} C")

    if sentiment.score <= -0.25 or sentiment.label == "negative":
        reasons.append("Negative clinical sentiment")

    kwset = set(k.lower() for k in keywords)
    if kwset & {k.lower() for k in CRITICAL_KWS}:
        reasons.append("Critical keyword present")
    elif kwset & {k.lower() for k in REVIEW_KWS}:
        reasons.append("Potential issue keyword")

    if any(r.startswith(("High BP","Abnormal HR","High temperature")) or r=="Critical keyword present" for r in reasons):
        return TriageResult(level="critical", reasons=reasons, confidence=0.9)
    if reasons:
        return TriageResult(level="needs_review", reasons=reasons, confidence=0.8)
    return TriageResult(level="normal", reasons=[], confidence=0.9)

# ---- Normalize for response model ----

def _normalize_rec(rec: NLPAnalysis) -> NLPAnalysisOut:
    ents = rec.entities
    if isinstance(ents, str):
        try: ents = json.loads(ents)
        except Exception: ents = []
    kws = rec.keywords
    if isinstance(kws, str):
        try: kws = json.loads(kws)
        except Exception: kws = []
    sent = rec.sentiment
    if isinstance(sent, str):
        try: sent = json.loads(sent)
        except Exception: sent = {"score": 0.0, "label": "neutral", "confidence": 0.5}

    ents = [NamedEntity(**e) if not isinstance(e, NamedEntity) else e for e in (ents or [])]
    if not isinstance(sent, SentimentResult):
        sent = SentimentResult(**sent)

    status_value = rec.status.value if hasattr(rec.status, "value") else (rec.status or "draft")

    return NLPAnalysisOut(
        id=rec.id,
        patient_id=rec.patient_id,
        source_text=rec.source_text or "",
        entities=ents,
        keywords=kws or [],
        sentiment=sent,
        summary=rec.summary or "",
        status=status_value,
        triage=None,  # set later when needed
    )

# ------------------ Endpoints ------------------

@router.post("/analyze-text", response_model=NLPAnalysisOut)
def analyze_and_save(
    body: PatientAnalyzeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    text = (body.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="text is required")

    # resolve target patient
    if current_user.role == "patient":
        patient_id = current_user.id
    else:
        if not body.patient_id:
            raise HTTPException(status_code=400, detail="patient_id required")
        patient_id = body.patient_id

    # run analysis
    entities, keywords, sentiment, summary = _analyze_text_like_doctor(text)

    rec = NLPAnalysis(
        patient_id=patient_id,
        source_text=text,
        entities=[e.model_dump() for e in entities],
        keywords=keywords,
        sentiment=sentiment.model_dump(),
        summary=summary,
        status=AnalysisStatus.draft,
        created_by=current_user.id,
    )
    db.add(rec); db.commit(); db.refresh(rec)

    # ---- AUTO TRIAGE ----
    triage = _auto_triage(text, keywords, sentiment)

    # if review needed → set status reviewed + create audit log (doctor request)
    if triage.level in ("needs_review", "critical"):
        rec.status = AnalysisStatus.reviewed
        db.commit(); db.refresh(rec)
        _log_review_request(db, current_user.id, rec.id, patient_id, triage.level)
        
        # figure doctors and notify
        doctor_ids = _find_target_doctors(db, patient_id)
        patient_name = getattr(current_user, "full_name", None) or getattr(current_user, "name", None)
        _notify_doctors(db, doctor_ids, rec.id, triage.level, patient_name)

    out = _normalize_rec(rec)
    out.triage = triage
    return out


@router.get("/me", response_model=List[NLPAnalysisOut])
def my_analyses(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role == "patient":
        rows = (
            db.query(NLPAnalysis)
            .filter(NLPAnalysis.patient_id == current_user.id)
            .order_by(NLPAnalysis.id.desc())
            .all()
        )
    else:
        rows = db.query(NLPAnalysis).order_by(NLPAnalysis.id.desc()).all()
    outs = []
    for r in rows:
        o = _normalize_rec(r)
        # optional: light triage on list too (cheap heuristics)
        o.triage = None
        outs.append(o)
    return outs


@router.get("/{analysis_id}", response_model=NLPAnalysisOut)
def get_one(
    analysis_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rec = db.get(NLPAnalysis, analysis_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Not found")
    if current_user.role == "patient" and rec.patient_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden")
    out = _normalize_rec(rec)
    # recompute triage on demand
    out.triage = _auto_triage(rec.source_text or "", [*rec.keywords] if isinstance(rec.keywords, list) else [], out.sentiment)
    return out


@router.patch("/{analysis_id}", response_model=NLPAnalysisOut)
def hitl_update(
    analysis_id: int,
    body: NLPAnalysisUpdateHITL,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rec = db.get(NLPAnalysis, analysis_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Not found")
    if current_user.role == "patient" and rec.patient_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden")

    if body.entities is not None:
        rec.entities = [e.model_dump() for e in body.entities]
    if body.keywords is not None:
        rec.keywords = body.keywords[:10]
    if body.sentiment is not None:
        rec.sentiment = body.sentiment.model_dump()
    if body.summary is not None:
        rec.summary = body.summary.strip()
    if body.status is not None:
        rec.status = body.status

    db.commit(); db.refresh(rec)
    try:
        if current_user.role in ("doctor", "admin"):
            create_notification_once(
                db,
                user_id=rec.patient_id,
                type="nlp_updated",
                title="NLP analysis updated",
                message=f"Your analysis #{rec.id} was updated by a doctor.",
                ref_type="nlp_analysis",
                ref_id=rec.id,
                dedup_seconds=180,
            )
    except Exception:
        db.rollback()
    return _normalize_rec(rec)


@router.post(
    "/{analysis_id}/approve",
    response_model=NLPAnalysisOut,
    dependencies=[Depends(role_required(["doctor", "admin"]))],
)
def approve_final(
    analysis_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rec = db.get(NLPAnalysis, analysis_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Not found")
    rec.status = AnalysisStatus.final
    db.commit(); db.refresh(rec)
    try:
        create_notification_once(
            db,
            user_id=rec.patient_id,
            type="nlp_finalized",
            title="NLP analysis finalized",
            message=f"Your analysis #{rec.id} has been finalized by the doctor.",
            ref_type="nlp_analysis",
            ref_id=rec.id,
            dedup_seconds=300,  # thoda zyada bhi rakh sakte ho
        )
    except Exception:
        db.rollback()

    return _normalize_rec(rec)


# (optional) patient/doctor can explicitly request review
@router.post("/{analysis_id}/request-review", response_model=NLPAnalysisOut)
def request_review(
    analysis_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rec = db.get(NLPAnalysis, analysis_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Not found")
    if current_user.role == "patient" and rec.patient_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden")

    rec.status = AnalysisStatus.reviewed
    db.commit(); db.refresh(rec)
    _log_review_request(db, current_user.id, rec.id, rec.patient_id, "manual")

    out = _normalize_rec(rec)
    out.triage = TriageResult(level="needs_review", reasons=["Manual review requested"], confidence=0.8)
    return out

@router.delete("/{analysis_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_analysis(
    analysis_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rec = db.get(NLPAnalysis, analysis_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Not found")

    # Patients: apna hi record delete kar sakte hain; 'final' lock
    if current_user.role == "patient":
        if rec.patient_id != current_user.id:
            raise HTTPException(status_code=403, detail="Forbidden")
        if str(rec.status) in ("final", getattr(AnalysisStatus, "final", "final")):
            raise HTTPException(status_code=400, detail="Final analyses cannot be deleted by patient")

    # Doctors/Admins: allowed
    db.delete(rec)
    db.commit()
    return