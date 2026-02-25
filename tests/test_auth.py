from httpx import AsyncClient



class TestRegister:
    async def test_register_success(self, async_client: AsyncClient):
        resp = await async_client.post(
            "/auth/register",
            json={"email": "new@example.com", "password": "strongpwd"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["email"] == "new@example.com"
        assert data["is_active"] is True
        assert "id" in data

    async def test_register_duplicate_email(self, async_client: AsyncClient):
        payload = {"email": "dup@example.com", "password": "pwd123"}
        await async_client.post("/auth/register", json=payload)
        resp = await async_client.post("/auth/register", json=payload)
        assert resp.status_code == 409

    async def test_register_invalid_email(self, async_client: AsyncClient):
        resp = await async_client.post(
            "/auth/register",
            json={"email": "not-an-email", "password": "pwd123"},
        )
        assert resp.status_code == 422


class TestLogin:
    async def test_login_success(self, async_client: AsyncClient):
        await async_client.post(
            "/auth/register",
            json={"email": "login@example.com", "password": "pwd123"},
        )
        resp = await async_client.post(
            "/auth/login",
            data={"username": "login@example.com", "password": "pwd123"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    async def test_login_wrong_password(self, async_client: AsyncClient):
        await async_client.post(
            "/auth/register",
            json={"email": "wrong@example.com", "password": "correct"},
        )
        resp = await async_client.post(
            "/auth/login",
            data={"username": "wrong@example.com", "password": "incorrect"},
        )
        assert resp.status_code == 401

    async def test_login_nonexistent_user(self, async_client: AsyncClient):
        resp = await async_client.post(
            "/auth/login",
            data={"username": "ghost@example.com", "password": "pwd"},
        )
        assert resp.status_code == 401


class TestRefresh:
    async def test_refresh_success(self, async_client: AsyncClient):
        await async_client.post(
            "/auth/register",
            json={"email": "refresh@example.com", "password": "pwd123"},
        )
        login_resp = await async_client.post(
            "/auth/login",
            data={"username": "refresh@example.com", "password": "pwd123"},
        )
        refresh_token = login_resp.json()["refresh_token"]

        resp = await async_client.post(
            "/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data

    async def test_refresh_invalid_token(self, async_client: AsyncClient):
        resp = await async_client.post(
            "/auth/refresh",
            json={"refresh_token": "bad.token.value"},
        )
        assert resp.status_code == 401


class TestMe:
    async def test_me_authenticated(self, async_client: AsyncClient):
        await async_client.post(
            "/auth/register",
            json={"email": "me@example.com", "password": "pwd123"},
        )
        login_resp = await async_client.post(
            "/auth/login",
            data={"username": "me@example.com", "password": "pwd123"},
        )
        token = login_resp.json()["access_token"]

        resp = await async_client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["email"] == "me@example.com"

    async def test_me_unauthenticated(self, async_client: AsyncClient):
        resp = await async_client.get("/auth/me")
        assert resp.status_code == 401

    async def test_me_invalid_token(self, async_client: AsyncClient):
        resp = await async_client.get(
            "/auth/me",
            headers={"Authorization": "Bearer bad.token"},
        )
        assert resp.status_code == 401

