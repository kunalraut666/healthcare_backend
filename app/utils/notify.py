# app/utils/notify.py
from datetime import datetime, timedelta
from app.models.notification import Notification

def create_notification_once(db, *, user_id:int, type:str, title:str, message:str, ref_type:str, ref_id:int, dedup_seconds:int=120):
    since = datetime.utcnow() - timedelta(seconds=dedup_seconds)
    exists = (
        db.query(Notification)
          .filter(
              Notification.user_id==user_id,
              Notification.type==type,
              Notification.ref_type==ref_type,
              Notification.ref_id==ref_id,
              Notification.created_at >= since
          ).first()
    )
    if exists:
        return exists
    n = Notification(
        user_id=user_id, type=type, title=title, message=message,
        ref_type=ref_type, ref_id=ref_id
    )
    db.add(n); db.commit(); db.refresh(n)
    return n
