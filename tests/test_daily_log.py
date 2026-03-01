import uuid
from datetime import date

import pytest
from pydantic import ValidationError

from app.domain.health.schemas import DailyLogCreate, DailyLogRead


class TestDailyLogCreateSchema:
    def test_valid(self):
        data = DailyLogCreate(date=date(2026, 3, 1))
        assert data.date == date(2026, 3, 1)

    def test_from_string(self):
        data = DailyLogCreate(date="2026-03-01")
        assert data.date == date(2026, 3, 1)

    def test_missing_date_rejected(self):
        with pytest.raises(ValidationError):
            DailyLogCreate()

    def test_invalid_date_rejected(self):
        with pytest.raises(ValidationError):
            DailyLogCreate(date="not-a-date")


class TestDailyLogReadSchema:
    def test_from_attributes(self):
        log_id = uuid.uuid4()

        class FakeLog:
            id = log_id
            profile_id = 1
            date = date(2026, 3, 1)
            total_calories = 2200.0
            total_protein_g = 180.0
            total_carbs_g = 250.0
            total_fat_g = 70.0

        data = DailyLogRead.model_validate(FakeLog())
        assert data.id == log_id
        assert data.profile_id == 1
        assert data.date == date(2026, 3, 1)
        assert data.total_calories == 2200.0
        assert data.total_protein_g == 180.0
        assert data.total_carbs_g == 250.0
        assert data.total_fat_g == 70.0

    def test_zero_totals(self):
        log_id = uuid.uuid4()

        class FakeLog:
            id = log_id
            profile_id = 1
            date = date(2026, 3, 1)
            total_calories = 0
            total_protein_g = 0
            total_carbs_g = 0
            total_fat_g = 0

        data = DailyLogRead.model_validate(FakeLog())
        assert data.total_calories == 0
        assert data.total_protein_g == 0
        assert data.total_carbs_g == 0
        assert data.total_fat_g == 0

