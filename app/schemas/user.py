from pydantic import BaseModel, EmailStr
from datetime import datetime, date
from typing import Optional

from app.models.user import ActivityLevel, Goal, Gender


class UserCreate(BaseModel):
    email: EmailStr
    password: str


class UserRead(BaseModel):
    id: int
    email: EmailStr
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenRefresh(BaseModel):
    refresh_token: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserProfileCreate(BaseModel):
    date_of_birth: date
    gender: Optional[Gender] = None
    weight: float
    height: float
    goal: Optional[Goal] = None
    activity_level: Optional[ActivityLevel] = None


class UserProfileUpdate(BaseModel):
    date_of_birth: Optional[date] = None
    gender: Optional[Gender] = None
    weight: Optional[float] = None
    height: Optional[float] = None
    goal: Optional[Goal] = None
    activity_level: Optional[ActivityLevel] = None


class UserProfileRead(BaseModel):
    id: int
    user_id: int
    date_of_birth: date
    gender: Optional[Gender] = None
    weight: float
    height: float
    goal: Optional[Goal] = None
    activity_level: Optional[ActivityLevel] = None

    model_config = {"from_attributes": True}

