from __future__ import annotations

import enum
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Date, Enum, Float, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
from datetime import date

if TYPE_CHECKING:
    from app.domain.user.models import User
    from app.domain.nutrition.models import Meal


class ActivityLevel(str, enum.Enum):
    SEDENTARY = "sedentary"
    LIGHTLY_ACTIVE = "lightly_active"
    MODERATELY_ACTIVE = "moderately_active"
    VERY_ACTIVE = "very_active"
    ATHLETE = "athlete"


class Goal(str, enum.Enum):
    CUT = "cut"
    MAINTAIN = "maintain"
    BULK = "bulk"
    RECOMP = "recomp"


class Gender(str, enum.Enum):
    MALE = "male"
    FEMALE = "female"


ACTIVITY_MULTIPLIER: dict[ActivityLevel, float] = {
    ActivityLevel.SEDENTARY: 1.2,
    ActivityLevel.LIGHTLY_ACTIVE: 1.375,
    ActivityLevel.MODERATELY_ACTIVE: 1.55,
    ActivityLevel.VERY_ACTIVE: 1.725,
    ActivityLevel.ATHLETE: 1.9,
}

GOAL_CALORIE_MULTIPLIER: dict[Goal, float] = {
    Goal.CUT: 0.825,
    Goal.MAINTAIN: 1.0,
    Goal.BULK: 1.15,
    Goal.RECOMP: 1.0,
}


class UserProfile(Base):
    __tablename__ = "user_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    date_of_birth: Mapped[date] = mapped_column(Date, nullable=False)
    gender: Mapped[Gender | None] = mapped_column(Enum(Gender), nullable=True)
    weight: Mapped[float] = mapped_column(Float, nullable=False)
    height: Mapped[float] = mapped_column(Float, nullable=False)
    goal: Mapped[Goal | None] = mapped_column(Enum(Goal), nullable=True)
    activity_level: Mapped[ActivityLevel | None] = mapped_column(Enum(ActivityLevel), nullable=True)
    user: Mapped["User"] = relationship("User", back_populates="profile")
    targets: Mapped[list["UserTargets"]] = relationship(
        back_populates="profile",
        cascade="all, delete-orphan",
        order_by="desc(UserTargets.calculated_at)",
    )
    daily_logs: Mapped[list["DailyLog"]] = relationship(
        back_populates="profile",
        cascade="all, delete-orphan",
        order_by="desc(DailyLog.date)",
    )
    meals: Mapped[list["Meal"]] = relationship(
        back_populates="profile",
        cascade="all, delete-orphan",
    )


class UserTargets(Base):
    __tablename__ = "user_targets"

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("user_profiles.id"))
    calories: Mapped[float] = mapped_column(Float, nullable=False)
    protein_g: Mapped[float] = mapped_column(Float, nullable=False)
    carbs_g: Mapped[float] = mapped_column(Float, nullable=False)
    fat_g: Mapped[float] = mapped_column(Float, nullable=False)
    calculated_at: Mapped[date] = mapped_column(Date, nullable=False)
    based_on_weight: Mapped[float] = mapped_column(Float, nullable=False)
    based_on_goal: Mapped[str] = mapped_column(String(50), nullable=False)
    is_manual: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    profile: Mapped["UserProfile"] = relationship(back_populates="targets")


class DailyLog(Base):
    __tablename__ = "daily_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    profile_id: Mapped[int] = mapped_column(ForeignKey("user_profiles.id"), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)

    total_calories: Mapped[float] = mapped_column(Float, default=0)
    total_protein_g: Mapped[float] = mapped_column(Float, default=0)
    total_carbs_g: Mapped[float] = mapped_column(Float, default=0)
    total_fat_g: Mapped[float] = mapped_column(Float, default=0)

    profile: Mapped["UserProfile"] = relationship("UserProfile", back_populates="daily_logs")
    meals: Mapped[list["Meal"]] = relationship("Meal", back_populates="daily_log")

    __table_args__ = (
        UniqueConstraint("profile_id", "date", name="uq_profile_date"),
    )


