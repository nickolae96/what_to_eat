import uuid

from pydantic import BaseModel, Field
from datetime import date
from typing import Optional

from app.domain.health.models import ActivityLevel, Goal, Gender


class ProfileCreate(BaseModel):
    date_of_birth: date
    gender: Optional[Gender] = None
    weight: float
    height: float
    goal: Optional[Goal] = None
    activity_level: Optional[ActivityLevel] = None


class ProfileUpdate(BaseModel):
    date_of_birth: Optional[date] = None
    gender: Optional[Gender] = None
    weight: Optional[float] = None
    height: Optional[float] = None
    goal: Optional[Goal] = None
    activity_level: Optional[ActivityLevel] = None


class ProfileRead(BaseModel):
    id: int
    user_id: int
    date_of_birth: date
    gender: Optional[Gender] = None
    weight: float
    height: float
    goal: Optional[Goal] = None
    activity_level: Optional[ActivityLevel] = None

    model_config = {"from_attributes": True}


class TargetsRead(BaseModel):
    id: int
    profile_id: int
    calories: float
    protein_g: float
    carbs_g: float
    fat_g: float
    calculated_at: date
    based_on_weight: float
    based_on_goal: str
    is_manual: bool

    model_config = {"from_attributes": True}


class TargetsOverride(BaseModel):
    calories: float = Field(gt=0)
    protein_g: Optional[float] = Field(default=None, gt=0)
    fat_g: Optional[float] = Field(default=None, gt=0)
    carbs_g: Optional[float] = Field(default=None, gt=0)


# ── DailyLog ──────────────────────────────────────────────────────────

class DailyLogCreate(BaseModel):
    date: date


class DailyLogRead(BaseModel):
    id: uuid.UUID
    profile_id: int
    date: date
    total_calories: float
    total_protein_g: float
    total_carbs_g: float
    total_fat_g: float

    model_config = {"from_attributes": True}


