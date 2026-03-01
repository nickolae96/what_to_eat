from __future__ import annotations

import enum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Date, Enum, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
from datetime import date

if TYPE_CHECKING:
    from app.domain.user.models import User


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

