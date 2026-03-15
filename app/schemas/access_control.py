from pydantic import BaseModel

class AccessControlBase(BaseModel):
    user_id: int
    table_name: str
    can_read: bool
    can_write: bool
    can_delete: bool

class AccessControlCreate(AccessControlBase):
    pass

class AccessControlResponse(AccessControlBase):
    id: int

    class Config:
        from_attributes = True
