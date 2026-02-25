from httpx import AsyncClient


PROFILE_PAYLOAD = {
    "date_of_birth": "1990-05-15",
    "weight": 75.5,
    "height": 180.0,
    "goal": "lose weight",
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
        assert data["weight"] == 75.5
        assert data["height"] == 180.0
        assert data["goal"] == "lose weight"
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
            "weight": 80.0,
            "height": 185.0,
            "goal": "gain muscle",
        }
        resp = await async_client.put("/profile", json=update, headers=_auth(token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["weight"] == 80.0
        assert data["height"] == 185.0
        assert data["goal"] == "gain muscle"
        assert data["date_of_birth"] == "1992-01-01"

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
        assert data["goal"] == "lose weight"

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
