"""Тесты аутентификации администраторов."""
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    validate_password_strength,
)
from app.models.admin import AdminRole, AdminUser


async def create_admin(db: AsyncSession, username: str = "testadmin") -> AdminUser:
    user = AdminUser(
        username=username,
        email=f"{username}@test.local",
        full_name="Test Admin",
        hashed_password=hash_password("SecurePassword123"),
        role=AdminRole.system_admin,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient, db_session: AsyncSession):
    await create_admin(db_session)
    response = await client.post("/api/auth/login", json={"username": "testadmin", "password": "SecurePassword123"})
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient, db_session: AsyncSession):
    await create_admin(db_session, username="admin2")
    response = await client.post("/api/auth/login", json={"username": "admin2", "password": "wrongpassword"})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_me_authenticated(client: AsyncClient, db_session: AsyncSession):
    await create_admin(db_session, username="admin3")
    login = await client.post("/api/auth/login", json={"username": "admin3", "password": "SecurePassword123"})
    token = login.json()["access_token"]

    response = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["username"] == "admin3"


@pytest.mark.asyncio
async def test_me_no_token(client: AsyncClient):
    response = await client.get("/api/auth/me")
    assert response.status_code == 401  # HTTPBearer returns 401 in FastAPI 0.110+


@pytest.mark.asyncio
async def test_health(client: AsyncClient):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_login_inactive_user(client: AsyncClient, db_session: AsyncSession):
    user = await create_admin(db_session, username="inactive_admin")
    user.is_active = False
    await db_session.commit()

    response = await client.post(
        "/api/auth/login",
        json={"username": "inactive_admin", "password": "SecurePassword123"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_locked_user(client: AsyncClient, db_session: AsyncSession):
    user = await create_admin(db_session, username="locked_admin")
    user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=5)
    await db_session.commit()

    response = await client.post(
        "/api/auth/login",
        json={"username": "locked_admin", "password": "SecurePassword123"},
    )
    assert response.status_code == 429


@pytest.mark.asyncio
async def test_login_locks_after_failed_attempts(client: AsyncClient, db_session: AsyncSession):
    await create_admin(db_session, username="threshold_admin")
    for _ in range(5):
        response = await client.post(
            "/api/auth/login",
            json={"username": "threshold_admin", "password": "wrongpassword"},
        )
        assert response.status_code == 401

    blocked = await client.post(
        "/api/auth/login",
        json={"username": "threshold_admin", "password": "SecurePassword123"},
    )
    assert blocked.status_code == 429


@pytest.mark.asyncio
async def test_refresh_success(client: AsyncClient, db_session: AsyncSession):
    await create_admin(db_session, username="refresh_ok")
    login = await client.post("/api/auth/login", json={"username": "refresh_ok", "password": "SecurePassword123"})
    assert login.status_code == 200

    refreshed = await client.post("/api/auth/refresh")
    assert refreshed.status_code == 200
    assert "access_token" in refreshed.json()


@pytest.mark.asyncio
async def test_refresh_missing_cookie(client: AsyncClient):
    response = await client.post("/api/auth/refresh")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_refresh_invalid_cookie_token(client: AsyncClient):
    response = await client.post("/api/auth/refresh", cookies={"refresh_token": "invalid.token.value"})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_refresh_wrong_token_type_cookie(client: AsyncClient, db_session: AsyncSession):
    user = await create_admin(db_session, username="refresh_wrong_type")
    access = create_access_token(str(user.id), user.role)

    response = await client.post("/api/auth/refresh", cookies={"refresh_token": access})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_refresh_user_not_found(client: AsyncClient):
    refresh = create_refresh_token("00000000-0000-0000-0000-000000000000")
    response = await client.post("/api/auth/refresh", cookies={"refresh_token": refresh})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_logout(client: AsyncClient):
    response = await client.post("/api/auth/logout")
    assert response.status_code == 200
    assert response.json()["detail"] == "Выход выполнен"


def test_validate_password_strength():
    validate_password_strength("StrongPassword123!")
    with pytest.raises(ValueError):
        validate_password_strength("short")
    with pytest.raises(ValueError):
        validate_password_strength("password123456")
