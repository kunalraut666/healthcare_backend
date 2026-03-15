from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.models.access_control import AccessControl
from app.schemas.access_control import AccessControlCreate, AccessControlResponse
from app.core.database import get_db

router = APIRouter()

@router.post("/access-controls", response_model=AccessControlResponse)
def create_access_control(data: AccessControlCreate, db: Session = Depends(get_db)):
    record = AccessControl(**data.dict())
    db.add(record)
    db.commit()
    db.refresh(record)
    return record