"""Mifflin-St Jeor BMR / TDEE calculator and goal-based macro targets."""

from dataclasses import dataclass
from datetime import date

from app.models.user import ActivityLevel, Gender, Goal

ACTIVITY_MULTIPLIER: dict[ActivityLevel, float] = {
    ActivityLevel.SEDENTARY: 1,
    ActivityLevel.LIGHTLY_ACTIVE: 1.2,
    ActivityLevel.MODERATELY_ACTIVE: 1.35,
    ActivityLevel.VERY_ACTIVE: 1.45,
    ActivityLevel.ATHLETE: 1.8,
}

GOAL_CALORIE_MULTIPLIER: dict[Goal, float] = {
    Goal.CUT: 0.825,
    Goal.MAINTAIN: 1.0,
    Goal.BULK: 1.15,
    Goal.RECOMP: 1.0,
}


def calculate_age(date_of_birth: date, today: date | None = None) -> int:
    if today is None:
        today = date.today()
    age = today.year - date_of_birth.year
    if (today.month, today.day) < (date_of_birth.month, date_of_birth.day):
        age -= 1
    return age


def calculate_bmr(
    weight_kg: float,
    height_cm: float,
    age_years: int,
    gender: Gender,
) -> float:
    """
    Mifflin-St Jeor equation.

    Male:   BMR = 10 × weight(kg) + 6.25 × height(cm) − 5 × age + 5
    Female: BMR = 10 × weight(kg) + 6.25 × height(cm) − 5 × age − 161
    """
    base = 10 * weight_kg + 6.25 * height_cm - 5 * age_years
    if gender == Gender.MALE:
        return round(base + 5, 2)
    return round(base - 161, 2)


def calculate_tdee(bmr: float, activity_level: ActivityLevel) -> float:
    return round(bmr * ACTIVITY_MULTIPLIER[activity_level], 2)


@dataclass
class Targets:
    calories: float
    protein_g: float
    fat_g: float
    carbs_g: float


def calculate_targets(
    weight_kg: float,
    height_cm: float,
    age_years: int,
    gender: Gender,
    activity_level: ActivityLevel,
    goal: Goal,
) -> Targets:
    """
    Compute daily macro targets based on TDEE and goal.
    """
    bmr = calculate_bmr(weight_kg, height_cm, age_years, gender)
    tdee = calculate_tdee(bmr, activity_level)

    calories = round(tdee * GOAL_CALORIE_MULTIPLIER[goal], 2)
    protein_g = round(weight_kg * 2.2, 2)
    fat_g = round(weight_kg * 0.8, 2)

    protein_calories = protein_g * 4
    fat_calories = fat_g * 9
    remaining_calories = calories - protein_calories - fat_calories
    carbs_g = round(remaining_calories / 4, 2)

    return Targets(
        calories=calories,
        protein_g=protein_g,
        fat_g=fat_g,
        carbs_g=carbs_g,
    )


def calculate_manual_targets(
    calories: float,
    weight_kg: float,
    protein_g: float | None = None,
    fat_g: float | None = None,
    carbs_g: float | None = None,
) -> Targets:
    """
        Build targets from a user-supplied calorie number.
    """
    protein_g = protein_g if protein_g is not None else round(weight_kg * 2.2, 2)
    fat_g = fat_g if fat_g is not None else round(weight_kg * 0.8, 2)

    if carbs_g is None:
        remaining = calories - protein_g * 4 - fat_g * 9
        carbs_g = round(max(remaining, 0) / 4, 2)

    return Targets(
        calories=calories,
        protein_g=protein_g,
        fat_g=fat_g,
        carbs_g=carbs_g,
    )

