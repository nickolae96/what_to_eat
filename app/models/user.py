import enum

from sqlalchemy import Boolean, DateTime, String, func, Index, ForeignKey, Date, Float, Enum
from sqlalchemy.dialects.postgresql import CITEXT
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
from datetime import date


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


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(CITEXT, unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[date] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[date] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    profile: Mapped["UserProfile"] = relationship(
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_users_email", "email"),
    )


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
    user: Mapped["User"] = relationship(back_populates="profile")
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
