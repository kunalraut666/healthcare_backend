# app/routers/appointments.py

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
from app.models.appointment import Appointment
from app.schemas.appointment import AppointmentCreate, AppointmentUpdate, AppointmentResponse
from app.core.database import get_db
from app.models.user import User
from app.dependencies.roles import get_current_user  # keep the dependency (must return User)

router = APIRouter()

# --------------------------
# Helper
# --------------------------
def is_doctor(user: Optional[User]) -> bool:
    return getattr(user, "role", None) == "doctor"

def is_patient(user: Optional[User]) -> bool:
    return getattr(user, "role", None) == "patient"

# helper to serialize appointment with names
def serialize_appointment(a):
    # try attached relationship first, fallback to queries
    patient_name = None
    doctor_name = None
    try:
        patient_name = getattr(a, "patient", None) and getattr(a.patient, "name", None)
    except Exception:
        patient_name = None
    try:
        doctor_name = getattr(a, "doctor", None) and getattr(a.doctor, "name", None)
    except Exception:
        doctor_name = None

    # fallback if relationships are not loaded
    if not patient_name:
        # may be None; attempt safe attribute access
        patient_name = getattr(a, "patient_name", None) or None
    if not doctor_name:
        doctor_name = getattr(a, "doctor_name", None) or None

    return {
        "id": a.id,
        "patient_id": a.patient_id,
        "patient_name": patient_name or "Unknown",
        "doctor_id": a.doctor_id,
        "doctor_name": doctor_name or "Unknown",
        "appointment_datetime": a.appointment_datetime.isoformat() if a.appointment_datetime else None,
        "reason": a.reason,
        "status": a.status,
    }

# --------------------------
# GET /doctors
# Return list of doctors for patient dropdown
# --------------------------
@router.get("/doctors")
def list_doctors(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Returns list of doctors. Minimal info: id, name, specialty, available.
    Authenticated users only (so token required by get_current_user).
    """
    doctors = db.query(User).filter(User.role == "doctor").all()
    out = []
    for d in doctors:
        # normalize name
        name = getattr(d, "name", None) or f"{getattr(d,'first_name','')} {getattr(d,'last_name','')}".strip() or getattr(d, "email", "Unknown")
        out.append({
            "id": d.id,
            "name": name,
            "specialty": getattr(d, "specialty", "General"),
            "available": getattr(d, "available", True)
        })
    return out


# --------------------------
# POST /      (create appointment)
# Patient (from token) or admin can create appointment.
# --------------------------
@router.post("/", response_model=AppointmentResponse, status_code=status.HTTP_201_CREATED)
def create_appointment(
    data: AppointmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create an appointment.
    - If current_user is patient -> patient_id derived from token (client should NOT send patient_id).
    - If admin -> admin must provide patient_id in payload (if AppointmentCreate supports it).
    """
    if current_user is None:
        raise HTTPException(status_code=401, detail="Unauthorized")

    # Determine patient_id
    if is_patient(current_user):
        patient_id = current_user.id
    else:
        # admin case: try to get patient_id from payload; if not present, reject
        patient_id = getattr(data, "patient_id", None)
        if not patient_id:
            raise HTTPException(status_code=400, detail="patient_id is required when creating appointment as admin")

    # Validate doctor exists and is doctor
    doctor = db.query(User).filter(User.id == data.doctor_id, User.role == "doctor").first()
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")

    # Optional: check simple exact-time conflict for same doctor
    conflict = db.query(Appointment).filter(
        Appointment.doctor_id == data.doctor_id,
        Appointment.appointment_datetime == data.appointment_datetime,
        Appointment.status != "cancelled"
    ).first()
    if conflict:
        raise HTTPException(status_code=400, detail="Selected time slot is already taken")

    # Prepare appointment dict
    appt_dict = data.dict()
    appt_dict["patient_id"] = patient_id

    # create and save
    appointment = Appointment(**appt_dict)
    db.add(appointment)
    db.commit()
    db.refresh(appointment)
    return appointment


# optional: GET / -> admin/doctor list, include both names
@router.get("/", response_model=List[AppointmentResponse])
def get_all_appointments(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if current_user is None:
        raise HTTPException(status_code=401, detail="Unauthorized")
    if is_doctor(current_user):
        appts = db.query(Appointment).options(joinedload(Appointment.patient)).filter(Appointment.doctor_id == current_user.id).order_by(Appointment.appointment_datetime.asc()).all()
        return [serialize_appointment(a) for a in appts]
    if getattr(current_user, "role", None) != "admin":
        raise HTTPException(status_code=403, detail="Access denied")
    appts = db.query(Appointment).options(joinedload(Appointment.patient), joinedload(Appointment.doctor)).order_by(Appointment.appointment_datetime.asc()).all()
    return [serialize_appointment(a) for a in appts]


# GET /me -> patient's appointments, include doctor name
@router.get("/me")
def get_my_appointments(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if current_user is None:
        raise HTTPException(status_code=401, detail="Unauthorized")
    if not is_patient(current_user):
        raise HTTPException(status_code=403, detail="Only patients can access their appointments")

    # eager load doctor relationship
    appts = db.query(Appointment).options(joinedload(Appointment.doctor)).filter(Appointment.patient_id == current_user.id).order_by(Appointment.appointment_datetime.asc()).all()

    return [serialize_appointment(a) for a in appts]


# GET /doctor -> doctor's appointments, include patient name
@router.get("/doctor")
def get_doctor_appointments(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if current_user is None:
        raise HTTPException(status_code=401, detail="Unauthorized")
    if not is_doctor(current_user):
        raise HTTPException(status_code=403, detail="Only doctors can access this endpoint")

    # eager load patient relationship to avoid N+1 queries
    appts = db.query(Appointment).options(joinedload(Appointment.patient)).filter(Appointment.doctor_id == current_user.id).order_by(Appointment.appointment_datetime.asc()).all()

    return [serialize_appointment(a) for a in appts]

@router.patch("/{appointment_id}")
async def patch_appointment(
    appointment_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Partially update an appointment.
    Accepts JSON body with any of: status, notes, appointment_datetime, reason
    """
    appt = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    if not appt:
        raise HTTPException(status_code=404, detail="Appointment not found")

    if current_user is None:
        raise HTTPException(status_code=401, detail="Unauthorized")

    role = getattr(current_user, "role", None)

    # ---- permission on whose appointment ----
    if role == "doctor":
        if appt.doctor_id != current_user.id:
            raise HTTPException(status_code=403, detail="Not allowed to modify this appointment")
    elif role == "patient":
        if appt.patient_id != current_user.id:
            raise HTTPException(status_code=403, detail="Not allowed to modify this appointment")
    elif role == "admin":
        pass
    else:
        raise HTTPException(status_code=403, detail="Access denied")

    # ---- parse partial body ----
    body_bytes = await request.body()
    payload = await request.json() if body_bytes else {}

    allowed = {"status", "notes", "appointment_datetime", "reason"}
    updates = {k: v for k, v in payload.items() if k in allowed}

    if not updates:
        raise HTTPException(status_code=400, detail="No valid fields to update")

    from datetime import datetime

    def parse_dt(v: str):
        try:
            # 2025-12-02T11:30:00 -> works with fromisoformat
            return datetime.fromisoformat(v)
        except Exception:
            try:
                return datetime.strptime(v, "%Y-%m-%dT%H:%M:%S")
            except Exception:
                raise HTTPException(status_code=400, detail="Invalid datetime format")

    # ---- PATIENT: can reschedule or cancel only ----
    if role == "patient":
        # patient cannot touch notes/reason
        disallowed = set(updates.keys()) - {"status", "appointment_datetime"}
        if disallowed:
            raise HTTPException(
                status_code=403,
                detail="Patients can only change date/time or cancel their appointments",
            )

        # validate status if provided
        if "status" in updates:
            new_status = updates["status"]
            if new_status not in ("cancelled", "scheduled"):
                raise HTTPException(
                    status_code=403,
                    detail="Patients can only set status to 'scheduled' or 'cancelled'",
                )
            appt.status = new_status

        # allow changing date/time
        if "appointment_datetime" in updates:
            if not isinstance(updates["appointment_datetime"], str):
                raise HTTPException(status_code=400, detail="appointment_datetime must be a string")
            appt.appointment_datetime = parse_dt(updates["appointment_datetime"])

    # ---- DOCTOR / ADMIN: full update allowed (as before) ----
    else:
        for k, v in updates.items():
            if k == "appointment_datetime" and isinstance(v, str):
                appt.appointment_datetime = parse_dt(v)
            else:
                setattr(appt, k, v)

    db.add(appt)
    db.commit()
    db.refresh(appt)

    # serialize with names (same helper as earlier)
    def serialize(a):
        patient_name = getattr(a, "patient", None) and getattr(a.patient, "name", None)
        doctor_name = getattr(a, "doctor", None) and getattr(a.doctor, "name", None)
        return {
            "id": a.id,
            "patient_id": a.patient_id,
            "patient_name": patient_name or "Unknown",
            "doctor_id": a.doctor_id,
            "doctor_name": doctor_name or "Unknown",
            "appointment_datetime": a.appointment_datetime.isoformat() if a.appointment_datetime else None,
            "reason": a.reason,
            "status": a.status,
            "notes": getattr(a, "notes", None),
        }

    return serialize(appt)
