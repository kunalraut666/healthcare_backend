# app/routers/medical_records.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app.models.medical_record import MedicalRecord
from app.schemas.medical_record import MedicalRecordCreate, MedicalRecordResponse, MedicalRecordUpdate
from app.core.database import get_db
from app.dependencies.roles import get_current_user, role_required
from app.models.user import User
from app.core.config import settings
from app.models.report_upload import ReportUpload
import os

router = APIRouter()

def _build_url(file_path: str) -> str:
    fname = os.path.basename(file_path).replace("\\", "/")
    return f"{settings.API_BASE_URL}/uploads/{fname}"

# ➕ Create record (Doctor only)
@router.post("/", response_model=MedicalRecordResponse, dependencies=[Depends(role_required(["doctor"]))])
def create_record(data: MedicalRecordCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    record = MedicalRecord(
        patient_id=data.patient_id,
        doctor_id=current_user.id,
        record_type=data.record_type,
        report_text=data.report_text,
        diagnosis=data.diagnosis,
        prescription=data.prescription,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record

# 📍 Get all (Doctor/Admin only)
@router.get("/", response_model=List[MedicalRecordResponse], dependencies=[Depends(role_required(["admin", "doctor"]))])
def get_all_records(db: Session = Depends(get_db)):
    return db.query(MedicalRecord).all()

# 👤 Patient: My Records Only
@router.get("/me", response_model=List[MedicalRecordResponse])
def get_my_records(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role != "patient":
        raise HTTPException(status_code=403, detail="Only patients can access this route")

    # Left join MedicalRecord -> ReportUpload (via source_upload_id)
    q = (
        db.query(
            MedicalRecord,
            ReportUpload.file_path.label("ru_file_path")
        )
        .outerjoin(
            ReportUpload,
            ReportUpload.id == MedicalRecord.source_upload_id
        )
        .filter(MedicalRecord.patient_id == current_user.id)
        .order_by(MedicalRecord.created_at.desc())
    )

    out = []
    for rec, ru_file_path in q.all():
        d = {
            "id": rec.id,
            "patient_id": rec.patient_id,
            "doctor_id": rec.doctor_id,
            "record_type": rec.record_type,
            "report_text": rec.report_text,
            "diagnosis": rec.diagnosis,
            "prescription": rec.prescription,
            "created_at": rec.created_at,
            "source_upload_id": rec.source_upload_id,
            "file_url": _build_url(ru_file_path) if ru_file_path else None,
        }
        out.append(d)
    return out

# 🔍 Get by ID (Patient=Own, Doctor/Admin=All)
@router.get("/{record_id}", response_model=MedicalRecordResponse)
def get_record_by_id(record_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    record = db.query(MedicalRecord).filter(MedicalRecord.id == record_id).first()

    if not record:
        raise HTTPException(status_code=404, detail="Record not found")

    if current_user.role == "patient" and current_user.id != record.patient_id:
        raise HTTPException(status_code=403, detail="Access denied")

    return record

# ✏️ Update (Doctor Only)
@router.put("/{record_id}", response_model=MedicalRecordResponse, dependencies=[Depends(role_required(["doctor"]))])
def update_record(record_id: int, data: MedicalRecordUpdate, db: Session = Depends(get_db)):
    record = db.query(MedicalRecord).filter(MedicalRecord.id == record_id).first()

    if not record:
        raise HTTPException(status_code=404, detail="Record not found")

    for field, value in data.dict(exclude_unset=True).items():
        setattr(record, field, value)

    db.commit()
    db.refresh(record)
    return record

# ❌ Delete (Admin Only)
@router.delete("/{record_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(role_required(["admin"]))])
def delete_record(record_id: int, db: Session = Depends(get_db)):
    record = db.query(MedicalRecord).filter(MedicalRecord.id == record_id).first()

    if not record:
        raise HTTPException(status_code=404, detail="Record not found")

    db.delete(record)
    db.commit()
    return
