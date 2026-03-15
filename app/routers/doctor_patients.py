# app/routers/doctor_patients.py

from fastapi import APIRouter, Depends
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func as sa_func, and_
from datetime import datetime, date

from app.core.database import get_db
from app.dependencies.roles import get_current_user, role_required
from app.models.user import User
from app.models.appointment import Appointment
from app.models.medical_record import MedicalRecord

router = APIRouter()

from pydantic import BaseModel

class PatientCard(BaseModel):
    id: int
    name: str
    age: Optional[int] = None
    gender: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    lastVisit: Optional[str] = None
    condition: Optional[str] = None
    nextAppointment: Optional[str] = None
    class Config:
        from_attributes = True

def _parse_age(raw_dob: Optional[str]) -> Optional[int]:
    # DB screenshot me dob "DD/MM/YYYY" lag rahi thi
    if not raw_dob:
        return None
    try:
        if "-" in raw_dob:  # e.g., 1999-07-12
            y, m, d = [int(x) for x in raw_dob.split("-")]
        else:               # e.g., 12/07/1999
            d, m, y = [int(x) for x in raw_dob.split("/")]
        dob = date(y, m, d)
        today = date.today()
        return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
    except Exception:
        return None

@router.get(
    "/my-patients",
    response_model=List[PatientCard],
    dependencies=[Depends(role_required(["doctor"]))],
)
def get_doctor_my_patients(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    NO query params. Returns all distinct patients who have (or had) an appointment with the current doctor.
    Includes last past visit, next future appointment, and latest diagnosis.
    """

    now = datetime.utcnow()

    # distinct patients for this doctor
    sub_patients = (
        db.query(Appointment.patient_id.label("pid"))
        .filter(Appointment.doctor_id == current_user.id)
        .group_by(Appointment.patient_id)
        .subquery()
    )

    # last completed/past visit
    sub_last = (
        db.query(
            Appointment.patient_id.label("lv_pid"),
            sa_func.max(Appointment.appointment_datetime).label("last_visit"),
        )
        .filter(
            Appointment.doctor_id == current_user.id,
            Appointment.appointment_datetime <= now,
        )
        .group_by(Appointment.patient_id)
        .subquery()
    )

    # next upcoming visit
    sub_next = (
        db.query(
            Appointment.patient_id.label("nv_pid"),
            sa_func.min(Appointment.appointment_datetime).label("next_visit"),
        )
        .filter(
            Appointment.doctor_id == current_user.id,
            Appointment.appointment_datetime >= now,
        )
        .group_by(Appointment.patient_id)
        .subquery()
    )

    # latest medical record diagnosis per patient
    sub_latest_id = (
        db.query(
            MedicalRecord.patient_id.label("mr_pid"),
            sa_func.max(MedicalRecord.id).label("latest_id"),
        )
        .group_by(MedicalRecord.patient_id)
        .subquery()
    )
    sub_dx = (
        db.query(
            MedicalRecord.patient_id.label("dx_pid"),
            MedicalRecord.diagnosis.label("latest_dx"),
        )
        .join(
            sub_latest_id,
            and_(
                sub_latest_id.c.mr_pid == MedicalRecord.patient_id,
                sub_latest_id.c.latest_id == MedicalRecord.id,
            ),
        )
        .subquery()
    )

    # pick patient user fields (columns from your healthcare_users)
    rows = (
        db.query(
            User.id.label("uid"),
            User.name.label("name"),
            User.email.label("email"),
            User.mobile.label("phone"),     # matches your table
            User.gender.label("gender"),
            User.dob.label("dob"),          # string like "12/07/1999"
            sub_last.c.last_visit,
            sub_next.c.next_visit,
            sub_dx.c.latest_dx,
        )
        .join(sub_patients, sub_patients.c.pid == User.id)
        .outerjoin(sub_last, sub_last.c.lv_pid == User.id)
        .outerjoin(sub_next, sub_next.c.nv_pid == User.id)
        .outerjoin(sub_dx,   sub_dx.c.dx_pid   == User.id)
        .filter(User.role == "patient")
        .order_by(sa_func.coalesce(sub_next.c.next_visit, sub_last.c.last_visit).desc())
        .all()
    )

    out: List[PatientCard] = []
    for uid, name, email, phone, gender, dob, lastv, nextv, dx in rows:
        out.append(
            PatientCard(
                id=uid,
                name=name or "Patient",
                age=_parse_age(dob),
                gender=gender,
                phone=phone,
                email=email,
                lastVisit=(lastv.date().isoformat() if lastv else None),
                condition=dx,
                nextAppointment=(nextv.date().isoformat() if nextv else None),
            )
        )
    return out
