import pytest
from datetime import date
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User, UserProfile
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
            weight=75.5,
            height=180.0,
            goal="lose weight",
        )
        db_session.add(profile)
        await db_session.flush()
        await db_session.refresh(profile)

        assert profile.id is not None
        assert profile.user_id == user.id
        assert profile.date_of_birth == date(1990, 5, 15)
        assert profile.weight == 75.5
        assert profile.height == 180.0
        assert profile.goal == "lose weight"

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
            goal="gain muscle",
        )
        db_session.add(profile)
        await db_session.flush()

        # refresh user so the relationship is loaded
        await db_session.refresh(user, ["profile"])
        assert user.profile is not None
        assert user.profile.goal == "gain muscle"

