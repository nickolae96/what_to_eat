import uuid

from datetime import date as date_type
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.auth import get_current_user
from app.core.database import get_db_session
from app.domain.nutrition.models import Food, FoodAlias, FoodEmbedding, Meal, MealItem
from app.domain.nutrition.llm import decompose_meal_text
from app.domain.nutrition.embedding import get_embedding
from app.domain.nutrition.schemas import (
    FoodAliasCreate,
    FoodAliasRead,
    FoodCreate,
    FoodRead,
    FoodUpdate,
    MealCreate,
    MealRead,
    IntakeResponse,
    IntakeRequest,
    SmartIntakeRequest,
    SmartIntakeItemResponse,
    SmartIntakeResponse,
)
from app.domain.nutrition.service import FoodMatcher, IntakeService
from app.domain.user.models import User
from app.domain.health.models import UserProfile

router = APIRouter(prefix="/nutrition", tags=["nutrition"])


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

        macros = IntakeService.compute_macros(food, item_data.quantity_g)
        meal_item = MealItem(
            meal_id=meal.id,
            food_id=food.id,
            quantity_g=item_data.quantity_g,
            calculated_calories=macros["calories"],
            calculated_protein_g=macros["protein_g"],
            calculated_carbs_g=macros["carbs_g"],
            calculated_fat_g=macros["fat_g"],
        )
        db.add(meal_item)

        total_cal += macros["calories"]
        total_protein += macros["protein_g"]
        total_carbs += macros["carbs_g"]
        total_fat += macros["fat_g"]

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


@router.post("/intake", response_model=IntakeResponse, status_code=201)
async def log_intake(
    body: IntakeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """
    Accept a free-text food description, match it in the DB,
    create (or reuse) today's DailyLog, create a Meal + MealItem,
    and update the daily totals.
    """
    profile = await _get_profile_or_404(current_user, db)

    food = await FoodMatcher(db).match(body.raw_input)
    if food is None:
        raise HTTPException(status_code=404, detail=f"No food matched for '{body.raw_input}'")

    log_date = body.date or date_type.today()
    svc = IntakeService(db)
    daily_log = await svc.get_or_create_daily_log(profile, log_date)

    meal, meal_item, macros = await svc.create_meal_with_item(
        profile=profile,
        daily_log=daily_log,
        food=food,
        quantity_g=body.quantity_g,
        meal_type=body.meal_type,
        raw_input_text=body.raw_input,
    )

    await db.commit()
    await db.refresh(meal_item)

    return IntakeResponse(
        daily_log_id=str(daily_log.id),
        meal_id=str(meal.id),
        meal_item_id=str(meal_item.id),
        matched_food_name=food.name,
        quantity_g=body.quantity_g,
        calculated_calories=macros["calories"],
        calculated_protein_g=macros["protein_g"],
        calculated_carbs_g=macros["carbs_g"],
        calculated_fat_g=macros["fat_g"],
    )


@router.post("/intake/smart", response_model=SmartIntakeResponse, status_code=201)
async def smart_intake(
    body: SmartIntakeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """
    Accept free-form text (e.g. *"I had grilled chicken with rice and
    a side salad for lunch"*), send it to the configured LLM which
    decomposes it into individual food items with estimated quantities
    """

    profile = await _get_profile_or_404(current_user, db)

    try:
        parsed_items = await decompose_meal_text(body.text)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"LLM processing failed: {exc}")

    if not parsed_items:
        raise HTTPException(status_code=422, detail="LLM could not extract any food items from the text")

    log_date = body.date or date_type.today()
    svc = IntakeService(db)
    daily_log = await svc.get_or_create_daily_log(profile, log_date)

    matcher = FoodMatcher(db)
    result_items: list[SmartIntakeItemResponse] = []
    unmatched: list[str] = []

    for parsed in parsed_items:
        food = await matcher.match(parsed.food_name)
        if food is None:
            unmatched.append(parsed.food_name)
            continue

        meal, meal_item, macros = await svc.create_meal_with_item(
            profile=profile,
            daily_log=daily_log,
            food=food,
            quantity_g=parsed.quantity_g,
            meal_type=parsed.meal_type,
            raw_input_text=parsed.food_name,
        )

        result_items.append(
            SmartIntakeItemResponse(
                meal_id=str(meal.id),
                meal_item_id=str(meal_item.id),
                matched_food_name=food.name,
                food_name_from_llm=parsed.food_name,
                quantity_g=parsed.quantity_g,
                meal_type=parsed.meal_type,
                calculated_calories=macros["calories"],
                calculated_protein_g=macros["protein_g"],
                calculated_carbs_g=macros["carbs_g"],
                calculated_fat_g=macros["fat_g"],
            )
        )

    if not result_items:
        raise HTTPException(status_code=404, detail=f"No foods could be matched. Unrecognised items: {unmatched}")

    await db.commit()

    return SmartIntakeResponse(
        daily_log_id=str(daily_log.id),
        items=result_items,
        unmatched=unmatched,
    )


@router.post(
    "/foods/{food_id}/embedding",
    status_code=status.HTTP_201_CREATED,
    summary="Generate or refresh the pgvector embedding for a single food",
)
async def upsert_food_embedding(
    food_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    food_result = await db.execute(select(Food).where(Food.id == food_id))
    food = food_result.scalar_one_or_none()
    if food is None:
        raise HTTPException(status_code=404, detail="Food not found")

    text = " ".join(filter(None, [food.name, food.brand, food.category]))
    vector = await get_embedding(text)

    existing = await db.execute(select(FoodEmbedding).where(FoodEmbedding.food_id == food_id))
    emb = existing.scalar_one_or_none()

    if emb is not None:
        emb.embedding = vector
    else:
        emb = FoodEmbedding(food_id=food_id, embedding=vector)
        db.add(emb)

    await db.flush()
    return {"food_id": str(food_id), "status": "ok"}


@router.post(
    "/foods/embeddings/refresh",
    status_code=status.HTTP_200_OK,
    summary="Regenerate embeddings for all foods",
)
async def refresh_all_embeddings(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    foods = (await db.execute(select(Food))).scalars().all()
    updated = 0
    for food in foods:
        text = " ".join(filter(None, [food.name, food.brand, food.category]))
        vector = await get_embedding(text)

        existing = await db.execute(select(FoodEmbedding).where(FoodEmbedding.food_id == food.id))
        emb = existing.scalar_one_or_none()

        if emb is not None:
            emb.embedding = vector
        else:
            db.add(FoodEmbedding(food_id=food.id, embedding=vector))

        updated += 1

    await db.flush()
    return {"updated": updated}
