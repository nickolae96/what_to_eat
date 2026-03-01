import pytest
import uuid
from datetime import date
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.user.models import User
from app.domain.health.models import UserProfile, UserTargets, DailyLog, ActivityLevel, Goal, Gender
from app.core.auth import hash_password



class TestUserModel:
    async def test_create_user(self, db_session: AsyncSession):
        user = User(
            email="alice@example.com",
            hashed_password=hash_password("secret"),
        )
        db_session.add(user)
        await db_session.flush()
        await db_session.refresh(user)

        assert user.id is not None
        assert user.email == "alice@example.com"
        assert user.is_active is True
        assert user.created_at is not None

    async def test_user_email_unique(self, db_session: AsyncSession):
        u1 = User(email="dup@example.com", hashed_password="h1")
        u2 = User(email="dup@example.com", hashed_password="h2")
        db_session.add(u1)
        await db_session.flush()
        db_session.add(u2)
        with pytest.raises(Exception):  # IntegrityError
            await db_session.flush()
        await db_session.rollback()

    async def test_user_defaults(self, db_session: AsyncSession):
        user = User(email="bob@example.com", hashed_password="h")
        db_session.add(user)
        await db_session.flush()
        await db_session.refresh(user)

        assert user.is_active is True



class TestUserProfileModel:
    async def test_create_profile(self, db_session: AsyncSession):
        user = User(email="profile@example.com", hashed_password="h")
        db_session.add(user)
        await db_session.flush()
        await db_session.refresh(user)

        profile = UserProfile(
            user_id=user.id,
            date_of_birth=date(1990, 5, 15),
            gender=Gender.MALE,
            weight=75.5,
            height=180.0,
            goal=Goal.CUT,
            activity_level=ActivityLevel.MODERATELY_ACTIVE,
        )
        db_session.add(profile)
        await db_session.flush()
        await db_session.refresh(profile)

        assert profile.id is not None
        assert profile.user_id == user.id
        assert profile.date_of_birth == date(1990, 5, 15)
        assert profile.gender == Gender.MALE
        assert profile.weight == 75.5
        assert profile.height == 180.0
        assert profile.goal == Goal.CUT
        assert profile.activity_level == ActivityLevel.MODERATELY_ACTIVE

    async def test_profile_user_id_unique(self, db_session: AsyncSession):
        user = User(email="one@example.com", hashed_password="h")
        db_session.add(user)
        await db_session.flush()
        await db_session.refresh(user)

        p1 = UserProfile(user_id=user.id, date_of_birth=date(2000, 1, 1), weight=70, height=170)
        db_session.add(p1)
        await db_session.flush()

        p2 = UserProfile(user_id=user.id, date_of_birth=date(2000, 1, 1), weight=80, height=175)
        db_session.add(p2)
        with pytest.raises(Exception):
            await db_session.flush()
        await db_session.rollback()

    async def test_cascade_delete(self, db_session: AsyncSession):
        user = User(email="cascade@example.com", hashed_password="h")
        db_session.add(user)
        await db_session.flush()
        await db_session.refresh(user)

        profile = UserProfile(
            user_id=user.id,
            date_of_birth=date(1995, 3, 20),
            weight=65.0,
            height=165.0,
        )
        db_session.add(profile)
        await db_session.flush()
        await db_session.refresh(profile)
        profile_id = profile.id

        await db_session.delete(user)
        await db_session.flush()

        result = await db_session.execute(
            select(UserProfile).where(UserProfile.id == profile_id)
        )
        assert result.scalar_one_or_none() is None

    async def test_profile_relationship(self, db_session: AsyncSession):
        user = User(email="rel@example.com", hashed_password="h")
        db_session.add(user)
        await db_session.flush()
        await db_session.refresh(user)

        profile = UserProfile(
            user_id=user.id,
            date_of_birth=date(1988, 12, 1),
            weight=90.0,
            height=185.0,
            goal=Goal.BULK,
        )
        db_session.add(profile)
        await db_session.flush()

        # refresh user so the relationship is loaded
        await db_session.refresh(user, ["profile"])
        assert user.profile is not None
        assert user.profile.goal == Goal.BULK

    @pytest.mark.parametrize("level", list(ActivityLevel))
    async def test_activity_level_values(self, db_session: AsyncSession, level: ActivityLevel):
        user = User(email=f"{level.value}@example.com", hashed_password="h")
        db_session.add(user)
        await db_session.flush()
        await db_session.refresh(user)

        profile = UserProfile(
            user_id=user.id,
            date_of_birth=date(2000, 1, 1),
            weight=70,
            height=175,
            activity_level=level,
        )
        db_session.add(profile)
        await db_session.flush()
        await db_session.refresh(profile)

        assert profile.activity_level == level

    async def test_activity_level_nullable(self, db_session: AsyncSession):
        user = User(email="nolevel@example.com", hashed_password="h")
        db_session.add(user)
        await db_session.flush()
        await db_session.refresh(user)

        profile = UserProfile(
            user_id=user.id,
            date_of_birth=date(2000, 1, 1),
            weight=70,
            height=175,
        )
        db_session.add(profile)
        await db_session.flush()
        await db_session.refresh(profile)

        assert profile.activity_level is None

    @pytest.mark.parametrize("goal", list(Goal))
    async def test_goal_values(self, db_session: AsyncSession, goal: Goal):
        user = User(email=f"{goal.value}@example.com", hashed_password="h")
        db_session.add(user)
        await db_session.flush()
        await db_session.refresh(user)

        profile = UserProfile(
            user_id=user.id,
            date_of_birth=date(2000, 1, 1),
            weight=70,
            height=175,
            goal=goal,
        )
        db_session.add(profile)
        await db_session.flush()
        await db_session.refresh(profile)

        assert profile.goal == goal

    async def test_goal_nullable(self, db_session: AsyncSession):
        user = User(email="nogoal@example.com", hashed_password="h")
        db_session.add(user)
        await db_session.flush()
        await db_session.refresh(user)

        profile = UserProfile(
            user_id=user.id,
            date_of_birth=date(2000, 1, 1),
            weight=70,
            height=175,
        )
        db_session.add(profile)
        await db_session.flush()
        await db_session.refresh(profile)

        assert profile.goal is None

    @pytest.mark.parametrize("gender", list(Gender))
    async def test_gender_values(self, db_session: AsyncSession, gender: Gender):
        user = User(email=f"{gender.value}@example.com", hashed_password="h")
        db_session.add(user)
        await db_session.flush()
        await db_session.refresh(user)

        profile = UserProfile(
            user_id=user.id,
            date_of_birth=date(2000, 1, 1),
            weight=70,
            height=175,
            gender=gender,
        )
        db_session.add(profile)
        await db_session.flush()
        await db_session.refresh(profile)

        assert profile.gender == gender

    async def test_gender_nullable(self, db_session: AsyncSession):
        user = User(email="nogender@example.com", hashed_password="h")
        db_session.add(user)
        await db_session.flush()
        await db_session.refresh(user)

        profile = UserProfile(
            user_id=user.id,
            date_of_birth=date(2000, 1, 1),
            weight=70,
            height=175,
        )
        db_session.add(profile)
        await db_session.flush()
        await db_session.refresh(profile)

        assert profile.gender is None


async def _make_profile(db: AsyncSession, email: str = "daily@example.com") -> UserProfile:
    user = User(email=email, hashed_password="h")
    db.add(user)
    await db.flush()
    await db.refresh(user)

    profile = UserProfile(
        user_id=user.id,
        date_of_birth=date(1990, 1, 1),
        weight=75,
        height=180,
    )
    db.add(profile)
    await db.flush()
    await db.refresh(profile)
    return profile


class TestDailyLogModel:
    async def test_create_daily_log(self, db_session: AsyncSession):
        profile = await _make_profile(db_session)

        log = DailyLog(profile_id=profile.id, date=date(2026, 3, 1))
        db_session.add(log)
        await db_session.flush()
        await db_session.refresh(log)

        assert log.id is not None
        assert isinstance(log.id, uuid.UUID)
        assert log.profile_id == profile.id
        assert log.date == date(2026, 3, 1)

    async def test_daily_log_defaults(self, db_session: AsyncSession):
        profile = await _make_profile(db_session)

        log = DailyLog(profile_id=profile.id, date=date(2026, 3, 1))
        db_session.add(log)
        await db_session.flush()
        await db_session.refresh(log)

        assert log.total_calories == 0
        assert log.total_protein_g == 0
        assert log.total_carbs_g == 0
        assert log.total_fat_g == 0

    async def test_daily_log_uuid_auto_generated(self, db_session: AsyncSession):
        profile = await _make_profile(db_session)

        log1 = DailyLog(profile_id=profile.id, date=date(2026, 3, 1))
        log2 = DailyLog(profile_id=profile.id, date=date(2026, 3, 2))
        db_session.add_all([log1, log2])
        await db_session.flush()

        assert log1.id != log2.id

    async def test_unique_profile_date_constraint(self, db_session: AsyncSession):
        profile = await _make_profile(db_session)

        log1 = DailyLog(profile_id=profile.id, date=date(2026, 3, 1))
        db_session.add(log1)
        await db_session.flush()

        log2 = DailyLog(profile_id=profile.id, date=date(2026, 3, 1))
        db_session.add(log2)
        with pytest.raises(Exception):  # IntegrityError
            await db_session.flush()
        await db_session.rollback()

    async def test_different_profiles_same_date_allowed(self, db_session: AsyncSession):
        p1 = await _make_profile(db_session, email="user1@example.com")
        p2 = await _make_profile(db_session, email="user2@example.com")

        log1 = DailyLog(profile_id=p1.id, date=date(2026, 3, 1))
        log2 = DailyLog(profile_id=p2.id, date=date(2026, 3, 1))
        db_session.add_all([log1, log2])
        await db_session.flush()

        assert log1.id != log2.id

    async def test_daily_log_profile_relationship(self, db_session: AsyncSession):
        profile = await _make_profile(db_session)

        log = DailyLog(profile_id=profile.id, date=date(2026, 3, 1))
        db_session.add(log)
        await db_session.flush()
        await db_session.refresh(log, ["profile"])

        assert log.profile.id == profile.id

    async def test_profile_daily_logs_relationship(self, db_session: AsyncSession):
        profile = await _make_profile(db_session)

        db_session.add(DailyLog(profile_id=profile.id, date=date(2026, 3, 1)))
        db_session.add(DailyLog(profile_id=profile.id, date=date(2026, 3, 2)))
        await db_session.flush()
        await db_session.refresh(profile, ["daily_logs"])

        assert len(profile.daily_logs) == 2
        # ordered desc by date
        assert profile.daily_logs[0].date == date(2026, 3, 2)
        assert profile.daily_logs[1].date == date(2026, 3, 1)

    async def test_cascade_delete_profile_removes_daily_logs(self, db_session: AsyncSession):
        profile = await _make_profile(db_session)
        user_id = profile.user_id

        log = DailyLog(profile_id=profile.id, date=date(2026, 3, 1))
        db_session.add(log)
        await db_session.flush()
        log_id = log.id

        # delete user → cascades to profile → cascades to daily_logs
        result = await db_session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one()
        await db_session.delete(user)
        await db_session.flush()

        result = await db_session.execute(
            select(DailyLog).where(DailyLog.id == log_id)
        )
        assert result.scalar_one_or_none() is None

    async def test_daily_log_with_totals(self, db_session: AsyncSession):
        profile = await _make_profile(db_session)

        log = DailyLog(
            profile_id=profile.id,
            date=date(2026, 3, 1),
            total_calories=2200,
            total_protein_g=180,
            total_carbs_g=250,
            total_fat_g=70,
        )
        db_session.add(log)
        await db_session.flush()
        await db_session.refresh(log)

        assert log.total_calories == 2200
        assert log.total_protein_g == 180
        assert log.total_carbs_g == 250
        assert log.total_fat_g == 70

    async def test_daily_log_meals_relationship(self, db_session: AsyncSession):
        from app.domain.nutrition.models import Meal

        profile = await _make_profile(db_session)

        log = DailyLog(profile_id=profile.id, date=date(2026, 3, 1))
        db_session.add(log)
        await db_session.flush()

        meal = Meal(
            profile_id=profile.id,
            daily_log_id=log.id,
            meal_type="breakfast",
        )
        db_session.add(meal)
        await db_session.flush()
        await db_session.refresh(log, ["meals"])

        assert len(log.meals) == 1
        assert log.meals[0].meal_type == "breakfast"


