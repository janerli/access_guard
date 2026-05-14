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


@pytest.mark.asyncio
async def test_login_sets_refresh_cookie(client: AsyncClient, db_session: AsyncSession):
    await create_admin(db_session, username="admin_cookie")
    response = await client.post("/api/auth/login", json={"username": "admin_cookie", "password": "SecurePassword123"})
    assert response.status_code == 200
    assert "refresh_token" in response.cookies


@pytest.mark.asyncio
async def test_refresh_success(client: AsyncClient, db_session: AsyncSession):
    await create_admin(db_session, username="admin_refresh")
    login = await client.post("/api/auth/login", json={"username": "admin_refresh", "password": "SecurePassword123"})
    assert login.status_code == 200

    refresh_cookie = login.cookies.get("refresh_token")
    assert refresh_cookie is not None

    response = await client.post("/api/auth/refresh", cookies={"refresh_token": refresh_cookie})
    assert response.status_code == 200
    assert "access_token" in response.json()


@pytest.mark.asyncio
async def test_refresh_no_cookie(client: AsyncClient):
    response = await client.post("/api/auth/refresh")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_refresh_invalid_token(client: AsyncClient):
    response = await client.post("/api/auth/refresh", cookies={"refresh_token": "not.a.valid.token"})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_refresh_wrong_token_type(client: AsyncClient, db_session: AsyncSession):
    from app.core.security import create_access_token
    from app.models.admin import AdminRole
    # Use an access token (type=access) where a refresh token is expected
    access_token = create_access_token("fake-id", AdminRole.system_admin)
    response = await client.post("/api/auth/refresh", cookies={"refresh_token": access_token})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_logout(client: AsyncClient):
    response = await client.post("/api/auth/logout")
    assert response.status_code == 200
    assert response.json()["detail"] == "Выход выполнен"


@pytest.mark.asyncio
async def test_login_account_lockout(client: AsyncClient, db_session: AsyncSession):
    await create_admin(db_session, username="admin_lock")
    for _ in range(5):
        await client.post("/api/auth/login", json={"username": "admin_lock", "password": "wrongpass"})
    response = await client.post("/api/auth/login", json={"username": "admin_lock", "password": "wrongpass"})
    assert response.status_code == 429
