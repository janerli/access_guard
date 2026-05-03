"""Тесты аутентификации администраторов."""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
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
