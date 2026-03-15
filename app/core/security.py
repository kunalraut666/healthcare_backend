from passlib.context import CryptContext
from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt
from app.core.config import SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES
from sqlalchemy.orm import Session
from typing import Optional, Tuple
from app.models.refresh_token import RefreshToken  # <-- Step-1 me banaya hua model
import hashlib, uuid

# ---------- Password helpers ----------
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

# ---------- Access token (unchanged API) ----------
def _now():
    return datetime.now(timezone.utc)

def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    exp = _now() + (expires_delta or timedelta(minutes=int(ACCESS_TOKEN_EXPIRE_MINUTES)))
    to_encode.update({"exp": exp})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def decode_access_token(token: str):
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None

# ---------- Refresh token helpers (opaque string, stored hashed in DB) ----------
def _sha256(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def _new_refresh_raw() -> str:
    # opaque (non-JWT) random string
    return uuid.uuid4().hex + uuid.uuid4().hex

def create_refresh_session(
    db: Session,
    user_id: int,
    days_valid: int = 30,
    user_agent: Optional[str] = None,
    ip: Optional[str] = None,
) -> str:
    raw = _new_refresh_raw()
    rt = RefreshToken(
        user_id=user_id,
        token_hash=_sha256(raw),
        user_agent=(user_agent or "")[:200] or None,
        ip=(ip or "")[:64] or None,
        expires_at=_now() + timedelta(days=days_valid),
        revoked=False,
    )
    db.add(rt); db.commit()
    return raw

def verify_refresh_token(db: Session, raw: str) -> Optional[RefreshToken]:
    if not raw:
        return None
    h = _sha256(raw)
    rt = db.query(RefreshToken).filter(RefreshToken.token_hash == h).first()
    if not rt or rt.revoked or rt.expires_at <= _now():
        return None
    return rt

def rotate_refresh_token(db: Session, rt: RefreshToken, days_valid: int = 30) -> str:
    rt.revoked = True
    db.add(rt); db.flush()

    new_raw = _new_refresh_raw()
    new_rt = RefreshToken(
        user_id=rt.user_id,
        token_hash=_sha256(new_raw),
        user_agent=rt.user_agent,
        ip=rt.ip,
        expires_at=_now() + timedelta(days=days_valid),
        revoked=False,
    )
    db.add(new_rt); db.commit()
    return new_raw

def revoke_all_user_tokens(db: Session, user_id: int):
    db.query(RefreshToken).filter(
        RefreshToken.user_id == user_id, RefreshToken.revoked.is_(False)
    ).update({"revoked": True}, synchronize_session=False)
    db.commit()
