from httpx import AsyncClient


PROFILE_PAYLOAD = {
    "date_of_birth": "1990-05-15",
    "gender": "male",
    "weight": 75.5,
    "height": 180.0,
    "goal": "cut",
    "activity_level": "moderately_active",
}


async def _register_and_get_token(client: AsyncClient, email: str = "p@example.com") -> str:
    await client.post("/auth/register", json={"email": email, "password": "pwd123"})
    resp = await client.post("/auth/login", data={"username": email, "password": "pwd123"})
    return resp.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


class TestCreateProfile:
    async def test_create_success(self, async_client: AsyncClient):
        token = await _register_and_get_token(async_client)
        resp = await async_client.post("/profile", json=PROFILE_PAYLOAD, headers=_auth(token))

        assert resp.status_code == 201
        data = resp.json()
        assert data["date_of_birth"] == "1990-05-15"
        assert data["gender"] == "male"
        assert data["weight"] == 75.5
        assert data["height"] == 180.0
        assert data["goal"] == "cut"
        assert data["activity_level"] == "moderately_active"
        assert "id" in data
        assert "user_id" in data

    async def test_create_without_goal(self, async_client: AsyncClient):
        token = await _register_and_get_token(async_client)
        payload = {k: v for k, v in PROFILE_PAYLOAD.items() if k != "goal"}
        resp = await async_client.post("/profile", json=payload, headers=_auth(token))
        assert resp.status_code == 201
        assert resp.json()["goal"] is None

    async def test_create_duplicate(self, async_client: AsyncClient):
        token = await _register_and_get_token(async_client)
        await async_client.post("/profile", json=PROFILE_PAYLOAD, headers=_auth(token))
        resp = await async_client.post("/profile", json=PROFILE_PAYLOAD, headers=_auth(token))
        assert resp.status_code == 409

    async def test_create_unauthenticated(self, async_client: AsyncClient):
        resp = await async_client.post("/profile", json=PROFILE_PAYLOAD)
        assert resp.status_code == 401

    async def test_create_invalid_payload(self, async_client: AsyncClient):
        token = await _register_and_get_token(async_client)
        resp = await async_client.post(
            "/profile",
            json={"weight": "not-a-number"},
            headers=_auth(token),
        )
        assert resp.status_code == 422



class TestGetProfile:
    async def test_get_success(self, async_client: AsyncClient):
        token = await _register_and_get_token(async_client)
        await async_client.post("/profile", json=PROFILE_PAYLOAD, headers=_auth(token))

        resp = await async_client.get("/profile", headers=_auth(token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["weight"] == 75.5
        assert data["height"] == 180.0

    async def test_get_not_found(self, async_client: AsyncClient):
        token = await _register_and_get_token(async_client)
        resp = await async_client.get("/profile", headers=_auth(token))
        assert resp.status_code == 404

    async def test_get_unauthenticated(self, async_client: AsyncClient):
        resp = await async_client.get("/profile")
        assert resp.status_code == 401


class TestUpdateProfile:
    async def test_update_full(self, async_client: AsyncClient):
        token = await _register_and_get_token(async_client)
        await async_client.post("/profile", json=PROFILE_PAYLOAD, headers=_auth(token))

        update = {
            "date_of_birth": "1992-01-01",
            "gender": "female",
            "weight": 80.0,
            "height": 185.0,
            "goal": "bulk",
            "activity_level": "very_active",
        }
        resp = await async_client.put("/profile", json=update, headers=_auth(token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["weight"] == 80.0
        assert data["height"] == 185.0
        assert data["goal"] == "bulk"
        assert data["date_of_birth"] == "1992-01-01"
        assert data["gender"] == "female"
        assert data["activity_level"] == "very_active"

    async def test_update_partial(self, async_client: AsyncClient):
        token = await _register_and_get_token(async_client)
        await async_client.post("/profile", json=PROFILE_PAYLOAD, headers=_auth(token))

        resp = await async_client.put(
            "/profile",
            json={"weight": 70.0},
            headers=_auth(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["weight"] == 70.0
        # other fields unchanged
        assert data["height"] == 180.0
        assert data["goal"] == "cut"

    async def test_update_not_found(self, async_client: AsyncClient):
        token = await _register_and_get_token(async_client)
        resp = await async_client.put(
            "/profile",
            json={"weight": 70.0},
            headers=_auth(token),
        )
        assert resp.status_code == 404

    async def test_update_unauthenticated(self, async_client: AsyncClient):
        resp = await async_client.put("/profile", json={"weight": 70.0})
        assert resp.status_code == 401


class TestDeleteProfile:
    async def test_delete_success(self, async_client: AsyncClient):
        token = await _register_and_get_token(async_client)
        await async_client.post("/profile", json=PROFILE_PAYLOAD, headers=_auth(token))

        resp = await async_client.delete("/profile", headers=_auth(token))
        assert resp.status_code == 204

        # confirm it's gone
        resp = await async_client.get("/profile", headers=_auth(token))
        assert resp.status_code == 404

    async def test_delete_not_found(self, async_client: AsyncClient):
        token = await _register_and_get_token(async_client)
        resp = await async_client.delete("/profile", headers=_auth(token))
        assert resp.status_code == 404

    async def test_delete_unauthenticated(self, async_client: AsyncClient):
        resp = await async_client.delete("/profile")
        assert resp.status_code == 401


class TestProfileIsolation:
    async def test_users_cannot_see_each_others_profiles(self, async_client: AsyncClient):
        token_a = await _register_and_get_token(async_client, "a@example.com")
        token_b = await _register_and_get_token(async_client, "b@example.com")

        await async_client.post("/profile", json=PROFILE_PAYLOAD, headers=_auth(token_a))

        # user B has no profile
        resp = await async_client.get("/profile", headers=_auth(token_b))
        assert resp.status_code == 404


class TestActivityLevel:
    async def test_create_with_each_level(self, async_client: AsyncClient):
        for i, level in enumerate(
            ["sedentary", "lightly_active", "moderately_active", "very_active", "athlete"]
        ):
            token = await _register_and_get_token(async_client, f"al{i}@example.com")
            payload = {**PROFILE_PAYLOAD, "activity_level": level}
            resp = await async_client.post("/profile", json=payload, headers=_auth(token))
            assert resp.status_code == 201
            assert resp.json()["activity_level"] == level

    async def test_create_with_invalid_activity_level(self, async_client: AsyncClient):
        token = await _register_and_get_token(async_client)
        payload = {**PROFILE_PAYLOAD, "activity_level": "couch_potato"}
        resp = await async_client.post("/profile", json=payload, headers=_auth(token))
        assert resp.status_code == 422

    async def test_create_without_activity_level(self, async_client: AsyncClient):
        token = await _register_and_get_token(async_client)
        payload = {k: v for k, v in PROFILE_PAYLOAD.items() if k != "activity_level"}
        resp = await async_client.post("/profile", json=payload, headers=_auth(token))
        assert resp.status_code == 201
        assert resp.json()["activity_level"] is None

    async def test_update_activity_level(self, async_client: AsyncClient):
        token = await _register_and_get_token(async_client)
        await async_client.post("/profile", json=PROFILE_PAYLOAD, headers=_auth(token))

        resp = await async_client.put(
            "/profile",
            json={"activity_level": "athlete"},
            headers=_auth(token),
        )
        assert resp.status_code == 200
        assert resp.json()["activity_level"] == "athlete"
        # other fields unchanged
        assert resp.json()["weight"] == 75.5


class TestGoal:
    async def test_create_with_each_goal(self, async_client: AsyncClient):
        for i, goal in enumerate(["cut", "maintain", "bulk", "recomp"]):
            token = await _register_and_get_token(async_client, f"goal{i}@example.com")
            payload = {**PROFILE_PAYLOAD, "goal": goal}
            resp = await async_client.post("/profile", json=payload, headers=_auth(token))
            assert resp.status_code == 201
            assert resp.json()["goal"] == goal

    async def test_create_with_invalid_goal(self, async_client: AsyncClient):
        token = await _register_and_get_token(async_client)
        payload = {**PROFILE_PAYLOAD, "goal": "lose weight"}
        resp = await async_client.post("/profile", json=payload, headers=_auth(token))
        assert resp.status_code == 422

    async def test_create_without_goal(self, async_client: AsyncClient):
        token = await _register_and_get_token(async_client)
        payload = {k: v for k, v in PROFILE_PAYLOAD.items() if k != "goal"}
        resp = await async_client.post("/profile", json=payload, headers=_auth(token))
        assert resp.status_code == 201
        assert resp.json()["goal"] is None

    async def test_update_goal(self, async_client: AsyncClient):
        token = await _register_and_get_token(async_client)
        await async_client.post("/profile", json=PROFILE_PAYLOAD, headers=_auth(token))

        resp = await async_client.put(
            "/profile",
            json={"goal": "recomp"},
            headers=_auth(token),
        )
        assert resp.status_code == 200
        assert resp.json()["goal"] == "recomp"
        # other fields unchanged
        assert resp.json()["weight"] == 75.5


class TestGender:
    async def test_create_with_each_gender(self, async_client: AsyncClient):
        for i, gender in enumerate(["male", "female"]):
            token = await _register_and_get_token(async_client, f"gender{i}@example.com")
            payload = {**PROFILE_PAYLOAD, "gender": gender}
            resp = await async_client.post("/profile", json=payload, headers=_auth(token))
            assert resp.status_code == 201
            assert resp.json()["gender"] == gender

    async def test_create_with_invalid_gender(self, async_client: AsyncClient):
        token = await _register_and_get_token(async_client)
        payload = {**PROFILE_PAYLOAD, "gender": "other"}
        resp = await async_client.post("/profile", json=payload, headers=_auth(token))
        assert resp.status_code == 422

    async def test_create_without_gender(self, async_client: AsyncClient):
        token = await _register_and_get_token(async_client)
        payload = {k: v for k, v in PROFILE_PAYLOAD.items() if k != "gender"}
        resp = await async_client.post("/profile", json=payload, headers=_auth(token))
        assert resp.status_code == 201
        assert resp.json()["gender"] is None

    async def test_update_gender(self, async_client: AsyncClient):
        token = await _register_and_get_token(async_client)
        await async_client.post("/profile", json=PROFILE_PAYLOAD, headers=_auth(token))

        resp = await async_client.put(
            "/profile",
            json={"gender": "female"},
            headers=_auth(token),
        )
        assert resp.status_code == 200
        assert resp.json()["gender"] == "female"
        # other fields unchanged
        assert resp.json()["weight"] == 75.5


