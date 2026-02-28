import pytest
from datetime import date

from httpx import AsyncClient

from app.models.user import ActivityLevel, Gender, Goal
from app.services.health_engine import (
    calculate_age,
    calculate_bmr,
    calculate_tdee,
    calculate_targets,
    calculate_manual_targets,
    ACTIVITY_MULTIPLIER,
    GOAL_CALORIE_MULTIPLIER,
    Targets,
)


# ── calculate_age ─────────────────────────────────────────────────────────

class TestCalculateAge:
    def test_age_normal(self):
        assert calculate_age(date(1990, 1, 1), today=date(2026, 2, 26)) == 36

    def test_age_birthday_today(self):
        assert calculate_age(date(1990, 2, 26), today=date(2026, 2, 26)) == 36

    def test_age_birthday_tomorrow(self):
        assert calculate_age(date(1990, 2, 27), today=date(2026, 2, 26)) == 35

    def test_age_leap_year_birthday(self):
        assert calculate_age(date(2000, 2, 29), today=date(2026, 2, 28)) == 25

    def test_age_child(self):
        assert calculate_age(date(2020, 6, 15), today=date(2026, 2, 26)) == 5


# ── calculate_bmr ─────────────────────────────────────────────────────────

class TestCalculateBMR:
    def test_male_bmr(self):
        # 10×80 + 6.25×180 − 5×30 + 5 = 1780
        assert calculate_bmr(80, 180, 30, Gender.MALE) == 1780.0

    def test_female_bmr(self):
        # 10×60 + 6.25×165 − 5×25 − 161 = 1345.25
        assert calculate_bmr(60, 165, 25, Gender.FEMALE) == 1345.25

    def test_male_vs_female_diff_is_166(self):
        male = calculate_bmr(70, 175, 30, Gender.MALE)
        female = calculate_bmr(70, 175, 30, Gender.FEMALE)
        assert male - female == 166.0

    def test_heavier_person_higher_bmr(self):
        assert calculate_bmr(90, 175, 30, Gender.MALE) > calculate_bmr(60, 175, 30, Gender.MALE)

    def test_older_person_lower_bmr(self):
        assert calculate_bmr(75, 175, 20, Gender.MALE) > calculate_bmr(75, 175, 50, Gender.MALE)

    def test_taller_person_higher_bmr(self):
        assert calculate_bmr(75, 190, 30, Gender.MALE) > calculate_bmr(75, 160, 30, Gender.MALE)


# ── calculate_tdee ────────────────────────────────────────────────────────

class TestCalculateTDEE:
    @pytest.mark.parametrize("level,mult", [
        (ActivityLevel.SEDENTARY, 1.2),
        (ActivityLevel.LIGHTLY_ACTIVE, 1.375),
        (ActivityLevel.MODERATELY_ACTIVE, 1.55),
        (ActivityLevel.VERY_ACTIVE, 1.725),
        (ActivityLevel.ATHLETE, 1.9),
    ])
    def test_each_level(self, level, mult):
        assert calculate_tdee(1780.0, level) == round(1780.0 * mult, 2)

    @pytest.mark.parametrize("level", list(ActivityLevel))
    def test_all_multipliers_covered(self, level):
        assert level in ACTIVITY_MULTIPLIER

    def test_higher_activity_higher_tdee(self):
        assert calculate_tdee(1500, ActivityLevel.ATHLETE) > calculate_tdee(1500, ActivityLevel.SEDENTARY)


# ── calculate_targets ─────────────────────────────────────────────────────

class TestCalculateTargets:
    """80 kg, 180 cm, 30 y/o male, moderately active → BMR 1780, TDEE 2759."""

    def _base(self, goal: Goal) -> Targets:
        return calculate_targets(80, 180, 30, Gender.MALE, ActivityLevel.MODERATELY_ACTIVE, goal)

    def test_cut_calories(self):
        t = self._base(Goal.CUT)
        expected_tdee = round(1780.0 * 1.55, 2)  # 2759.0
        assert t.calories == round(expected_tdee * GOAL_CALORIE_MULTIPLIER[Goal.CUT], 2)

    def test_cut_macros(self):
        t = self._base(Goal.CUT)
        assert t.protein_g == round(80 * 2.2, 2)
        assert t.fat_g == round(80 * 0.8, 2)
        # carbs = (calories - protein_g*4 - fat_g*9) / 4
        expected_carbs = round((t.calories - t.protein_g * 4 - t.fat_g * 9) / 4, 2)
        assert t.carbs_g == expected_carbs

    def test_maintain_uses_full_tdee(self):
        t = self._base(Goal.MAINTAIN)
        assert t.calories == 2759.0

    def test_bulk_has_surplus(self):
        t = self._base(Goal.BULK)
        assert t.calories == round(2759.0 * GOAL_CALORIE_MULTIPLIER[Goal.BULK], 2)
        assert t.calories > 2759.0

    def test_recomp_uses_full_tdee(self):
        t = self._base(Goal.RECOMP)
        assert t.calories == 2759.0

    @pytest.mark.parametrize("goal", list(Goal))
    def test_all_goal_multipliers_covered(self, goal):
        assert goal in GOAL_CALORIE_MULTIPLIER

    def test_protein_and_fat_same_across_goals(self):
        cut = self._base(Goal.CUT)
        maintain = self._base(Goal.MAINTAIN)
        assert maintain.protein_g == cut.protein_g
        assert maintain.fat_g == cut.fat_g

    def test_carbs_differ_across_goals(self):
        """Carbs are derived from remaining calories, so they change with goal."""
        cut = self._base(Goal.CUT)
        maintain = self._base(Goal.MAINTAIN)
        assert cut.carbs_g < maintain.carbs_g

    def test_cut_calories_less_than_maintain(self):
        cut = self._base(Goal.CUT)
        maintain = self._base(Goal.MAINTAIN)
        assert cut.calories < maintain.calories

    def test_bulk_calories_more_than_maintain(self):
        bulk = self._base(Goal.BULK)
        maintain = self._base(Goal.MAINTAIN)
        assert bulk.calories > maintain.calories

    def test_female_cut(self):
        t = calculate_targets(60, 165, 25, Gender.FEMALE, ActivityLevel.LIGHTLY_ACTIVE, Goal.CUT)
        bmr = calculate_bmr(60, 165, 25, Gender.FEMALE)
        tdee = calculate_tdee(bmr, ActivityLevel.LIGHTLY_ACTIVE)
        assert t.calories == round(tdee * GOAL_CALORIE_MULTIPLIER[Goal.CUT], 2)
        assert t.protein_g == round(60 * 2.2, 2)

    @pytest.mark.parametrize("goal", list(Goal))
    def test_macro_calories_sum_to_total(self, goal):
        """protein_g×4 + fat_g×9 + carbs_g×4 should equal total calories."""
        t = self._base(goal)
        macro_cals = round(t.protein_g * 4 + t.fat_g * 9 + t.carbs_g * 4, 2)
        assert macro_cals == t.calories


# ── calculate_manual_targets ──────────────────────────────────────────────

class TestCalculateManualTargets:
    def test_calories_only(self):
        """Only calories provided → protein/fat from weight, carbs from remainder."""
        t = calculate_manual_targets(calories=2000, weight_kg=80)
        assert t.calories == 2000
        assert t.protein_g == round(80 * 2.2, 2)
        assert t.fat_g == round(80 * 0.8, 2)
        remaining = 2000 - t.protein_g * 4 - t.fat_g * 9
        assert t.carbs_g == round(remaining / 4, 2)

    def test_all_macros_provided(self):
        """All macros supplied → used as-is, no fallback."""
        t = calculate_manual_targets(
            calories=2500, weight_kg=80, protein_g=200, fat_g=70, carbs_g=250,
        )
        assert t.calories == 2500
        assert t.protein_g == 200
        assert t.fat_g == 70
        assert t.carbs_g == 250

    def test_partial_macros_protein_only(self):
        """Only protein supplied → fat from weight, carbs from remainder."""
        t = calculate_manual_targets(calories=2000, weight_kg=80, protein_g=180)
        assert t.protein_g == 180
        assert t.fat_g == round(80 * 0.8, 2)
        remaining = 2000 - 180 * 4 - t.fat_g * 9
        assert t.carbs_g == round(remaining / 4, 2)

    def test_partial_macros_fat_only(self):
        t = calculate_manual_targets(calories=2000, weight_kg=80, fat_g=60)
        assert t.protein_g == round(80 * 2.2, 2)
        assert t.fat_g == 60

    def test_partial_macros_carbs_only(self):
        """Carbs supplied → used as-is, protein/fat from weight."""
        t = calculate_manual_targets(calories=2000, weight_kg=80, carbs_g=300)
        assert t.protein_g == round(80 * 2.2, 2)
        assert t.fat_g == round(80 * 0.8, 2)
        assert t.carbs_g == 300

    def test_negative_remainder_clamps_to_zero(self):
        """If protein+fat calories exceed total, carbs should be 0."""
        t = calculate_manual_targets(calories=500, weight_kg=80)
        assert t.carbs_g == 0

    def test_returns_targets_dataclass(self):
        t = calculate_manual_targets(calories=2000, weight_kg=70)
        assert isinstance(t, Targets)


# ── Full pipeline ─────────────────────────────────────────────────────────

class TestFullPipeline:
    def test_male_full(self):
        age = calculate_age(date(1996, 2, 26), today=date(2026, 2, 26))
        assert age == 30
        bmr = calculate_bmr(80, 180, age, Gender.MALE)
        assert bmr == 1780.0
        tdee = calculate_tdee(bmr, ActivityLevel.MODERATELY_ACTIVE)
        assert tdee == 2759.0

    def test_female_full(self):
        age = calculate_age(date(2001, 2, 26), today=date(2026, 2, 26))
        assert age == 25
        bmr = calculate_bmr(60, 165, age, Gender.FEMALE)
        assert bmr == 1345.25
        tdee = calculate_tdee(bmr, ActivityLevel.LIGHTLY_ACTIVE)
        assert tdee == 1849.72


# ── Integration: profile create/update populates UserTargets ──────────────

PROFILE_PAYLOAD = {
    "date_of_birth": "1996-02-26",
    "gender": "male",
    "weight": 80,
    "height": 180,
    "goal": "cut",
    "activity_level": "moderately_active",
}


async def _register_and_get_token(client: AsyncClient, email: str = "h@example.com") -> str:
    await client.post("/auth/register", json={"email": email, "password": "pwd123"})
    resp = await client.post("/auth/login", data={"username": email, "password": "pwd123"})
    return resp.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


class TestTargetsPopulation:
    async def test_create_profile_populates_targets(self, async_client: AsyncClient, db_session):
        """Creating a complete profile should insert a UserTargets row."""
        from sqlalchemy import select
        from app.models.user import UserTargets

        token = await _register_and_get_token(async_client)
        resp = await async_client.post("/profile", json=PROFILE_PAYLOAD, headers=_auth(token))
        assert resp.status_code == 201
        profile_id = resp.json()["id"]

        result = await db_session.execute(
            select(UserTargets).where(UserTargets.profile_id == profile_id)
        )
        rows = result.scalars().all()
        assert len(rows) == 1
        targets = rows[0]
        assert targets.based_on_goal == "cut"
        assert targets.based_on_weight == 80
        # cut: calories = TDEE × goal multiplier
        expected_tdee = round(1780.0 * ACTIVITY_MULTIPLIER[ActivityLevel.MODERATELY_ACTIVE], 2)
        assert targets.calories == round(expected_tdee * GOAL_CALORIE_MULTIPLIER[Goal.CUT], 2)
        assert targets.protein_g == round(80 * 2.2, 2)
        assert targets.fat_g == round(80 * 0.8, 2)
        expected_carbs = round((targets.calories - targets.protein_g * 4 - targets.fat_g * 9) / 4, 2)
        assert targets.carbs_g == expected_carbs

    async def test_update_weight_adds_new_targets_row(self, async_client: AsyncClient, db_session):
        from sqlalchemy import select
        from app.models.user import UserTargets

        token = await _register_and_get_token(async_client)
        resp = await async_client.post("/profile", json=PROFILE_PAYLOAD, headers=_auth(token))
        profile_id = resp.json()["id"]

        # change weight → should insert a second row
        await async_client.put("/profile", json={"weight": 90}, headers=_auth(token))

        result = await db_session.execute(
            select(UserTargets)
            .where(UserTargets.profile_id == profile_id)
            .order_by(UserTargets.id.desc())
        )
        rows = result.scalars().all()
        assert len(rows) == 2
        latest = rows[0]
        assert latest.based_on_weight == 90
        assert latest.protein_g == round(90 * 2.2, 2)
        assert latest.fat_g == round(90 * 0.8, 2)

    async def test_update_goal_adds_new_targets_row(self, async_client: AsyncClient, db_session):
        from sqlalchemy import select
        from app.models.user import UserTargets

        token = await _register_and_get_token(async_client)
        resp = await async_client.post("/profile", json=PROFILE_PAYLOAD, headers=_auth(token))
        profile_id = resp.json()["id"]

        # switch from cut → maintain
        await async_client.put("/profile", json={"goal": "maintain"}, headers=_auth(token))

        result = await db_session.execute(
            select(UserTargets)
            .where(UserTargets.profile_id == profile_id)
            .order_by(UserTargets.id.desc())
        )
        rows = result.scalars().all()
        assert len(rows) == 2
        latest = rows[0]
        assert latest.based_on_goal == "maintain"
        expected_tdee = round(1780.0 * ACTIVITY_MULTIPLIER[ActivityLevel.MODERATELY_ACTIVE], 2)
        assert latest.calories == expected_tdee

    async def test_no_targets_when_missing_gender(self, async_client: AsyncClient, db_session):
        from sqlalchemy import select
        from app.models.user import UserTargets

        token = await _register_and_get_token(async_client)
        payload = {k: v for k, v in PROFILE_PAYLOAD.items() if k != "gender"}
        resp = await async_client.post("/profile", json=payload, headers=_auth(token))
        profile_id = resp.json()["id"]

        result = await db_session.execute(
            select(UserTargets).where(UserTargets.profile_id == profile_id)
        )
        assert result.scalars().all() == []

    async def test_no_targets_when_missing_goal(self, async_client: AsyncClient, db_session):
        from sqlalchemy import select
        from app.models.user import UserTargets

        token = await _register_and_get_token(async_client)
        payload = {k: v for k, v in PROFILE_PAYLOAD.items() if k != "goal"}
        resp = await async_client.post("/profile", json=payload, headers=_auth(token))
        profile_id = resp.json()["id"]

        result = await db_session.execute(
            select(UserTargets).where(UserTargets.profile_id == profile_id)
        )
        assert result.scalars().all() == []

    async def test_no_targets_when_missing_activity_level(self, async_client: AsyncClient, db_session):
        from sqlalchemy import select
        from app.models.user import UserTargets

        token = await _register_and_get_token(async_client)
        payload = {k: v for k, v in PROFILE_PAYLOAD.items() if k != "activity_level"}
        resp = await async_client.post("/profile", json=payload, headers=_auth(token))
        profile_id = resp.json()["id"]

        result = await db_session.execute(
            select(UserTargets).where(UserTargets.profile_id == profile_id)
        )
        assert result.scalars().all() == []

    async def test_targets_created_on_update_when_profile_becomes_complete(
        self, async_client: AsyncClient, db_session
    ):
        """Create incomplete profile (no goal), then update with goal → targets appear."""
        from sqlalchemy import select
        from app.models.user import UserTargets

        token = await _register_and_get_token(async_client)
        payload = {k: v for k, v in PROFILE_PAYLOAD.items() if k != "goal"}
        resp = await async_client.post("/profile", json=payload, headers=_auth(token))
        profile_id = resp.json()["id"]

        # no targets yet
        result = await db_session.execute(
            select(UserTargets).where(UserTargets.profile_id == profile_id)
        )
        assert result.scalars().all() == []

        # now add the goal
        await async_client.put("/profile", json={"goal": "cut"}, headers=_auth(token))

        result = await db_session.execute(
            select(UserTargets).where(UserTargets.profile_id == profile_id)
        )
        rows = result.scalars().all()
        assert len(rows) == 1
        assert rows[0].based_on_goal == "cut"


class TestTargetsHistory:
    async def test_history_accumulates(self, async_client: AsyncClient, db_session):
        """Each target-relevant update adds a new row to the history."""
        from sqlalchemy import select
        from app.models.user import UserTargets

        token = await _register_and_get_token(async_client)
        resp = await async_client.post("/profile", json=PROFILE_PAYLOAD, headers=_auth(token))
        profile_id = resp.json()["id"]

        # 1st row from create
        await async_client.put("/profile", json={"weight": 85}, headers=_auth(token))   # 2nd
        await async_client.put("/profile", json={"goal": "bulk"}, headers=_auth(token)) # 3rd

        result = await db_session.execute(
            select(UserTargets)
            .where(UserTargets.profile_id == profile_id)
            .order_by(UserTargets.id)
        )
        rows = result.scalars().all()
        assert len(rows) == 3
        assert rows[0].based_on_weight == 80
        assert rows[0].based_on_goal == "cut"
        assert rows[1].based_on_weight == 85
        assert rows[1].based_on_goal == "cut"
        assert rows[2].based_on_weight == 85
        assert rows[2].based_on_goal == "bulk"

    async def test_non_target_field_update_does_not_add_row(self, async_client: AsyncClient, db_session):
        """Updating height (not in _TARGET_FIELDS) should not insert a new row."""
        from sqlalchemy import select
        from app.models.user import UserTargets

        token = await _register_and_get_token(async_client)
        resp = await async_client.post("/profile", json=PROFILE_PAYLOAD, headers=_auth(token))
        profile_id = resp.json()["id"]

        await async_client.put("/profile", json={"height": 185}, headers=_auth(token))

        result = await db_session.execute(
            select(UserTargets).where(UserTargets.profile_id == profile_id)
        )
        assert len(result.scalars().all()) == 1

    async def test_delete_profile_cascades_history(self, async_client: AsyncClient, db_session):
        """Deleting the profile should delete all target history."""
        from sqlalchemy import select
        from app.models.user import UserTargets

        token = await _register_and_get_token(async_client)
        resp = await async_client.post("/profile", json=PROFILE_PAYLOAD, headers=_auth(token))
        profile_id = resp.json()["id"]

        await async_client.put("/profile", json={"weight": 85}, headers=_auth(token))
        await async_client.delete("/profile", headers=_auth(token))

        result = await db_session.execute(
            select(UserTargets).where(UserTargets.profile_id == profile_id)
        )
        assert result.scalars().all() == []


class TestTargetsEndpoints:
    async def test_get_current_targets(self, async_client: AsyncClient):
        token = await _register_and_get_token(async_client)
        await async_client.post("/profile", json=PROFILE_PAYLOAD, headers=_auth(token))
        await async_client.put("/profile", json={"weight": 90}, headers=_auth(token))

        resp = await async_client.get("/profile/targets", headers=_auth(token))
        assert resp.status_code == 200
        data = resp.json()
        # should return the latest snapshot (weight=90)
        assert data["based_on_weight"] == 90
        assert "id" in data
        assert "profile_id" in data

    async def test_get_current_targets_no_profile(self, async_client: AsyncClient):
        token = await _register_and_get_token(async_client)
        resp = await async_client.get("/profile/targets", headers=_auth(token))
        assert resp.status_code == 404

    async def test_get_current_targets_no_targets(self, async_client: AsyncClient):
        token = await _register_and_get_token(async_client)
        payload = {k: v for k, v in PROFILE_PAYLOAD.items() if k != "goal"}
        await async_client.post("/profile", json=payload, headers=_auth(token))
        resp = await async_client.get("/profile/targets", headers=_auth(token))
        assert resp.status_code == 404

    async def test_get_current_targets_unauthenticated(self, async_client: AsyncClient):
        resp = await async_client.get("/profile/targets")
        assert resp.status_code == 401

    async def test_get_history(self, async_client: AsyncClient):
        token = await _register_and_get_token(async_client)
        await async_client.post("/profile", json=PROFILE_PAYLOAD, headers=_auth(token))
        await async_client.put("/profile", json={"weight": 85}, headers=_auth(token))
        await async_client.put("/profile", json={"goal": "maintain"}, headers=_auth(token))

        resp = await async_client.get("/profile/targets/history", headers=_auth(token))
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 3
        # newest first
        assert data[0]["based_on_goal"] == "maintain"
        assert data[1]["based_on_weight"] == 85
        assert data[2]["based_on_weight"] == 80

    async def test_get_history_empty(self, async_client: AsyncClient):
        token = await _register_and_get_token(async_client)
        payload = {k: v for k, v in PROFILE_PAYLOAD.items() if k != "goal"}
        await async_client.post("/profile", json=payload, headers=_auth(token))
        resp = await async_client.get("/profile/targets/history", headers=_auth(token))
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_get_history_no_profile(self, async_client: AsyncClient):
        token = await _register_and_get_token(async_client)
        resp = await async_client.get("/profile/targets/history", headers=_auth(token))
        assert resp.status_code == 404

    async def test_get_history_unauthenticated(self, async_client: AsyncClient):
        resp = await async_client.get("/profile/targets/history")
        assert resp.status_code == 401


class TestTargetsOverride:
    async def test_override_calories_only(self, async_client: AsyncClient):
        """PUT /profile/targets with just calories → macros derived from weight."""
        token = await _register_and_get_token(async_client)
        await async_client.post("/profile", json=PROFILE_PAYLOAD, headers=_auth(token))

        resp = await async_client.put(
            "/profile/targets",
            json={"calories": 2000},
            headers=_auth(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["calories"] == 2000
        assert data["is_manual"] is True
        # protein/fat default to weight-based
        assert data["protein_g"] == round(80 * 2.2, 2)
        assert data["fat_g"] == round(80 * 0.8, 2)
        # carbs fill the remainder
        remaining = 2000 - data["protein_g"] * 4 - data["fat_g"] * 9
        assert data["carbs_g"] == round(remaining / 4, 2)

    async def test_override_all_macros(self, async_client: AsyncClient):
        """PUT with calories + all macros → all values are user-provided."""
        token = await _register_and_get_token(async_client)
        await async_client.post("/profile", json=PROFILE_PAYLOAD, headers=_auth(token))

        resp = await async_client.put(
            "/profile/targets",
            json={"calories": 2500, "protein_g": 200, "fat_g": 70, "carbs_g": 250},
            headers=_auth(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["calories"] == 2500
        assert data["protein_g"] == 200
        assert data["fat_g"] == 70
        assert data["carbs_g"] == 250
        assert data["is_manual"] is True

    async def test_override_shows_in_current(self, async_client: AsyncClient):
        """After override, GET /profile/targets returns the manual entry."""
        token = await _register_and_get_token(async_client)
        await async_client.post("/profile", json=PROFILE_PAYLOAD, headers=_auth(token))
        await async_client.put(
            "/profile/targets",
            json={"calories": 1800},
            headers=_auth(token),
        )

        resp = await async_client.get("/profile/targets", headers=_auth(token))
        assert resp.status_code == 200
        assert resp.json()["calories"] == 1800
        assert resp.json()["is_manual"] is True

    async def test_override_appears_in_history(self, async_client: AsyncClient):
        """Manual override is part of the history alongside computed entries."""
        token = await _register_and_get_token(async_client)
        await async_client.post("/profile", json=PROFILE_PAYLOAD, headers=_auth(token))  # computed
        await async_client.put(
            "/profile/targets",
            json={"calories": 1800},
            headers=_auth(token),
        )  # manual

        resp = await async_client.get("/profile/targets/history", headers=_auth(token))
        data = resp.json()
        assert len(data) == 2
        # newest first
        assert data[0]["is_manual"] is True
        assert data[0]["calories"] == 1800
        assert data[1]["is_manual"] is False

    async def test_profile_update_after_override_adds_computed(self, async_client: AsyncClient):
        """Updating weight after a manual override inserts a new computed row on top."""
        token = await _register_and_get_token(async_client)
        await async_client.post("/profile", json=PROFILE_PAYLOAD, headers=_auth(token))
        await async_client.put(
            "/profile/targets",
            json={"calories": 1800},
            headers=_auth(token),
        )
        # update weight → triggers auto-compute
        await async_client.put("/profile", json={"weight": 85}, headers=_auth(token))

        resp = await async_client.get("/profile/targets/history", headers=_auth(token))
        data = resp.json()
        assert len(data) == 3
        assert data[0]["is_manual"] is False  # latest = auto-computed
        assert data[0]["based_on_weight"] == 85
        assert data[1]["is_manual"] is True   # manual override
        assert data[2]["is_manual"] is False  # original computed

    async def test_override_no_profile(self, async_client: AsyncClient):
        token = await _register_and_get_token(async_client)
        resp = await async_client.put(
            "/profile/targets",
            json={"calories": 2000},
            headers=_auth(token),
        )
        assert resp.status_code == 404

    async def test_override_unauthenticated(self, async_client: AsyncClient):
        resp = await async_client.put("/profile/targets", json={"calories": 2000})
        assert resp.status_code == 401

    async def test_override_invalid_calories(self, async_client: AsyncClient):
        token = await _register_and_get_token(async_client)
        await async_client.post("/profile", json=PROFILE_PAYLOAD, headers=_auth(token))
        resp = await async_client.put(
            "/profile/targets",
            json={"calories": -100},
            headers=_auth(token),
        )
        assert resp.status_code == 422

    async def test_override_missing_calories(self, async_client: AsyncClient):
        token = await _register_and_get_token(async_client)
        await async_client.post("/profile", json=PROFILE_PAYLOAD, headers=_auth(token))
        resp = await async_client.put(
            "/profile/targets",
            json={"protein_g": 150},
            headers=_auth(token),
        )
        assert resp.status_code == 422

    async def test_computed_targets_have_is_manual_false(self, async_client: AsyncClient):
        """Auto-computed targets from profile creation should have is_manual=False."""
        token = await _register_and_get_token(async_client)
        await async_client.post("/profile", json=PROFILE_PAYLOAD, headers=_auth(token))

        resp = await async_client.get("/profile/targets", headers=_auth(token))
        assert resp.status_code == 200
        assert resp.json()["is_manual"] is False



