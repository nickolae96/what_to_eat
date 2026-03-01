import uuid
from typing import Optional

from pydantic import BaseModel, Field


class FoodCreate(BaseModel):
    name: str
    brand: Optional[str] = None
    category: Optional[str] = None
    calories_per_100g: float = Field(ge=0)
    protein_per_100g: float = Field(ge=0)
    carbs_per_100g: float = Field(ge=0)
    fat_per_100g: float = Field(ge=0)
    fiber_per_100g: Optional[float] = Field(default=None, ge=0)
    source: Optional[str] = None
    is_verified: bool = True


class FoodUpdate(BaseModel):
    name: Optional[str] = None
    brand: Optional[str] = None
    category: Optional[str] = None
    calories_per_100g: Optional[float] = Field(default=None, ge=0)
    protein_per_100g: Optional[float] = Field(default=None, ge=0)
    carbs_per_100g: Optional[float] = Field(default=None, ge=0)
    fat_per_100g: Optional[float] = Field(default=None, ge=0)
    fiber_per_100g: Optional[float] = Field(default=None, ge=0)
    source: Optional[str] = None
    is_verified: Optional[bool] = None


class FoodAliasRead(BaseModel):
    id: uuid.UUID
    food_id: uuid.UUID
    alias: str

    model_config = {"from_attributes": True}


class FoodRead(BaseModel):
    id: uuid.UUID
    name: str
    brand: Optional[str] = None
    category: Optional[str] = None
    calories_per_100g: float
    protein_per_100g: float
    carbs_per_100g: float
    fat_per_100g: float
    fiber_per_100g: Optional[float] = None
    source: Optional[str] = None
    is_verified: bool
    aliases: list[FoodAliasRead] = []

    model_config = {"from_attributes": True}


class FoodAliasCreate(BaseModel):
    alias: str


class MealItemCreate(BaseModel):
    food_id: uuid.UUID
    quantity_g: float = Field(gt=0)


class MealItemRead(BaseModel):
    id: uuid.UUID
    meal_id: uuid.UUID
    food_id: uuid.UUID
    quantity_g: float
    calculated_calories: float
    calculated_protein_g: float
    calculated_carbs_g: float
    calculated_fat_g: float

    model_config = {"from_attributes": True}


class MealCreate(BaseModel):
    meal_type: Optional[str] = None
    raw_input_text: Optional[str] = None
    daily_log_id: Optional[uuid.UUID] = None
    items: list[MealItemCreate] = []


class MealRead(BaseModel):
    id: uuid.UUID
    profile_id: int
    daily_log_id: Optional[uuid.UUID] = None
    meal_type: Optional[str] = None
    raw_input_text: Optional[str] = None
    total_calories: float
    total_protein_g: float
    total_carbs_g: float
    total_fat_g: float
    items: list[MealItemRead] = []

    model_config = {"from_attributes": True}

