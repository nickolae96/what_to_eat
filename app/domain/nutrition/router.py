import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.auth import get_current_user
from app.core.database import get_db_session
from app.domain.nutrition.models import Food, FoodAlias, Meal, MealItem
from app.domain.nutrition.schemas import (
    FoodAliasCreate,
    FoodAliasRead,
    FoodCreate,
    FoodRead,
    FoodUpdate,
    MealCreate,
    MealRead,
)
from app.domain.user.models import User
from app.domain.health.models import UserProfile

router = APIRouter(prefix="/nutrition", tags=["nutrition"])


# ── Food CRUD ─────────────────────────────────────────────────────────

@router.post("/foods", response_model=FoodRead, status_code=status.HTTP_201_CREATED)
async def create_food(
    data: FoodCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    food = Food(**data.model_dump())
    db.add(food)
    await db.flush()
    await db.refresh(food, attribute_names=["aliases"])
    return food


@router.get("/foods", response_model=list[FoodRead])
async def list_foods(
    q: str | None = None,
    category: str | None = None,
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db_session),
):
    stmt = select(Food).options(selectinload(Food.aliases))
    if q:
        stmt = stmt.where(Food.name.ilike(f"%{q}%"))
    if category:
        stmt = stmt.where(Food.category == category)
    stmt = stmt.offset(skip).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/foods/{food_id}", response_model=FoodRead)
async def get_food(
    food_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
):
    stmt = select(Food).options(selectinload(Food.aliases)).where(Food.id == food_id)
    result = await db.execute(stmt)
    food = result.scalar_one_or_none()
    if food is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Food not found")
    return food


@router.patch("/foods/{food_id}", response_model=FoodRead)
async def update_food(
    food_id: uuid.UUID,
    data: FoodUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    stmt = select(Food).options(selectinload(Food.aliases)).where(Food.id == food_id)
    result = await db.execute(stmt)
    food = result.scalar_one_or_none()
    if food is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Food not found")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(food, field, value)

    await db.flush()
    await db.refresh(food, attribute_names=["aliases"])
    return food


@router.delete("/foods/{food_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_food(
    food_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    stmt = select(Food).where(Food.id == food_id)
    result = await db.execute(stmt)
    food = result.scalar_one_or_none()
    if food is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Food not found")
    await db.delete(food)
    await db.flush()


# ── Food Alias ────────────────────────────────────────────────────────

@router.post("/foods/{food_id}/aliases", response_model=FoodAliasRead, status_code=status.HTTP_201_CREATED)
async def create_food_alias(
    food_id: uuid.UUID,
    data: FoodAliasCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    stmt = select(Food).where(Food.id == food_id)
    result = await db.execute(stmt)
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Food not found")

    alias = FoodAlias(food_id=food_id, alias=data.alias)
    db.add(alias)
    await db.flush()
    await db.refresh(alias)
    return alias


@router.delete("/foods/{food_id}/aliases/{alias_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_food_alias(
    food_id: uuid.UUID,
    alias_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    stmt = select(FoodAlias).where(FoodAlias.id == alias_id, FoodAlias.food_id == food_id)
    result = await db.execute(stmt)
    alias = result.scalar_one_or_none()
    if alias is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alias not found")
    await db.delete(alias)
    await db.flush()


# ── Meal CRUD ─────────────────────────────────────────────────────────

def _calculate_item_macros(food: Food, quantity_g: float) -> dict:
    factor = quantity_g / 100.0
    return {
        "calculated_calories": round(food.calories_per_100g * factor, 2),
        "calculated_protein_g": round(food.protein_per_100g * factor, 2),
        "calculated_carbs_g": round(food.carbs_per_100g * factor, 2),
        "calculated_fat_g": round(food.fat_per_100g * factor, 2),
    }


async def _get_profile_or_404(user: User, db: AsyncSession) -> UserProfile:
    result = await db.execute(
        select(UserProfile).where(UserProfile.user_id == user.id)
    )
    profile = result.scalar_one_or_none()
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found",
        )
    return profile


@router.post("/meals", response_model=MealRead, status_code=status.HTTP_201_CREATED)
async def create_meal(
    data: MealCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    profile = await _get_profile_or_404(current_user, db)

    meal = Meal(
        profile_id=profile.id,
        daily_log_id=data.daily_log_id,
        meal_type=data.meal_type,
        raw_input_text=data.raw_input_text,
    )
    db.add(meal)
    await db.flush()

    total_cal = total_protein = total_carbs = total_fat = 0.0

    for item_data in data.items:
        food_result = await db.execute(select(Food).where(Food.id == item_data.food_id))
        food = food_result.scalar_one_or_none()
        if food is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Food {item_data.food_id} not found",
            )

        macros = _calculate_item_macros(food, item_data.quantity_g)
        meal_item = MealItem(
            meal_id=meal.id,
            food_id=food.id,
            quantity_g=item_data.quantity_g,
            **macros,
        )
        db.add(meal_item)

        total_cal += macros["calculated_calories"]
        total_protein += macros["calculated_protein_g"]
        total_carbs += macros["calculated_carbs_g"]
        total_fat += macros["calculated_fat_g"]

    meal.total_calories = round(total_cal, 2)
    meal.total_protein_g = round(total_protein, 2)
    meal.total_carbs_g = round(total_carbs, 2)
    meal.total_fat_g = round(total_fat, 2)

    await db.flush()
    await db.refresh(meal, attribute_names=["items"])
    return meal


@router.get("/meals", response_model=list[MealRead])
async def list_meals(
    skip: int = 0,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    profile = await _get_profile_or_404(current_user, db)

    stmt = (
        select(Meal)
        .options(selectinload(Meal.items))
        .where(Meal.profile_id == profile.id)
        .offset(skip)
        .limit(limit)
    )
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/meals/{meal_id}", response_model=MealRead)
async def get_meal(
    meal_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    profile = await _get_profile_or_404(current_user, db)

    stmt = (
        select(Meal)
        .options(selectinload(Meal.items))
        .where(Meal.id == meal_id, Meal.profile_id == profile.id)
    )
    result = await db.execute(stmt)
    meal = result.scalar_one_or_none()
    if meal is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meal not found")
    return meal


@router.delete("/meals/{meal_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_meal(
    meal_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    profile = await _get_profile_or_404(current_user, db)

    stmt = select(Meal).where(Meal.id == meal_id, Meal.profile_id == profile.id)
    result = await db.execute(stmt)
    meal = result.scalar_one_or_none()
    if meal is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meal not found")
    await db.delete(meal)
    await db.flush()

