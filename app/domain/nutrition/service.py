import re
import unicodedata

from sqlalchemy import func, select, literal_column
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.nutrition.models import Food, FoodAlias


def normalize(text_val: str) -> str:
    """Lower-case, strip accents, collapse whitespace, remove punctuation."""
    text_val = unicodedata.normalize("NFKD", text_val)
    text_val = "".join(c for c in text_val if not unicodedata.combining(c))
    text_val = text_val.lower().strip()
    text_val = re.sub(r"[^\w\s]", "", text_val)
    text_val = re.sub(r"\s+", " ", text_val)
    return text_val


async def _match_by_exact_alias(db: AsyncSession, raw: str) -> Food | None:
    """Case-insensitive exact match against ``food_aliases.alias``."""
    stmt = (
        select(Food)
        .join(FoodAlias, FoodAlias.food_id == Food.id)
        .where(func.lower(FoodAlias.alias) == raw.lower())
        .limit(1)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def _match_by_normalized_alias(db: AsyncSession, norm_input: str) -> Food | None:
    """Normalize every alias in the DB and compare to *norm_input*."""
    rows = (await db.execute(select(FoodAlias))).scalars().all()

    for alias_row in rows:
        if normalize(alias_row.alias) == norm_input:
            food_result = await db.execute(
                select(Food).where(Food.id == alias_row.food_id)
            )
            return food_result.scalar_one_or_none()

    return None


async def _match_by_normalized_name(db: AsyncSession, norm_input: str) -> Food | None:
    """Normalize every ``foods.name`` and compare to *norm_input*."""
    rows = (await db.execute(select(Food))).scalars().all()

    for food in rows:
        if normalize(food.name) == norm_input:
            return food

    return None


async def _match_by_tokens(db: AsyncSession, norm_input: str) -> Food | None:
    tokens = norm_input.split()
    if not tokens:
        return None

    stmt = select(Food)
    for token in tokens:
        stmt = stmt.where(Food.name.ilike(f"%{token}%"))
    stmt = stmt.limit(5)

    candidates = list((await db.execute(stmt)).scalars().all())

    if len(candidates) == 1:
        return candidates[0]
    if len(candidates) > 1:
        return _rank_candidates(candidates, tokens)

    return None


async def _match_by_full_text(db: AsyncSession, raw: str) -> Food | None:
    tsquery = func.plainto_tsquery("english", raw)
    rank = func.ts_rank(Food.search_vector, tsquery).label("rank")

    stmt = (
        select(Food, rank)
        .where(Food.search_vector.op("@@")(tsquery))
        .order_by(literal_column("rank").desc())
        .limit(1)
    )

    try:
        row = (await db.execute(stmt)).first()
    except Exception as e:
        return None

    if row is None:
        return None

    food, score = row
    return food if score > 0 else None


def _rank_candidates(candidates: list[Food], tokens: list[str]) -> Food:

    def _score(food: Food) -> tuple[int, int]:
        name_lower = food.name.lower()
        token_hits = sum(1 for t in tokens if t in name_lower)
        verified = int(food.is_verified)
        return token_hits, verified

    return max(candidates, key=_score)


async def match_food(db: AsyncSession, raw_input: str) -> Food | None:
    """
    Resolve a free-text string to a `Food`.
    """
    trimmed = raw_input.strip()
    if not trimmed:
        return None

    norm_input = normalize(trimmed)

    strategies = [
        lambda: _match_by_exact_alias(db, trimmed),
        lambda: _match_by_normalized_alias(db, norm_input),
        lambda: _match_by_normalized_name(db, norm_input),
        lambda: _match_by_tokens(db, norm_input),
        lambda: _match_by_full_text(db, trimmed),
    ]

    for strategy in strategies:
        food = await strategy()
        if food is not None:
            return food

    return None
