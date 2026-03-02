from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Float, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.domain.health.models import DailyLog, UserProfile


class Food(Base):
    __tablename__ = "foods"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String, index=True, nullable=False)
    brand: Mapped[str | None] = mapped_column(String, nullable=True)
    category: Mapped[str | None] = mapped_column(String, index=True, nullable=True)

    calories_per_100g: Mapped[float] = mapped_column(Float, nullable=False)
    protein_per_100g: Mapped[float] = mapped_column(Float, nullable=False)
    carbs_per_100g: Mapped[float] = mapped_column(Float, nullable=False)
    fat_per_100g: Mapped[float] = mapped_column(Float, nullable=False)
    fiber_per_100g: Mapped[float | None] = mapped_column(Float, nullable=True)

    source: Mapped[str | None] = mapped_column(String, nullable=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    search_vector: Mapped[str | None] = mapped_column(
        TSVECTOR, nullable=True
    )

    __table_args__ = (
        Index("ix_foods_search_vector", "search_vector", postgresql_using="gin"),
    )

    aliases: Mapped[list["FoodAlias"]] = relationship(
        "FoodAlias",
        back_populates="food",
        cascade="all, delete-orphan",
    )


class FoodAlias(Base):
    __tablename__ = "food_aliases"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    food_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("foods.id"), nullable=False)
    alias: Mapped[str] = mapped_column(String, index=True, nullable=False)

    food: Mapped["Food"] = relationship("Food", back_populates="aliases")


class Meal(Base):
    __tablename__ = "meals"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    profile_id: Mapped[int] = mapped_column(ForeignKey("user_profiles.id"), nullable=False)
    daily_log_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("daily_logs.id"), nullable=True
    )

    meal_type: Mapped[str | None] = mapped_column(String, nullable=True)
    raw_input_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    total_calories: Mapped[float] = mapped_column(Float, default=0)
    total_protein_g: Mapped[float] = mapped_column(Float, default=0)
    total_carbs_g: Mapped[float] = mapped_column(Float, default=0)
    total_fat_g: Mapped[float] = mapped_column(Float, default=0)

    items: Mapped[list["MealItem"]] = relationship(
        "MealItem",
        back_populates="meal",
        cascade="all, delete-orphan",
    )
    profile: Mapped["UserProfile"] = relationship("UserProfile", back_populates="meals")
    daily_log: Mapped["DailyLog | None"] = relationship("DailyLog", back_populates="meals")


class MealItem(Base):
    __tablename__ = "meal_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    meal_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("meals.id"), nullable=False)
    food_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("foods.id"), nullable=False)

    quantity_g: Mapped[float] = mapped_column(Float, nullable=False)

    calculated_calories: Mapped[float] = mapped_column(Float, nullable=False)
    calculated_protein_g: Mapped[float] = mapped_column(Float, nullable=False)
    calculated_carbs_g: Mapped[float] = mapped_column(Float, nullable=False)
    calculated_fat_g: Mapped[float] = mapped_column(Float, nullable=False)

    meal: Mapped["Meal"] = relationship("Meal", back_populates="items")
    food: Mapped["Food"] = relationship("Food")

