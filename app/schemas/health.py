from pydantic import BaseModel, Field
from datetime import date
from typing import Optional


class UserTargetsRead(BaseModel):
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


class UserTargetsOverride(BaseModel):
    calories: float = Field(gt=0)
    protein_g: Optional[float] = Field(default=None, gt=0)
    fat_g: Optional[float] = Field(default=None, gt=0)
    carbs_g: Optional[float] = Field(default=None, gt=0)

