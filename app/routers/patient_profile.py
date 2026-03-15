from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.models.patient_profile import PatientProfile
from app.schemas.patient_profile import PatientProfileCreate, PatientProfileUpdate, PatientProfileResponse
from app.core.database import get_db
from app.dependencies.roles import get_current_user, role_required
from app.models.user import User

router = APIRouter()

# Create profile (Admin only)
@router.post("/", response_model=PatientProfileResponse, dependencies=[Depends(role_required(["admin"]))])
def create_profile(data: PatientProfileCreate, db: Session = Depends(get_db)):
    profile = PatientProfile(**data.dict())
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile

# Get all profiles (Admin/Doctor only)
@router.get("/", response_model=list[PatientProfileResponse], dependencies=[Depends(role_required(["admin", "doctor"]))])
def get_all_profiles(db: Session = Depends(get_db)):
    return db.query(PatientProfile).all()

# Get profile by ID (Admin/Doctor or patient for self)
@router.get("/{profile_id}", response_model=PatientProfileResponse)
def get_profile_by_id(
    profile_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    profile = db.query(PatientProfile).filter(PatientProfile.id == profile_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    if current_user.role == "patient" and current_user.id != profile.user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    return profile

# Update profile (Admin/Doctor only)
@router.put("/{profile_id}", response_model=PatientProfileResponse, dependencies=[Depends(role_required(["admin", "doctor"]))])
def update_profile(profile_id: int, data: PatientProfileUpdate, db: Session = Depends(get_db)):
    profile = db.query(PatientProfile).filter(PatientProfile.id == profile_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    for field, value in data.dict(exclude_unset=True).items():
        setattr(profile, field, value)

    db.commit()
    db.refresh(profile)
    return profile

# Delete profile (Admin only)
@router.delete("/{profile_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(role_required(["admin"]))])
def delete_profile(profile_id: int, db: Session = Depends(get_db)):
    profile = db.query(PatientProfile).filter(PatientProfile.id == profile_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    db.delete(profile)
    db.commit()
    return
