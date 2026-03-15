from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.core.database import get_db
from app.models.notification import Notification
from app.models.user import User
from app.dependencies.roles import get_current_user

router = APIRouter()

@router.get("/unread-count")
def unread_count(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return {"count": db.query(Notification).filter(
        Notification.user_id==current_user.id, Notification.is_read.is_(False)
    ).count()}

@router.get("", response_model=list[dict])
def list_my_notifications(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    rows = (db.query(Notification)
              .filter(Notification.user_id==current_user.id)
              .order_by(Notification.created_at.desc())
              .limit(25).all())
    return [dict(
        id=r.id, type=r.type, title=r.title, message=r.message,
        ref_type=r.ref_type, ref_id=r.ref_id, is_read=r.is_read,
        created_at=r.created_at.isoformat()
    ) for r in rows]

@router.post("/{nid}/read")
def mark_read(nid: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    n = db.get(Notification, nid)
    if not n or n.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Not found")
    n.is_read = True; db.commit()
    return {"ok": True}
