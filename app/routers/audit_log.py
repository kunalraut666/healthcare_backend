from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.models.audit_log import AuditLog
from app.schemas.audit_log import AuditLogCreate, AuditLogResponse
from app.core.database import get_db
from app.dependencies.roles import get_current_user, role_required
from app.models.user import User

router = APIRouter()

# ➕ Create log
@router.post("/", response_model=AuditLogResponse)
def create_log(
    data: AuditLogCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    log = AuditLog(
        user_id=current_user.id,
        action=data.action,
        description=data.description
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log

# 👁️ View logs (Admin only)
@router.get("/", response_model=list[AuditLogResponse], dependencies=[Depends(role_required(["admin"]))])
def get_all_logs(db: Session = Depends(get_db)):
    return db.query(AuditLog).all()
