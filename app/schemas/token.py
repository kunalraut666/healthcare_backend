# app/schemas/token.py
from pydantic import BaseModel
from typing import Optional
from app.schemas.user import UserResponse

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class TokenWithUser(Token):
    user: Optional[UserResponse] = None
