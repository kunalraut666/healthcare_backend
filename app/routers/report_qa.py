# app/routers/report_qa.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional, List, Literal, Dict, Any
import os, re, json
from sqlalchemy import or_, and_
from app.core.database import get_db
from app.dependencies.roles import role_required, get_current_user
from app.models.user import User
from app.models.report_upload import ReportUpload
from app.models.report_qa import ReportQA, QAStatus
from app.schemas.report_qa import QAAskIn as ReportQAAsk, QAOut as ReportQAResponse
from app.models.notification import Notification
from app.core.llm import chat_json

router = APIRouter()

# ---------------- Notifications ----------------
try:
    # optional service; if present, this will send in-app/push/email as you implemented
    from app.services.notify import notify_user  # type: ignore
except Exception:  # fallback no-op
    def notify_user(user_id: int, title: str, body: str):
        return None

def notify_doctor_pending(report: ReportUpload, qa: ReportQA):
    # Report uploader is the treating doctor in this design
    title = f"Patient question requires review (Report #{report.id})"
    body = f"Question: {qa.question}\nReport Type: {report.report_type}\nStatus: Pending review."
    try:
        notify_user(report.uploaded_by_id, title, body)
    except Exception:
        ...

def notify_patient_resolution(report: ReportUpload, qa: ReportQA):
    title = f"Your question was {qa.status.value.replace('_',' ')} (Report #{report.id})"
    ans = qa.final_answer or ""
    body = f"Q: {qa.question}\nResult: {qa.status.value.replace('_',' ')}\nAnswer: {ans[:500]}"
    try:
        notify_user(report.patient_id, title, body)
    except Exception:
        ...

def push_notification(db: Session, *, user_id: int, n_type: str,
                      title: str, message: str,
                      ref_type: str | None = None, ref_id: int | None = None):
    n = Notification(
        user_id=user_id,
        type=n_type,
        title=title,
        message=message,
        ref_type=ref_type,
        ref_id=ref_id,
    )
    db.add(n)
    db.commit()

# -------- PDF utils --------
def extract_text(path: str) -> str:
    try:
        import fitz
        parts = []
        with fitz.open(path) as doc:
            for p in doc:
                parts.append(p.get_text("text") or "")
        t = "\n".join(parts)
        if t.strip():
            return t
    except Exception:
        ...
    from PyPDF2 import PdfReader
    with open(path, "rb") as f:
        pdf = PdfReader(f)
        return "\n".join(p.extract_text() or "" for p in pdf.pages)

def clean_text(t: str) -> str:
    t = t.replace("\u00ad", "")
    t = re.sub(r"(\w)-\s+(\w)", r"\1\2", t)
    t = re.sub(r"\s+", " ", t)
    return t.strip()

# -------- intent + criticality --------
Intent = Literal["meds", "labs", "summary", "generic"]
MED_Q = re.compile(r"\b(medication|medicine|drug|prescription|rx|tablet|tab|capsule|cap|inj)\b", re.I)
LAB_Q = re.compile(r"\b(result|lab|value|level|range|cbc|lft|rft|lipid|hba1c|hdl|ldl|triglyceride|glucose|potassium|sodium|bilirubin|creatinine)\b", re.I)
SUMMARY_Q = re.compile(r"\b(summary|summarize|key findings|overview|in short|brief)\b", re.I)

def detect_intent(q: str) -> Intent:
    ql = q.lower()
    if SUMMARY_Q.search(ql): return "summary"
    if MED_Q.search(ql): return "meds"
    if LAB_Q.search(ql): return "labs"
    return "generic"

CRITICAL_PATS = [
    r"\b(dose|dosage|mg|ml|increase|decrease|titrate)\b",
    r"\b(start|stop|continue)\b.*\b(medicine|medication|drug)\b",
    r"\b(emergency|urgent|severe|life[- ]threatening|anaphylaxis|stroke|heart attack|cancer|stage)\b",
    r"\b(pregnan(t|cy)|breastfeed|lactation)\b",
    r"\b(surgery|operate|operation|anesthesia)\b",
    r"\b(blood pressure|glucose|hbA1c|potassium|sodium|INR)\b.*\b(very high|very low|>|<)\b",
    r"\b(side effect|adverse|interaction|contraindication)\b",
]
def is_critical(q: str) -> bool:
    return any(re.search(p, q, re.I) for p in CRITICAL_PATS)

def trunc_tokens(s: str, max_tok: int) -> str:
    return s[: max_tok * 4]

def ensure_can_view_report(report: ReportUpload, user: User):
    if user.role == "admin":
        return
    if user.role == "doctor" and report.uploaded_by_id == user.id:
        return
    if user.role == "patient" and report.patient_id == user.id:
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

def ensure_can_moderate_report(report: ReportUpload, user: User):
    # Only uploader doctor (or admin) can approve/reject/delete
    if user.role == "admin":
        return
    if user.role == "doctor" and report.uploaded_by_id == user.id:
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")

# --------- Clinical Mode (LLM) ----------
def openai_clinical_answer(question: str, context: str, intent: Intent) -> Dict[str, Any]:
    # Stage 1: outline
    sys1 = 'Return STRICT JSON: {"outline": ["..."]} (<=6 bullets).'
    user1 = f"QUESTION:\n{question}\n\nCONTEXT (trimmed):\n{trunc_tokens(context, 4000)}"
    o1 = chat_json(sys1, user1, max_tokens=180)
    outline = o1.get("outline") if isinstance(o1, dict) else []
    if not isinstance(outline, list): outline = []

    # Stage 2: snippets
    sys2 = 'Select <=4 short snippets. STRICT JSON: {"snippets": ["..."]}'
    user2 = f"QUESTION:\n{question}\nOUTLINE:\n{json.dumps(outline)}\nREPORT (trimmed):\n{trunc_tokens(context, 8000)}"
    o2 = chat_json(sys2, user2, max_tokens=200)
    snippets = o2.get("snippets") if isinstance(o2, dict) else []
    if not snippets: snippets = [trunc_tokens(context, 1500)]
    focused = trunc_tokens("\n---\n".join(str(s)[:1600] for s in snippets), 3000)

    # Stage 3: final
    directive_generic = "Answer concisely using ONLY focused context. If not stated, say 'Not stated.'"
    directive_summary = "Give 3–5 sentences or 4–6 bullets summary from focused context."
    directive_meds = (
        "If meds are explicitly in the context, list as 'Name dose form freq' separated by '; '. "
        "If meds are not present but the question asks for 'what should he take', produce T2 clinical suggestions: "
        "medicines (generic names) with typical dose ranges, common side effects, and a brief monitoring plan. "
        "Add clear disclaimer: 'Doctor review required.'"
    )
    directive_labs = "List 'test: value unit' pairs; if absent, 'Not stated.'"

    intent_dir = {
        "generic": directive_generic,
        "summary": directive_summary,
        "meds": directive_meds,
        "labs": directive_labs,
    }[intent]

    sys3 = (
        "You are a careful medical assistant. Use ONLY the focused context. "
        'Return STRICT JSON: {"answer": str, "confidence": number (0..1), '
        '"clinical_summary": str|null, "treatment_suggestions": str|null, '
        '"monitoring_plan": str|null, "side_effects": str|null, "red_flags": str|null, "follow_up": str|null}. '
        "If data not present, set fields to null."
    )
    user3 = f"FOCUSED CONTEXT:\n{focused}\n\nQUESTION:\n{question}\n\nINSTRUCTIONS:\n{intent_dir}\n"
    o3 = chat_json(sys3, user3, max_tokens=320)

    if not isinstance(o3, dict):
        return {"answer": "Not stated.", "confidence": 0.0}

    ans = str(o3.get("answer", "")).strip() or "Not stated."
    conf = float(o3.get("confidence", 0.0))

    if intent == "meds":
        # ensure disclaimer
        if ans.lower() != "not stated" and "Doctor review required." not in ans:
            ans = ans + " (Doctor review required.)"

    return {
        "answer": ans,
        "confidence": conf,
        "clinical_summary": o3.get("clinical_summary"),
        "treatment_suggestions": o3.get("treatment_suggestions"),
        "monitoring_plan": o3.get("monitoring_plan"),
        "side_effects": o3.get("side_effects"),
        "red_flags": o3.get("red_flags"),
        "follow_up": o3.get("follow_up"),
    }

# ---------------- Routes ----------------

@router.post(
    "/ask",
    response_model=ReportQAResponse,
    dependencies=[Depends(role_required(["admin","doctor","patient"]))],
)
def ask_question(
    payload: ReportQAAsk,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rpt = db.query(ReportUpload).get(payload.report_id)
    if not rpt:
        raise HTTPException(404, "Report not found")
    ensure_can_view_report(rpt, current_user)

    ctx = clean_text(extract_text(rpt.file_path))
    if not ctx.strip():
        raise HTTPException(400, "Empty document")

    intent = detect_intent(payload.question)
    res = openai_clinical_answer(payload.question, ctx, intent)

    draft = res.get("answer") or ""
    critical = is_critical(payload.question)

    # ---- NEW decision table (creator-private) ----
    if current_user.role in ("doctor", "admin"):
        # Doctor questions are always PRIVATE to doctor.
        status_val   = QAStatus.approved           # can keep 'approved' for convenience
        final_answer = draft                       # but list endpoint will hide from patient
        reviewed_by  = current_user.id
        reviewed_at  = datetime.utcnow()
    else:  # patient
        if critical:
            # Need HITL: visible to doctor for review, hidden from patient until approved.
            status_val   = QAStatus.pending_review
            final_answer = None
            reviewed_by  = None
            reviewed_at  = None
        else:
            # Non-critical: auto for patient, hidden from doctor by list filter.
            status_val   = QAStatus.approved
            final_answer = draft
            reviewed_by  = current_user.id
            reviewed_at  = datetime.utcnow()
    # ----------------------------------------------

    qa = ReportQA(
        report_id=rpt.id,
        question=payload.question,
        draft_answer=draft,
        final_answer=final_answer,
        status=status_val,
        clinical_summary=res.get("clinical_summary"),
        treatment_suggestions=res.get("treatment_suggestions"),
        monitoring_plan=res.get("monitoring_plan"),
        side_effects=res.get("side_effects"),
        red_flags=res.get("red_flags"),
        follow_up=res.get("follow_up"),
        created_by_id=current_user.id,
        reviewed_by_id=reviewed_by,
        reviewed_at=reviewed_at,
    )
    db.add(qa); db.commit(); db.refresh(qa)

    # ONLY when patient asked & marked pending_review (critical):
    if current_user.role == "patient" and status_val == QAStatus.pending_review:
        push_notification(
            db,
            user_id=rpt.uploaded_by_id,              # doctor/uploader
            n_type="qa_review",
            title=f"Approval needed for Report #{rpt.id}",
            message=f"Patient asked: {qa.question}",
            ref_type="report_qa",
            ref_id=qa.id,
        )

    return qa

@router.post(
    "/{qa_id}/approve",
    response_model=ReportQAResponse,
    dependencies=[Depends(role_required(["admin", "doctor"]))],
)
def approve_qa(
    qa_id: int,
    edited_answer: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    qa = db.query(ReportQA).get(qa_id)
    if not qa:
        raise HTTPException(404, "QA not found")

    rpt = db.query(ReportUpload).get(qa.report_id)
    if not rpt:
        raise HTTPException(404, "Report not found")
    ensure_can_moderate_report(rpt, current_user)

    qa.status = QAStatus.approved
    qa.final_answer = (edited_answer or qa.draft_answer or "").strip()
    qa.reviewed_by_id = current_user.id
    qa.reviewed_at = datetime.utcnow()
    db.commit()
    push_notification(
        db,
        user_id=rpt.patient_id,
        n_type="qa_status",
        title=f"Your question was approved (Report #{rpt.id})",
        message=(qa.final_answer or "")[:500],
        ref_type="report_qa",
        ref_id=qa.id,
    )
    db.refresh(qa)

    # notify patient
    notify_patient_resolution(rpt, qa)
    return qa

@router.post(
    "/{qa_id}/reject",
    response_model=ReportQAResponse,
    dependencies=[Depends(role_required(["admin", "doctor"]))],
)
def reject_qa(
    qa_id: int,
    reason: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    qa = db.query(ReportQA).get(qa_id)
    if not qa:
        raise HTTPException(404, "QA not found")

    rpt = db.query(ReportUpload).get(qa.report_id)
    if not rpt:
        raise HTTPException(404, "Report not found")
    ensure_can_moderate_report(rpt, current_user)

    qa.status = QAStatus.rejected
    qa.final_answer = (reason or "Rejected by reviewer.").strip()
    qa.reviewed_by_id = current_user.id
    qa.reviewed_at = datetime.utcnow()
    db.commit()
    push_notification(
        db,
        user_id=rpt.patient_id,
        n_type="qa_status",
        title=f"Your question was rejected (Report #{rpt.id})",
        message=qa.final_answer or "Rejected by reviewer.",
        ref_type="report_qa",
        ref_id=qa.id,
    )
    db.refresh(qa)

    # notify patient
    notify_patient_resolution(rpt, qa)
    return qa

@router.get(
    "/by-report/{report_id}",
    response_model=List[ReportQAResponse],
    dependencies=[Depends(role_required(["admin","doctor","patient"]))],
)
def list_qas(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rpt = db.query(ReportUpload).get(report_id)
    if not rpt:
        raise HTTPException(404, "Report not found")
    ensure_can_view_report(rpt, current_user)

    base = db.query(ReportQA).filter(ReportQA.report_id == report_id)

    if current_user.role == "patient":
        # Patient sees ONLY QAs created by themselves.
        # If critical → pending_review, show item but without final_answer.
        rows = (
            base.filter(ReportQA.created_by_id == current_user.id)
                .order_by(ReportQA.created_at.asc()).all()
        )
        out = []
        for qa in rows:
            out.append({
                "id": qa.id,
                "report_id": qa.report_id,
                "question": qa.question,
                "draft_answer": None,  # never show draft to patient
                "final_answer": qa.final_answer if qa.status == QAStatus.approved else None,
                "status": qa.status.value if hasattr(qa.status, "value") else qa.status,
                "clinical_summary": None,
                "treatment_suggestions": None,
                "monitoring_plan": None,
                "side_effects": None,
                "red_flags": None,
                "follow_up": None,
                "created_by_id": qa.created_by_id,
                "reviewed_by_id": qa.reviewed_by_id if qa.status == QAStatus.approved else None,
                "reviewed_at": qa.reviewed_at if qa.status == QAStatus.approved else None,
                "created_at": qa.created_at,
            })
        return out

    if current_user.role == "doctor":
        # Doctor sees:
        #   (a) QAs created by the doctor (private to doctor), and
        #   (b) Patient-created QAs that are pending_review (for HITL).
        rows = (
            base.filter(
                or_(
                    ReportQA.created_by_id == current_user.id,
                    and_(ReportQA.status == QAStatus.pending_review,
                         ReportQA.created_by_id == rpt.patient_id),
                )
            )
            .order_by(ReportQA.created_at.asc())
            .all()
        )
        return [
            {
                "id": qa.id,
                "report_id": qa.report_id,
                "question": qa.question,
                "draft_answer": qa.draft_answer,
                "final_answer": qa.final_answer,
                "status": qa.status.value if hasattr(qa.status, "value") else qa.status,
                "clinical_summary": qa.clinical_summary,
                "treatment_suggestions": qa.treatment_suggestions,
                "monitoring_plan": qa.monitoring_plan,
                "side_effects": qa.side_effects,
                "red_flags": qa.red_flags,
                "follow_up": qa.follow_up,
                "created_by_id": qa.created_by_id,
                "reviewed_by_id": qa.reviewed_by_id,
                "reviewed_at": qa.reviewed_at,
                "created_at": qa.created_at,
            }
            for qa in rows
        ]

    # admin -> everything
    rows = base.order_by(ReportQA.created_at.asc()).all()
    return [
        {
            "id": qa.id,
            "report_id": qa.report_id,
            "question": qa.question,
            "draft_answer": qa.draft_answer,
            "final_answer": qa.final_answer,
            "status": qa.status.value if hasattr(qa.status, "value") else qa.status,
            "clinical_summary": qa.clinical_summary,
            "treatment_suggestions": qa.treatment_suggestions,
            "monitoring_plan": qa.monitoring_plan,
            "side_effects": qa.side_effects,
            "red_flags": qa.red_flags,
            "follow_up": qa.follow_up,
            "created_by_id": qa.created_by_id,
            "reviewed_by_id": qa.reviewed_by_id,
            "reviewed_at": qa.reviewed_at,
            "created_at": qa.created_at,
        }
        for qa in rows
    ]

@router.delete(
    "/{qa_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(role_required(["admin", "doctor", "patient"]))],
)
def delete_qa(
    qa_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    qa = db.query(ReportQA).get(qa_id)
    if not qa:
        raise HTTPException(404, "QA not found")

    rpt = db.query(ReportUpload).get(qa.report_id)
    if not rpt:
        raise HTTPException(404, "Report not found")

    # Rules:
    # - admin/doctor (uploader doctor only): can delete any on this report
    # - patient: can delete only own QAs AND only if not approved
    if current_user.role in ("doctor", "admin"):
        ensure_can_moderate_report(rpt, current_user)
    else:
        if qa.created_by_id != current_user.id or qa.status == QAStatus.approved:
            raise HTTPException(403, "Not allowed to delete this item")

    db.delete(qa)
    db.commit()
    return

@router.delete(
    "/by-report/{report_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(role_required(["admin", "doctor"]))],
)
def delete_qas_for_report(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rpt = db.query(ReportUpload).get(report_id)
    if not rpt:
        return
    ensure_can_moderate_report(rpt, current_user)

    db.query(ReportQA).filter(ReportQA.report_id == report_id).delete(synchronize_session=False)
    db.commit()
    return
