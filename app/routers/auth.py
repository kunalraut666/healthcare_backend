from fastapi import APIRouter, HTTPException, Depends, Request, status
from sqlalchemy.orm import Session
from datetime import timedelta
from app.schemas.user import UserCreate, UserLoginRequest, UserResponse
from app.schemas.token import TokenWithUser
from app.core.security import (
    hash_password, verify_password, create_access_token,
    create_refresh_session, verify_refresh_token, rotate_refresh_token,
    revoke_all_user_tokens
)
from app.models.user import User
from app.core.database import get_db
from app.dependencies.roles import get_current_user  # returns ORM User

router = APIRouter()

# -------- Register (unchanged) --------
@router.post("/register", response_model=UserResponse)
def register(user: UserCreate, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == user.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    new_user = User(
        name=user.name, email=user.email, password=hash_password(user.password),
        role=user.role, mobile=user.mobile, dob=user.dob, gender=user.gender
    )
    db.add(new_user); db.commit(); db.refresh(new_user)
    return new_user

# -------- Login -> issue access + refresh --------
@router.post("/login", response_model=TokenWithUser)
def login(credentials: UserLoginRequest, request: Request, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == credentials.email).first()
    if not user or not verify_password(credentials.password, user.password):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    # access token: keep sub=email (your existing convention)
    access = create_access_token(data={"sub": user.email, "role": user.role})

    # refresh session in DB
    refresh = create_refresh_session(
        db, user_id=user.id,
        user_agent=request.headers.get("user-agent"),
        ip=request.client.host if request.client else None,
    )

    user_out = UserResponse.from_orm(user)
    # frontend interceptor expects expires_in (sec) - give same as ACCESS_TOKEN_EXPIRE_MINUTES
    return {"access_token": access, "refresh_token": refresh, "token_type": "bearer",
            "expires_in": int(60*15), "user": user_out}

# -------- Me (unchanged) --------
@router.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)):
    return current_user

# -------- Refresh -> rotate refresh + new access --------
@router.post("/refresh")
def refresh(payload: dict, db: Session = Depends(get_db)):
    raw = (payload or {}).get("refresh_token")
    rt = verify_refresh_token(db, raw)
    if not rt:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token")

    # rotate refresh (replay-safe)
    new_refresh = rotate_refresh_token(db, rt)

    # issue new access; keep same subject convention (email in sub)
    user = db.get(User, rt.user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    access = create_access_token({"sub": user.email, "role": user.role})
    return {"access_token": access, "refresh_token": new_refresh, "expires_in": int(60*15)}

# -------- Logout (optional) -> revoke all refresh sessions --------
@router.post("/logout")
def logout(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    revoke_all_user_tokens(db, current_user.id)
    return {"ok": True}
