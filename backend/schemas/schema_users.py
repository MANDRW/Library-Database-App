from pydantic import BaseModel, EmailStr
from datetime import datetime
from decimal import Decimal
from schema_enums import AccessLevel

class UserBase(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr
    access_level: AccessLevel = AccessLevel.MEMBER

class UserCreate(UserBase):
    password: str

class User(UserBase):
    id: int
    is_active: bool
    fine: Decimal
    created_at: datetime

    class Config:
        from_attributes = True