from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app.models.ai_prediction import AIPrediction
from app.schemas.ai_prediction import AIPredictionCreate, AIPredictionUpdate, AIPredictionResponse
from app.core.database import get_db
from app.models.user import User
from app.dependencies.roles import get_current_user, role_required

router = APIRouter()

# ✅ Create prediction (admin/doctor only)
@router.post("/", response_model=AIPredictionResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(role_required(["admin", "doctor"]))])
def create_prediction(data: AIPredictionCreate, db: Session = Depends(get_db)):
    prediction = AIPrediction(**data.dict())
    db.add(prediction)
    db.commit()
    db.refresh(prediction)
    return prediction

# ✅ Get all predictions (admin/doctor)
@router.get("/", response_model=List[AIPredictionResponse], dependencies=[Depends(role_required(["admin", "doctor"]))])
def get_all_predictions(db: Session = Depends(get_db)):
    return db.query(AIPrediction).all()

# ✅ Get prediction by ID (admin/doctor/patient if their own)
@router.get("/{prediction_id}", response_model=AIPredictionResponse)
def get_prediction_by_id(
    prediction_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    prediction = db.query(AIPrediction).filter(AIPrediction.id == prediction_id).first()
    if not prediction:
        raise HTTPException(status_code=404, detail="Prediction not found")

    if current_user.role == "patient" and prediction.patient_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    return prediction

# ✅ Update prediction (admin/doctor only)
@router.put("/{prediction_id}", response_model=AIPredictionResponse, dependencies=[Depends(role_required(["admin", "doctor"]))])
def update_prediction(
    prediction_id: int,
    data: AIPredictionUpdate,
    db: Session = Depends(get_db)
):
    prediction = db.query(AIPrediction).filter(AIPrediction.id == prediction_id).first()
    if not prediction:
        raise HTTPException(status_code=404, detail="Prediction not found")

    for key, value in data.dict(exclude_unset=True).items():
        setattr(prediction, key, value)

    db.commit()
    db.refresh(prediction)
    return prediction

# ✅ Delete prediction (admin only)
@router.delete("/{prediction_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(role_required(["admin"]))])
def delete_prediction(prediction_id: int, db: Session = Depends(get_db)):
    prediction = db.query(AIPrediction).filter(AIPrediction.id == prediction_id).first()
    if not prediction:
        raise HTTPException(status_code=404, detail="Prediction not found")
    db.delete(prediction)
    db.commit()
