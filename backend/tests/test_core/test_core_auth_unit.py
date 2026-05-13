from uuid import uuid4

import pytest
from fastapi import HTTPException, Response
from unittest.mock import AsyncMock

from app.core import auth
from app.core.security import hash_password, create_refresh_token
from app.models.admin import AdminRole, AdminUser
from app.schemas.auth import LoginRequest


class _ScalarResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


def _admin_user(username: str = "unit_admin") -> AdminUser:
    return AdminUser(
        id=uuid4(),
        username=username,
        email=f"{username}@test.local",
        full_name="Unit Admin",
        hashed_password=hash_password("SecurePassword123"),
        role=AdminRole.system_admin,
        is_active=True,
    )


@pytest.mark.asyncio
async def test_login_unit_success_sets_cookie():
    user = _admin_user("login_unit")
    db = AsyncMock()
    db.execute.return_value = _ScalarResult(user)
    response = Response()

    result = await auth.login(
        LoginRequest(username="login_unit", password="SecurePassword123"),
        response,
        db,
    )

    assert result.access_token
    assert "refresh_token=" in response.headers.get("set-cookie", "")
    db.commit.assert_awaited()


@pytest.mark.asyncio
async def test_refresh_unit_success_sets_cookie():
    user = _admin_user("refresh_unit")
    db = AsyncMock()
    db.execute.return_value = _ScalarResult(user)
    response = Response()
    refresh = create_refresh_token(str(user.id))

    result = await auth.refresh_token(response, db, refresh_token=refresh)

    assert result.access_token
    assert "refresh_token=" in response.headers.get("set-cookie", "")
    db.execute.assert_awaited()


@pytest.mark.asyncio
async def test_login_unit_user_not_found():
    db = AsyncMock()
    db.execute.return_value = _ScalarResult(None)

    with pytest.raises(HTTPException) as exc:
        await auth.login(
            LoginRequest(username="missing", password="SecurePassword123"),
            Response(),
            db,
        )

    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_login_unit_locked_user():
    user = _admin_user("locked_unit")
    from datetime import datetime, timedelta, timezone
    user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=1)

    db = AsyncMock()
    db.execute.return_value = _ScalarResult(user)

    with pytest.raises(HTTPException) as exc:
        await auth.login(
            LoginRequest(username="locked_unit", password="SecurePassword123"),
            Response(),
            db,
        )

    assert exc.value.status_code == 429


@pytest.mark.asyncio
async def test_login_unit_wrong_password_locks_account():
    user = _admin_user("wrong_pass_unit")
    user.failed_login_count = 4

    db = AsyncMock()
    db.execute.return_value = _ScalarResult(user)

    with pytest.raises(HTTPException) as exc:
        await auth.login(
            LoginRequest(username="wrong_pass_unit", password="wrong-password"),
            Response(),
            db,
        )

    assert exc.value.status_code == 401
    assert user.failed_login_count == 0
    assert user.locked_until is not None
    db.commit.assert_awaited()


@pytest.mark.asyncio
async def test_refresh_unit_user_not_found():
    db = AsyncMock()
    db.execute.return_value = _ScalarResult(None)
    response = Response()
    refresh = create_refresh_token(str(uuid4()))

    with pytest.raises(HTTPException) as exc:
        await auth.refresh_token(response, db, refresh_token=refresh)

    assert exc.value.status_code == 401
