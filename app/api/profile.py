from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.database import get_db_session
from app.models.user import User, UserProfile, UserTargets
from app.schemas.user import UserProfileCreate, UserProfileRead, UserProfileUpdate
from app.schemas.health import UserTargetsRead, UserTargetsOverride
from app.services.health_engine import calculate_age, calculate_targets, calculate_manual_targets

router = APIRouter(prefix="/profile", tags=["profile"])

# Fields that, when changed, require targets to be recalculated
_TARGET_FIELDS = {"weight", "goal", "gender", "activity_level", "date_of_birth"}


async def _recalculate_targets(profile: UserProfile, db: AsyncSession) -> None:
    """Compute and insert a new UserTargets snapshot for the current profile state.

    Silently skips if the profile is missing gender, activity_level, or goal
    (targets simply cannot be calculated yet).
    """
    if profile.gender is None or profile.activity_level is None or profile.goal is None:
        return

    age = calculate_age(profile.date_of_birth)
    t = calculate_targets(
        weight_kg=profile.weight,
        height_cm=profile.height,
        age_years=age,
        gender=profile.gender,
        activity_level=profile.activity_level,
        goal=profile.goal,
    )

    targets = UserTargets(
        profile_id=profile.id,
        calories=t.calories,
        protein_g=t.protein_g,
        carbs_g=t.carbs_g,
        fat_g=t.fat_g,
        calculated_at=date.today(),
        based_on_weight=profile.weight,
        based_on_goal=profile.goal.value,
    )
    db.add(targets)
    await db.flush()


@router.post("", response_model=UserProfileRead, status_code=status.HTTP_201_CREATED)
async def create_profile(
    data: UserProfileCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    result = await db.execute(
        select(UserProfile).where(UserProfile.user_id == current_user.id)
    )
    if result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Profile already exists",
        )

    profile = UserProfile(
        user_id=current_user.id,
        date_of_birth=data.date_of_birth,
        gender=data.gender,
        weight=data.weight,
        height=data.height,
        goal=data.goal,
        activity_level=data.activity_level,
    )
    db.add(profile)
    await db.flush()
    await db.refresh(profile)

    await _recalculate_targets(profile, db)

    return profile


@router.get("", response_model=UserProfileRead)
async def get_profile(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    result = await db.execute(
        select(UserProfile).where(UserProfile.user_id == current_user.id)
    )
    profile = result.scalar_one_or_none()
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found",
        )
    return profile


@router.put("", response_model=UserProfileRead)
async def update_profile(
    data: UserProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    result = await db.execute(
        select(UserProfile).where(UserProfile.user_id == current_user.id)
    )
    profile = result.scalar_one_or_none()
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found",
        )

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(profile, field, value)

    await db.flush()
    await db.refresh(profile)

    if update_data.keys() & _TARGET_FIELDS:
        await _recalculate_targets(profile, db)

    return profile


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def delete_profile(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    result = await db.execute(
        select(UserProfile).where(UserProfile.user_id == current_user.id)
    )
    profile = result.scalar_one_or_none()
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found",
        )

    await db.delete(profile)
    await db.flush()


@router.get("/targets", response_model=UserTargetsRead)
async def get_current_targets(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    result = await db.execute(
        select(UserProfile).where(UserProfile.user_id == current_user.id)
    )
    profile = result.scalar_one_or_none()
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found",
        )

    result = await db.execute(
        select(UserTargets)
        .where(UserTargets.profile_id == profile.id)
        .order_by(UserTargets.id.desc())
        .limit(1)
    )
    targets = result.scalar_one_or_none()
    if targets is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No targets calculated yet",
        )
    return targets


@router.put("/targets", response_model=UserTargetsRead)
async def override_targets(
    data: UserTargetsOverride,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    result = await db.execute(
        select(UserProfile).where(UserProfile.user_id == current_user.id)
    )
    profile = result.scalar_one_or_none()
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found",
        )

    # Use user-provided macros, or fall back to weight-based defaults
    t = calculate_manual_targets(
        calories=data.calories,
        weight_kg=profile.weight,
        protein_g=data.protein_g,
        fat_g=data.fat_g,
        carbs_g=data.carbs_g,
    )

    targets = UserTargets(
        profile_id=profile.id,
        calories=t.calories,
        protein_g=t.protein_g,
        carbs_g=t.carbs_g,
        fat_g=t.fat_g,
        calculated_at=date.today(),
        based_on_weight=profile.weight,
        based_on_goal=profile.goal.value if profile.goal else "manual",
        is_manual=True,
    )
    db.add(targets)
    await db.flush()
    await db.refresh(targets)
    return targets


@router.get("/targets/history", response_model=list[UserTargetsRead])
async def get_targets_history(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    result = await db.execute(
        select(UserProfile).where(UserProfile.user_id == current_user.id)
    )
    profile = result.scalar_one_or_none()
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found",
        )

    result = await db.execute(
        select(UserTargets)
        .where(UserTargets.profile_id == profile.id)
        .order_by(UserTargets.id.desc())
    )
    return result.scalars().all()


