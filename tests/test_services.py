import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

from jose import jwt

from app.core.auth import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    create_tokens,
    decode_refresh_token,
    _decode_token,
)
from app.core.config import settings
from app.services.connection_manager import ConnectionManager


class TestPasswordHashing:
    def test_hash_and_verify(self):
        hashed = hash_password("mysecret")
        assert hashed != "mysecret"
        assert verify_password("mysecret", hashed)

    def test_wrong_password(self):
        hashed = hash_password("correct")
        assert not verify_password("wrong", hashed)

    def test_different_hashes(self):
        h1 = hash_password("same")
        h2 = hash_password("same")
        # hashes include random salt so they should differ
        assert h1 != h2


class TestTokens:
    def test_create_access_token_valid(self):
        token = create_access_token({"sub": "42"})
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
        assert payload["sub"] == "42"
        assert payload["type"] == "access"

    def test_create_refresh_token_valid(self):
        token = create_refresh_token({"sub": "7"})
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
        assert payload["sub"] == "7"
        assert payload["type"] == "refresh"

    def test_create_tokens_returns_both(self):
        result = create_tokens(99)
        assert "access_token" in result
        assert "refresh_token" in result
        assert result["token_type"] == "bearer"

    def test_decode_refresh_token_success(self):
        tokens = create_tokens(5)
        user_id = decode_refresh_token(tokens["refresh_token"])
        assert user_id == 5

    def test_decode_refresh_token_rejects_access_token(self):
        tokens = create_tokens(5)
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            decode_refresh_token(tokens["access_token"])
        assert exc_info.value.status_code == 401

    def test_decode_token_expired(self):
        payload = {
            "sub": "1",
            "type": "access",
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),
        }
        token = jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)
        from fastapi import HTTPException

        with pytest.raises(HTTPException):
            _decode_token(token, "access")

    def test_decode_token_invalid_string(self):
        from fastapi import HTTPException

        with pytest.raises(HTTPException):
            _decode_token("totally.invalid.jwt", "access")


class TestConnectionManager:
    async def test_connect_and_disconnect(self):
        mgr = ConnectionManager()
        ws = AsyncMock()
        await mgr.connect(ws)
        ws.accept.assert_awaited_once()
        assert ws in mgr.active

        await mgr.disconnect(ws)
        assert ws not in mgr.active

    async def test_disconnect_unknown_ws(self):
        mgr = ConnectionManager()
        ws = AsyncMock()
        # should not raise
        await mgr.disconnect(ws)

    async def test_broadcast(self):
        mgr = ConnectionManager()
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        await mgr.connect(ws1)
        await mgr.connect(ws2)

        await mgr.broadcast("hello")
        ws1.send_text.assert_awaited_once_with("Response: hello")
        ws2.send_text.assert_awaited_once_with("Response: hello")

    async def test_broadcast_empty(self):
        mgr = ConnectionManager()
        # no error on empty set
        await mgr.broadcast("nobody listening")


