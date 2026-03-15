# app/routers/report_upload.py
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Form, status
from sqlalchemy.orm import Session
from sqlalchemy import func, case, and_
from app.core.database import get_db
from app.dependencies.roles import role_required, get_current_user
from app.models.user import User
from app.models.report_upload import ReportUpload
from app.models.report_qa import ReportQA, QAStatus
from app.schemas.report_upload import ReportUploadResponse
from app.models.medical_record import MedicalRecord
from app.models.notification import Notification

from app.core.config import settings
import os, shutil
from datetime import datetime

router = APIRouter()

# ---- Paths / URLs -----------------------------------------------------------
UPLOAD_DIR = settings.UPLOAD_DIR  # absolute path (config makes it absolute)
os.makedirs(UPLOAD_DIR, exist_ok=True)


def build_url(file_path: str) -> str:
    fname = os.path.basename(file_path).replace("\\", "/")
    return f"{settings.API_BASE_URL}/uploads/{fname}"

def safe_join_filename(original: str) -> str:
    name, ext = os.path.splitext(os.path.basename(original))
    path = os.path.join(UPLOAD_DIR, f"{name}{ext}")
    if not os.path.exists(path):
        return path
    stamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    return os.path.join(UPLOAD_DIR, f"{name}_{stamp}{ext}")

# ---- Helpers --------------------------------------------------------------
def ensure_can_view(r: ReportUpload, user: User) -> None:
    if user.role == "admin":
        return
    # patient can see only:
    # - reports shared to them, OR
    # - reports they uploaded themselves
    if user.role == "patient" and r.patient_id == user.id:
        if r.is_shared or r.uploaded_by_id == user.id:
            return
    # doctor can see only own uploads
    if user.role == "doctor" and r.uploaded_by_id == user.id:
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

def ensure_can_modify(r: ReportUpload, user: User) -> None:
    if user.role == "admin":
        return
    # only uploader doctor can modify/delete/share
    if user.role == "doctor" and r.uploaded_by_id == user.id:
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")

def ensure_can_delete(r: ReportUpload, user: User) -> None:
    if user.role == "admin":
        return
    if user.role == "doctor" and r.uploaded_by_id == user.id:
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only uploader or admin can delete")

def ensure_snapshot_in_medical_records(db: Session, upload: ReportUpload, doctor: User) -> None:
    """
    Doctor ne patient ko report 'share' ki to patient ke liye ek permanent snapshot
    medical_records me create/ensure karo. Re-run safe (unique by source_upload_id).
    """
    if not upload or not upload.patient_id:
        return

    # already exists? (unique by source_upload_id)
    existing = db.query(MedicalRecord).filter(
        MedicalRecord.source_upload_id == upload.id
    ).first()
    if existing:
        return

    rec = MedicalRecord(
        patient_id = upload.patient_id,
        doctor_id  = doctor.id,
        record_type= upload.report_type or "Report",
        report_text= upload.description or f"Report shared: #{upload.id}",
        diagnosis  = None,
        prescription = None,
        created_at = upload.shared_at or datetime.utcnow(),
        source_upload_id = upload.id,
    )
    db.add(rec)
    db.commit()

def push_notification(db: Session, user_id: int, title: str, message: str,
                      ntype: str = "report_shared", ref_type: str | None = None, ref_id: int | None = None):
    n = Notification(
        user_id=user_id,
        type=ntype,
        title=title,
        message=message,
        ref_type=ref_type,     # patient ko link dena hi nahi, isliye None rehne do
        ref_id=ref_id,
    )
    db.add(n)
    db.commit()
    

# ---- Endpoints --------------------------------------------------------------

@router.post(
    "/",
    response_model=ReportUploadResponse,
    dependencies=[Depends(role_required(["admin", "doctor", "patient"]))],
)
def upload_report(
    patient_id: int | None = Form(None),
    report_type: str = Form(...),
    file: UploadFile = File(...),
    description: str | None = Form(None),
    share_now: bool = Form(False),   # NEW
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    save_path = safe_join_filename(file.filename)
    with open(save_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # decide patient_id + share flags
    is_shared = False
    shared_at = None

    if current_user.role == "doctor":
        if not patient_id:
            raise HTTPException(400, "Doctor must select patient_id")
        # doctor may choose to share now
        is_shared = bool(share_now)
        shared_at = datetime.utcnow() if is_shared else None

    elif current_user.role == "patient":
        # patient uploads: always to self, and visible to self anyway
        patient_id = current_user.id
        # sharing flag is irrelevant for self-view; keep False so doctor cannot see by default
        # (change to True if you want doctor to see patient uploads by default)
        is_shared = False
        shared_at = None

    rpt = ReportUpload(
        patient_id=patient_id,
        uploaded_by_id=current_user.id,
        report_type=report_type,
        file_path=save_path,
        description=description,
        is_shared=is_shared,
        shared_at=shared_at,
    )
    db.add(rpt); db.commit(); db.refresh(rpt)
    
    if current_user.role == "doctor" and rpt.is_shared and rpt.patient_id:
        title = f"New report shared (#{rpt.id})"
        msg = f"Your doctor shared a '{rpt.report_type or 'report'}'. Please check your My Medical Records section."
        push_notification(db, user_id=rpt.patient_id, title=title, message=msg)
        ensure_snapshot_in_medical_records(db, rpt, current_user)

    return ReportUploadResponse(
        id=rpt.id,
        patient_id=rpt.patient_id,
        report_type=rpt.report_type,
        uploaded_by_id=rpt.uploaded_by_id,
        uploaded_at=rpt.uploaded_at,
        description=rpt.description,
        is_shared=rpt.is_shared,
        shared_at=rpt.shared_at,
        report_url=build_url(rpt.file_path),
    )

@router.get(
    "/",
    response_model=list[ReportUploadResponse],
    dependencies=[Depends(role_required(["admin", "doctor"]))],
)
def list_all_reports(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    patient_id: int | None = None,
):
    q = db.query(ReportUpload)

    if current_user.role == "doctor":
        q = q.filter(ReportUpload.uploaded_by_id == current_user.id)
        if patient_id:
            q = q.filter(ReportUpload.patient_id == patient_id)
    elif current_user.role == "admin" and patient_id:
        q = q.filter(ReportUpload.patient_id == patient_id)

    rows = q.order_by(ReportUpload.uploaded_at.desc()).all()
    return [
        ReportUploadResponse(
            id=r.id,
            patient_id=r.patient_id,
            report_type=r.report_type,
            uploaded_by_id=r.uploaded_by_id,
            uploaded_at=r.uploaded_at,
            description=r.description,
            report_url=build_url(r.file_path),
        )
        for r in rows
    ]

@router.get(
    "/{report_id}",
    response_model=ReportUploadResponse,
    dependencies=[Depends(role_required(["admin", "doctor", "patient"]))],
)
def get_report_by_id(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    r = db.query(ReportUpload).filter(ReportUpload.id == report_id).first()
    if not r:
        raise HTTPException(404, "Report not found")
    ensure_can_view(r, current_user)
    return ReportUploadResponse(
        id=r.id,
        patient_id=r.patient_id,
        report_type=r.report_type,
        uploaded_by_id=r.uploaded_by_id,
        uploaded_at=r.uploaded_at,
        description=r.description,
        is_shared=r.is_shared,
        shared_at=r.shared_at,
        report_url=build_url(r.file_path),
    )

@router.delete(
    "/{report_id}",
    status_code=204,
    dependencies=[Depends(role_required(["admin", "doctor"]))],
)
def delete_report(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    r = db.query(ReportUpload).filter(ReportUpload.id == report_id).first()
    if not r:
        raise HTTPException(404, "Report not found")
    ensure_can_modify(r, current_user)

    try:
        if os.path.exists(r.file_path):
            os.remove(r.file_path)
    finally:
        db.delete(r); db.commit()

# Doctor: list ALL uploaded reports with stats
@router.get("/doctor/list", dependencies=[Depends(role_required(["doctor", "admin"]))])
def list_reports_for_doctor(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    patient_id: int | None = None,
):
    qa_count_case = case(
        (ReportQA.created_by_id == current_user.id, 1),
        else_=0
    )
    
    pending_case = case(
        (and_(ReportQA.status == QAStatus.pending_review,
            ReportQA.created_by_id == ReportUpload.patient_id), 1),
        else_=0
        )
    
    q = (
        db.query(
            ReportUpload.id,
            ReportUpload.patient_id,
            ReportUpload.report_type,
            ReportUpload.file_path,
            ReportUpload.uploaded_at,
            ReportUpload.is_shared,
            ReportUpload.shared_at,
            func.sum(qa_count_case).label("qa_count"),   # ⬅️ REPLACED
            func.sum(pending_case).label("pending_count")
        )
        .outerjoin(ReportQA, ReportQA.report_id == ReportUpload.id)
        .group_by(ReportUpload.id)
        .order_by(ReportUpload.uploaded_at.desc())
    )

    if current_user.role == "doctor":
        q = q.filter(ReportUpload.uploaded_by_id == current_user.id)
        if patient_id:
            q = q.filter(ReportUpload.patient_id == patient_id)
    elif current_user.role == "admin" and patient_id:
        q = q.filter(ReportUpload.patient_id == patient_id)

    rows = q.all()
    out = []
    for r in rows:
        file_name = os.path.basename(r.file_path or "").replace("\\", "/")
        out.append(
            {
                "id": r.id,
                "patient_id": r.patient_id,
                "report_type": r.report_type,
                "uploaded_at": r.uploaded_at,
                "qa_count": int(r.qa_count or 0),
                "pending_count": int(r.pending_count or 0),
                "file_name": file_name,
                "title": f"{file_name or '#'+str(r.id)}",
                "report_url": build_url(r.file_path),
                "is_shared": bool(r.is_shared),
                "shared_at": r.shared_at,
            }
        )
    return out


# Patient: list ONLY my reports + only approved QAs count
@router.get("/patient/list", dependencies=[Depends(role_required(["patient"]))])
def list_reports_for_patient(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    approved_case = case(
        (and_(ReportQA.status == QAStatus.approved,
            ReportQA.created_by_id == current_user.id), 1),
        else_=0
    )
    
    rows = (
        db.query(
            ReportUpload.id,
            ReportUpload.report_type,
            ReportUpload.file_path,
            ReportUpload.uploaded_at,
            ReportUpload.uploaded_by_id,
            ReportUpload.is_shared,
            func.sum(approved_case).label("approved_count"),  # ⬅️ REPLACED
        )
        .outerjoin(ReportQA, ReportQA.report_id == ReportUpload.id)
        .filter(
            ReportUpload.patient_id == current_user.id,
            # doctor shared OR patient uploaded themselves
            (ReportUpload.is_shared == True) | (ReportUpload.uploaded_by_id == current_user.id)
        )
        .group_by(ReportUpload.id)
        .order_by(ReportUpload.uploaded_at.desc())
        .all()
    )

    out = []
    for r in rows:
        out.append(
            {
                "id": r.id,
                "report_type": r.report_type,
                "uploaded_at": r.uploaded_at,
                "approved_qas": int(r.approved_count or 0),
                "report_url": build_url(r.file_path),
                "is_shared": bool(r.is_shared),
            }
        )
    return out

@router.post(
    "/{report_id}/share",
    dependencies=[Depends(role_required(["doctor", "admin"]))],
)
def share_report(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    r = db.query(ReportUpload).filter(ReportUpload.id == report_id).first()
    if not r:
        raise HTTPException(404, "Report not found")
    ensure_can_modify(r, current_user)

    if not r.is_shared and r.patient_id:
        # 1) share flags first
        r.is_shared = True
        r.shared_at = datetime.utcnow()
        db.commit()

        # 2) snapshot ensure
        ensure_snapshot_in_medical_records(db, r, current_user)

        # 3) THEN notify
        title = f"New report shared (#{r.id})"
        msg = f"Your doctor shared a '{r.report_type or 'report'}'. Please check your My Medical Records section."
        push_notification(db, user_id=r.patient_id, title=title, message=msg)

    return {"ok": True, "is_shared": r.is_shared, "shared_at": r.shared_at}

@router.post(
    "/{report_id}/unshare",
    dependencies=[Depends(role_required(["doctor", "admin"]))],
)
def unshare_report(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    r = db.query(ReportUpload).filter(ReportUpload.id == report_id).first()
    if not r:
        raise HTTPException(404, "Report not found")
    ensure_can_modify(r, current_user)

    if r.is_shared:
        r.is_shared = False
        r.shared_at = None
        db.commit()
    return {"ok": True, "is_shared": r.is_shared}