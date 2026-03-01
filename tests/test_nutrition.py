import uuid

import pytest
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import hash_password
from app.domain.nutrition.models import Food, FoodAlias, Meal, MealItem
from app.domain.nutrition.schemas import (
    FoodAliasCreate,
    FoodAliasRead,
    FoodCreate,
    FoodRead,
    FoodUpdate,
    MealCreate,
    MealItemCreate,
    MealItemRead,
    MealRead,
)
from app.domain.user.models import User


def _make_food(**overrides) -> Food:
    defaults = dict(
        name="Chicken Breast",
        brand="Generic",
        category="meat",
        calories_per_100g=165.0,
        protein_per_100g=31.0,
        carbs_per_100g=0.0,
        fat_per_100g=3.6,
        fiber_per_100g=0.0,
        source="USDA",
        is_verified=True,
    )
    defaults.update(overrides)
    return Food(**defaults)


async def _persist_user(db: AsyncSession, email: str = "meal@example.com") -> User:
    user = User(email=email, hashed_password=hash_password("pw"))
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user


async def _persist_food(db: AsyncSession, **overrides) -> Food:
    food = _make_food(**overrides)
    db.add(food)
    await db.flush()
    await db.refresh(food)
    return food



class TestFoodModel:
    async def test_create_food(self, db_session: AsyncSession):
        food = _make_food()
        db_session.add(food)
        await db_session.flush()
        await db_session.refresh(food)

        assert food.id is not None
        assert isinstance(food.id, uuid.UUID)
        assert food.name == "Chicken Breast"
        assert food.brand == "Generic"
        assert food.category == "meat"
        assert food.calories_per_100g == 165.0
        assert food.protein_per_100g == 31.0
        assert food.carbs_per_100g == 0.0
        assert food.fat_per_100g == 3.6
        assert food.fiber_per_100g == 0.0
        assert food.source == "USDA"
        assert food.is_verified is True

    async def test_food_optional_fields(self, db_session: AsyncSession):
        food = Food(
            name="Mystery Powder",
            calories_per_100g=100,
            protein_per_100g=10,
            carbs_per_100g=20,
            fat_per_100g=5,
        )
        db_session.add(food)
        await db_session.flush()
        await db_session.refresh(food)

        assert food.brand is None
        assert food.category is None
        assert food.fiber_per_100g is None
        assert food.source is None
        assert food.is_verified is True  # default

    async def test_food_is_verified_default_true(self, db_session: AsyncSession):
        food = await _persist_food(db_session)
        assert food.is_verified is True

    async def test_food_uuid_auto_generated(self, db_session: AsyncSession):
        f1 = await _persist_food(db_session, name="Food A")
        f2 = await _persist_food(db_session, name="Food B")
        assert f1.id != f2.id


class TestFoodAliasModel:
    async def test_create_alias(self, db_session: AsyncSession):
        food = await _persist_food(db_session)

        alias = FoodAlias(food_id=food.id, alias="grilled chicken")
        db_session.add(alias)
        await db_session.flush()
        await db_session.refresh(alias)

        assert alias.id is not None
        assert isinstance(alias.id, uuid.UUID)
        assert alias.food_id == food.id
        assert alias.alias == "grilled chicken"

    async def test_alias_relationship_back_to_food(self, db_session: AsyncSession):
        food = await _persist_food(db_session)
        alias = FoodAlias(food_id=food.id, alias="pollo")
        db_session.add(alias)
        await db_session.flush()
        await db_session.refresh(alias, ["food"])

        assert alias.food.name == food.name

    async def test_food_aliases_relationship(self, db_session: AsyncSession):
        food = await _persist_food(db_session)
        db_session.add(FoodAlias(food_id=food.id, alias="alias1"))
        db_session.add(FoodAlias(food_id=food.id, alias="alias2"))
        await db_session.flush()
        await db_session.refresh(food, ["aliases"])

        assert len(food.aliases) == 2
        names = {a.alias for a in food.aliases}
        assert names == {"alias1", "alias2"}

    async def test_cascade_delete_food_removes_aliases(self, db_session: AsyncSession):
        food = await _persist_food(db_session)
        alias = FoodAlias(food_id=food.id, alias="to_be_deleted")
        db_session.add(alias)
        await db_session.flush()
        alias_id = alias.id

        await db_session.delete(food)
        await db_session.flush()

        result = await db_session.execute(
            select(FoodAlias).where(FoodAlias.id == alias_id)
        )
        assert result.scalar_one_or_none() is None


class TestMealModel:
    async def test_create_meal(self, db_session: AsyncSession):
        user = await _persist_user(db_session)

        meal = Meal(
            user_id=user.id,
            meal_type="breakfast",
            raw_input_text="eggs and toast",
        )
        db_session.add(meal)
        await db_session.flush()
        await db_session.refresh(meal)

        assert meal.id is not None
        assert isinstance(meal.id, uuid.UUID)
        assert meal.user_id == user.id
        assert meal.meal_type == "breakfast"
        assert meal.raw_input_text == "eggs and toast"

    async def test_meal_defaults(self, db_session: AsyncSession):
        user = await _persist_user(db_session)
        meal = Meal(user_id=user.id)
        db_session.add(meal)
        await db_session.flush()
        await db_session.refresh(meal)

        assert meal.total_calories == 0
        assert meal.total_protein_g == 0
        assert meal.total_carbs_g == 0
        assert meal.total_fat_g == 0
        assert meal.meal_type is None
        assert meal.raw_input_text is None

    async def test_meal_user_relationship(self, db_session: AsyncSession):
        user = await _persist_user(db_session)
        meal = Meal(user_id=user.id, meal_type="lunch")
        db_session.add(meal)
        await db_session.flush()
        await db_session.refresh(meal, ["user"])

        assert meal.user.email == "meal@example.com"

    async def test_cascade_delete_meal_removes_items(self, db_session: AsyncSession):
        user = await _persist_user(db_session)
        food = await _persist_food(db_session)

        meal = Meal(user_id=user.id)
        db_session.add(meal)
        await db_session.flush()

        item = MealItem(
            meal_id=meal.id,
            food_id=food.id,
            quantity_g=200,
            calculated_calories=330,
            calculated_protein_g=62,
            calculated_carbs_g=0,
            calculated_fat_g=7.2,
        )
        db_session.add(item)
        await db_session.flush()
        item_id = item.id

        await db_session.delete(meal)
        await db_session.flush()

        result = await db_session.execute(
            select(MealItem).where(MealItem.id == item_id)
        )
        assert result.scalar_one_or_none() is None


class TestMealItemModel:
    async def test_create_meal_item(self, db_session: AsyncSession):
        user = await _persist_user(db_session)
        food = await _persist_food(db_session)
        meal = Meal(user_id=user.id, meal_type="dinner")
        db_session.add(meal)
        await db_session.flush()

        item = MealItem(
            meal_id=meal.id,
            food_id=food.id,
            quantity_g=150.0,
            calculated_calories=247.5,
            calculated_protein_g=46.5,
            calculated_carbs_g=0.0,
            calculated_fat_g=5.4,
        )
        db_session.add(item)
        await db_session.flush()
        await db_session.refresh(item)

        assert item.id is not None
        assert isinstance(item.id, uuid.UUID)
        assert item.meal_id == meal.id
        assert item.food_id == food.id
        assert item.quantity_g == 150.0
        assert item.calculated_calories == 247.5
        assert item.calculated_protein_g == 46.5
        assert item.calculated_carbs_g == 0.0
        assert item.calculated_fat_g == 5.4

    async def test_meal_item_relationships(self, db_session: AsyncSession):
        user = await _persist_user(db_session)
        food = await _persist_food(db_session, name="Rice")
        meal = Meal(user_id=user.id)
        db_session.add(meal)
        await db_session.flush()

        item = MealItem(
            meal_id=meal.id,
            food_id=food.id,
            quantity_g=100,
            calculated_calories=130,
            calculated_protein_g=2.7,
            calculated_carbs_g=28,
            calculated_fat_g=0.3,
        )
        db_session.add(item)
        await db_session.flush()
        await db_session.refresh(item, ["meal", "food"])

        assert item.meal.id == meal.id
        assert item.food.name == "Rice"

    async def test_meal_items_list(self, db_session: AsyncSession):
        user = await _persist_user(db_session)
        food1 = await _persist_food(db_session, name="Eggs")
        food2 = await _persist_food(db_session, name="Bacon")
        meal = Meal(user_id=user.id)
        db_session.add(meal)
        await db_session.flush()

        for food in (food1, food2):
            db_session.add(MealItem(
                meal_id=meal.id,
                food_id=food.id,
                quantity_g=100,
                calculated_calories=100,
                calculated_protein_g=10,
                calculated_carbs_g=1,
                calculated_fat_g=7,
            ))
        await db_session.flush()
        await db_session.refresh(meal, ["items"])

        assert len(meal.items) == 2



class TestFoodCreateSchema:
    def test_valid_minimal(self):
        data = FoodCreate(
            name="Apple",
            calories_per_100g=52,
            protein_per_100g=0.3,
            carbs_per_100g=14,
            fat_per_100g=0.2,
        )
        assert data.name == "Apple"
        assert data.brand is None
        assert data.category is None
        assert data.fiber_per_100g is None
        assert data.source is None
        assert data.is_verified is True

    def test_valid_full(self):
        data = FoodCreate(
            name="Oatmeal",
            brand="Quaker",
            category="grains",
            calories_per_100g=389,
            protein_per_100g=16.9,
            carbs_per_100g=66.3,
            fat_per_100g=6.9,
            fiber_per_100g=10.6,
            source="USDA",
            is_verified=False,
        )
        assert data.brand == "Quaker"
        assert data.is_verified is False

    def test_negative_calories_rejected(self):
        with pytest.raises(ValidationError) as exc_info:
            FoodCreate(
                name="Bad",
                calories_per_100g=-1,
                protein_per_100g=0,
                carbs_per_100g=0,
                fat_per_100g=0,
            )
        assert "calories_per_100g" in str(exc_info.value)

    def test_negative_protein_rejected(self):
        with pytest.raises(ValidationError):
            FoodCreate(
                name="Bad",
                calories_per_100g=0,
                protein_per_100g=-5,
                carbs_per_100g=0,
                fat_per_100g=0,
            )

    def test_negative_carbs_rejected(self):
        with pytest.raises(ValidationError):
            FoodCreate(
                name="Bad",
                calories_per_100g=0,
                protein_per_100g=0,
                carbs_per_100g=-1,
                fat_per_100g=0,
            )

    def test_negative_fat_rejected(self):
        with pytest.raises(ValidationError):
            FoodCreate(
                name="Bad",
                calories_per_100g=0,
                protein_per_100g=0,
                carbs_per_100g=0,
                fat_per_100g=-1,
            )

    def test_negative_fiber_rejected(self):
        with pytest.raises(ValidationError):
            FoodCreate(
                name="Bad",
                calories_per_100g=0,
                protein_per_100g=0,
                carbs_per_100g=0,
                fat_per_100g=0,
                fiber_per_100g=-1,
            )

    def test_zero_values_accepted(self):
        data = FoodCreate(
            name="Water",
            calories_per_100g=0,
            protein_per_100g=0,
            carbs_per_100g=0,
            fat_per_100g=0,
            fiber_per_100g=0,
        )
        assert data.calories_per_100g == 0

    def test_missing_name_rejected(self):
        with pytest.raises(ValidationError):
            FoodCreate(
                calories_per_100g=100,
                protein_per_100g=10,
                carbs_per_100g=20,
                fat_per_100g=5,
            )

    def test_missing_required_macro_rejected(self):
        with pytest.raises(ValidationError):
            FoodCreate(name="Incomplete")


class TestFoodUpdateSchema:
    def test_all_optional(self):
        data = FoodUpdate()
        assert data.model_dump(exclude_unset=True) == {}

    def test_partial_update(self):
        data = FoodUpdate(name="Updated Name", calories_per_100g=200)
        dumped = data.model_dump(exclude_unset=True)
        assert dumped == {"name": "Updated Name", "calories_per_100g": 200}

    def test_negative_field_rejected(self):
        with pytest.raises(ValidationError):
            FoodUpdate(calories_per_100g=-10)


class TestFoodReadSchema:
    def test_from_attributes(self):
        food_id_outer = uuid.uuid4()
        alias_id = uuid.uuid4()

        class FakeAlias:
            id = alias_id
            food_id = food_id_outer
            alias = "pollo"

        class FakeFood:
            id = food_id_outer
            name = "Chicken"
            brand = None
            category = "meat"
            calories_per_100g = 165.0
            protein_per_100g = 31.0
            carbs_per_100g = 0.0
            fat_per_100g = 3.6
            fiber_per_100g = None
            source = "USDA"
            is_verified = True
            aliases = [FakeAlias()]

        data = FoodRead.model_validate(FakeFood())
        assert data.id == food_id_outer
        assert data.name == "Chicken"
        assert len(data.aliases) == 1
        assert data.aliases[0].alias == "pollo"

    def test_empty_aliases(self):
        food_id = uuid.uuid4()

        class FakeFood:
            id = food_id
            name = "Tofu"
            brand = None
            category = None
            calories_per_100g = 76
            protein_per_100g = 8
            carbs_per_100g = 1.9
            fat_per_100g = 4.8
            fiber_per_100g = None
            source = None
            is_verified = True
            aliases = []

        data = FoodRead.model_validate(FakeFood())
        assert data.aliases == []


class TestFoodAliasCreateSchema:
    def test_valid(self):
        data = FoodAliasCreate(alias="pollo")
        assert data.alias == "pollo"

    def test_missing_alias_rejected(self):
        with pytest.raises(ValidationError):
            FoodAliasCreate()


class TestFoodAliasReadSchema:
    def test_from_attributes(self):
        alias_id = uuid.uuid4()
        food_id_outer = uuid.uuid4()

        class FakeAlias:
            id = alias_id
            food_id = food_id_outer
            alias = "chicken breast"

        data = FoodAliasRead.model_validate(FakeAlias())
        assert data.id == alias_id
        assert data.food_id == food_id_outer
        assert data.alias == "chicken breast"


class TestMealItemCreateSchema:
    def test_valid(self):
        fid = uuid.uuid4()
        data = MealItemCreate(food_id=fid, quantity_g=200)
        assert data.food_id == fid
        assert data.quantity_g == 200

    def test_zero_quantity_rejected(self):
        with pytest.raises(ValidationError):
            MealItemCreate(food_id=uuid.uuid4(), quantity_g=0)

    def test_negative_quantity_rejected(self):
        with pytest.raises(ValidationError):
            MealItemCreate(food_id=uuid.uuid4(), quantity_g=-50)

    def test_missing_food_id_rejected(self):
        with pytest.raises(ValidationError):
            MealItemCreate(quantity_g=100)

    def test_missing_quantity_rejected(self):
        with pytest.raises(ValidationError):
            MealItemCreate(food_id=uuid.uuid4())


class TestMealItemReadSchema:
    def test_from_attributes(self):
        item_id = uuid.uuid4()
        meal_id_outer = uuid.uuid4()
        food_id_outer = uuid.uuid4()

        class FakeItem:
            id = item_id
            meal_id = meal_id_outer
            food_id = food_id_outer
            quantity_g = 150.0
            calculated_calories = 247.5
            calculated_protein_g = 46.5
            calculated_carbs_g = 0.0
            calculated_fat_g = 5.4

        data = MealItemRead.model_validate(FakeItem())
        assert data.id == item_id
        assert data.quantity_g == 150.0
        assert data.calculated_calories == 247.5


class TestMealCreateSchema:
    def test_valid_with_items(self):
        fid = uuid.uuid4()
        data = MealCreate(
            meal_type="lunch",
            raw_input_text="chicken and rice",
            items=[
                MealItemCreate(food_id=fid, quantity_g=200),
            ],
        )
        assert data.meal_type == "lunch"
        assert len(data.items) == 1

    def test_valid_no_items(self):
        data = MealCreate()
        assert data.meal_type is None
        assert data.raw_input_text is None
        assert data.items == []

    def test_valid_minimal(self):
        data = MealCreate(meal_type="snack")
        assert data.meal_type == "snack"
        assert data.items == []


class TestMealReadSchema:
    def test_from_attributes(self):
        meal_id_outer = uuid.uuid4()
        item_id_outer = uuid.uuid4()
        food_id_outer = uuid.uuid4()

        class FakeItem:
            id = item_id_outer
            meal_id = meal_id_outer
            food_id = food_id_outer
            quantity_g = 100.0
            calculated_calories = 165.0
            calculated_protein_g = 31.0
            calculated_carbs_g = 0.0
            calculated_fat_g = 3.6

        class FakeMeal:
            id = item_id_outer
            user_id = 1
            meal_type = "dinner"
            raw_input_text = "grilled chicken"
            total_calories = 165.0
            total_protein_g = 31.0
            total_carbs_g = 0.0
            total_fat_g = 3.6
            items = [FakeItem()]

        data = MealRead.model_validate(FakeMeal())
        assert data.id == item_id_outer
        assert data.user_id == 1
        assert data.meal_type == "dinner"
        assert len(data.items) == 1
        assert data.total_calories == 165.0

    def test_empty_items(self):
        meal_id = uuid.uuid4()

        class FakeMeal:
            id = meal_id
            user_id = 1
            meal_type = None
            raw_input_text = None
            total_calories = 0
            total_protein_g = 0
            total_carbs_g = 0
            total_fat_g = 0
            items = []

        data = MealRead.model_validate(FakeMeal())
        assert data.items == []
        assert data.total_calories == 0

