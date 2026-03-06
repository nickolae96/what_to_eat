import logging
import re
import unicodedata
from datetime import date as date_type

from sqlalchemy import func, select, literal_column
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.nutrition.models import Food, FoodAlias, FoodEmbedding, Meal, MealItem
from app.domain.nutrition.embedding import get_embedding
from app.domain.health.models import UserProfile, DailyLog

logger = logging.getLogger(__name__)

SIMILARITY_GAP: float = 0.10


def normalize(text_val: str) -> str:
    """Lower-case, strip accents, collapse whitespace, remove punctuation."""
    text_val = unicodedata.normalize("NFKD", text_val)
    text_val = "".join(c for c in text_val if not unicodedata.combining(c))
    text_val = text_val.lower().strip()
    text_val = re.sub(r"[^\w\s]", "", text_val)
    text_val = re.sub(r"\s+", " ", text_val)
    return text_val


class FoodMatcher:
    """
    Resolve free-text input to a `Food`.
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def match(self, raw_input: str) -> Food | None:
        """Run every strategy in order; return the first hit or ``None``."""
        trimmed = raw_input.strip()
        if not trimmed:
            return None

        norm = normalize(trimmed)

        strategies = [
            self._by_exact_alias(trimmed),
            self._by_normalized_alias(norm),
            self._by_normalized_name(norm),
            self._by_tokens(norm),
            self._by_full_text(trimmed),
            self._by_semantic(trimmed),
        ]

        for strategy in strategies:
            food = await strategy
            if food is not None:
                return food

        return None

    async def _by_exact_alias(self, raw: str) -> Food | None:
        """Case-insensitive exact match against ``food_aliases.alias``."""
        stmt = (
            select(Food)
            .join(FoodAlias, FoodAlias.food_id == Food.id)
            .where(func.lower(FoodAlias.alias) == raw.lower())
            .limit(1)
        )
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def _by_normalized_alias(self, norm_input: str) -> Food | None:
        """Normalize every alias in the DB and compare to *norm_input*."""
        rows = (await self._db.execute(select(FoodAlias))).scalars().all()

        for alias_row in rows:
            if normalize(alias_row.alias) == norm_input:
                result = await self._db.execute(
                    select(Food).where(Food.id == alias_row.food_id)
                )
                return result.scalar_one_or_none()

        return None

    async def _by_normalized_name(self, norm_input: str) -> Food | None:
        """Normalize every ``foods.name`` and compare to *norm_input*."""
        rows = (await self._db.execute(select(Food))).scalars().all()

        for food in rows:
            if normalize(food.name) == norm_input:
                return food

        return None

    async def _by_tokens(self, norm_input: str) -> Food | None:
        """
        Split *norm_input* into tokens and require each to appear
        """
        tokens = norm_input.split()
        if not tokens:
            return None

        stmt = select(Food)
        for token in tokens:
            stmt = stmt.where(Food.name.ilike(f"%{token}%"))
        stmt = stmt.limit(5)

        candidates = list((await self._db.execute(stmt)).scalars().all())

        if len(candidates) == 1:
            return candidates[0]
        if len(candidates) > 1:
            return self._rank_candidates(candidates, tokens)

        return None

    async def _by_full_text(self, raw: str) -> Food | None:
        """
        'ts_rank' + 'plainto_tsquery' against the 'search_vector' column.
        """
        tsquery = func.plainto_tsquery("english", raw)
        rank = func.ts_rank(Food.search_vector, tsquery).label("rank")

        stmt = (
            select(Food, rank)
            .where(Food.search_vector.op("@@")(tsquery))
            .order_by(literal_column("rank").desc())
            .limit(1)
        )

        try:
            row = (await self._db.execute(stmt)).first()
        except Exception:
            return None

        if row is None:
            return None

        food, score = row
        return food if score > 0 else None


    async def _by_semantic(self, raw: str) -> Food | None:
        """
        Embed *raw* with OpenAI, then find the closest food embeddings
        via pgvector cosine distance.
        """
        try:
            query_vec = await get_embedding(raw)
        except Exception:
            logger.debug("Semantic strategy skipped – embedding unavailable", exc_info=True)
            return None

        distance = FoodEmbedding.embedding.cosine_distance(query_vec)

        stmt = select(FoodEmbedding.food_id, distance.label("distance")).order_by(distance).limit(3)

        try:
            rows = (await self._db.execute(stmt)).all()
        except Exception:
            logger.debug("Semantic strategy skipped – pgvector query failed", exc_info=True)
            return None

        if not rows:
            return None

        best_food_id, best_dist = rows[0]
        best_score = 1.0 - best_dist

        if best_score < 0.5:
            return None

        if len(rows) >= 2:
            second_score = 1.0 - rows[1][1]
            if best_score - second_score < SIMILARITY_GAP:
                return None

        result = await self._db.execute(select(Food).where(Food.id == best_food_id))
        return result.scalar_one_or_none()

    @staticmethod
    def _rank_candidates(candidates: list[Food], tokens: list[str]) -> Food:

        def _score(food: Food) -> tuple[int, int]:
            name_lower = food.name.lower()
            token_hits = sum(1 for t in tokens if t in name_lower)
            verified = int(food.is_verified)
            return token_hits, verified

        return max(candidates, key=_score)


class IntakeService:
    """Shared logic used by both ``log_intake`` and ``smart_intake`` endpoints."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    @staticmethod
    def compute_macros(food: Food, quantity_g: float) -> dict[str, float]:
        """Return cal / protein / carbs / fat for *quantity_g* of *food*."""
        factor = quantity_g / 100.0
        return {
            "calories": round(food.calories_per_100g * factor, 2),
            "protein_g": round(food.protein_per_100g * factor, 2),
            "carbs_g": round(food.carbs_per_100g * factor, 2),
            "fat_g": round(food.fat_per_100g * factor, 2),
        }

    async def get_or_create_daily_log(
        self,
        profile: UserProfile,
        log_date: date_type,
    ) -> DailyLog:
        """Return the existing DailyLog for *profile* + *log_date*, or create one."""
        stmt = select(DailyLog).where(
            DailyLog.profile_id == profile.id,
            DailyLog.date == log_date,
        )
        daily_log = (await self._db.execute(stmt)).scalar_one_or_none()
        if daily_log is None:
            daily_log = DailyLog(profile_id=profile.id, date=log_date)
            self._db.add(daily_log)
            await self._db.flush()
        return daily_log

    async def create_meal_with_item(
        self,
        *,
        profile: UserProfile,
        daily_log: DailyLog,
        food: Food,
        quantity_g: float,
        meal_type: str | None,
        raw_input_text: str,
    ) -> tuple[Meal, MealItem, dict[str, float]]:
        """Create a Meal + MealItem, update daily-log totals, return both rows and macros."""
        macros = self.compute_macros(food, quantity_g)

        meal = Meal(
            profile_id=profile.id,
            daily_log_id=daily_log.id,
            meal_type=meal_type,
            raw_input_text=raw_input_text,
            total_calories=macros["calories"],
            total_protein_g=macros["protein_g"],
            total_carbs_g=macros["carbs_g"],
            total_fat_g=macros["fat_g"],
        )
        self._db.add(meal)
        await self._db.flush()

        meal_item = MealItem(
            meal_id=meal.id,
            food_id=food.id,
            quantity_g=quantity_g,
            calculated_calories=macros["calories"],
            calculated_protein_g=macros["protein_g"],
            calculated_carbs_g=macros["carbs_g"],
            calculated_fat_g=macros["fat_g"],
        )
        self._db.add(meal_item)

        daily_log.total_calories = (daily_log.total_calories or 0) + macros["calories"]
        daily_log.total_protein_g = (daily_log.total_protein_g or 0) + macros["protein_g"]
        daily_log.total_carbs_g = (daily_log.total_carbs_g or 0) + macros["carbs_g"]
        daily_log.total_fat_g = (daily_log.total_fat_g or 0) + macros["fat_g"]

        await self._db.flush()

        return meal, meal_item, macros
