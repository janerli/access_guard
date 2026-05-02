"""Тесты Identity модуля — CRUD пользователей, жизненный цикл."""
from unittest.mock import AsyncMock, patch

import pytest

from app.models.identity import Department, Position, UserExt, UserStatus


@pytest.fixture
async def seed_position(db_session):
    from uuid import uuid4
    pos = Position(id=uuid4(), code="TEST-POS", name="Тестовая должность", level=1)
    db_session.add(pos)
    await db_session.flush()
    return pos


@pytest.fixture
async def seed_department(db_session):
    from uuid import uuid4
    dept = Department(id=uuid4(), code="TEST-DEPT", name="Тестовый отдел")
    db_session.add(dept)
    await db_session.flush()
    return dept


@pytest.mark.asyncio
async def test_create_user_via_api(client, seed_position, seed_department):
    with patch("app.kafka.producer.get_producer", new_callable=AsyncMock) as mock_prod:
        mock_prod.return_value.send = AsyncMock()
        resp = await client.post(
            "/api/identity/users",
            json={
                "employee_id": "E-0001",
                "username": "test.user",
                "email": "test.user@accessguard.local",
                "full_name": "Тестов Тест Тестович",
                "position_code": "TEST-POS",
                "department_code": "TEST-DEPT",
            },
            headers={"Authorization": "Bearer " + await _get_token(client)},
        )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["employee_id"] == "E-0001"
    assert data["status"] == "active"
    assert data["username"] == "test.user"


@pytest.mark.asyncio
async def test_list_users(client):
    token = await _get_token(client)
    resp = await client.get("/api/identity/users", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data


@pytest.mark.asyncio
async def test_create_and_block_user(client, seed_position, seed_department):
    token = await _get_token(client)
    headers = {"Authorization": f"Bearer {token}"}

    with patch("app.kafka.producer.get_producer", new_callable=AsyncMock) as mp:
        mp.return_value.send = AsyncMock()
        resp = await client.post(
            "/api/identity/users",
            json={
                "employee_id": "E-0002",
                "username": "block.me",
                "email": "block.me@accessguard.local",
                "full_name": "Блокируемый Пользователь",
            },
            headers=headers,
        )
    assert resp.status_code == 201
    user_id = resp.json()["id"]

    with patch("app.kafka.producer.get_producer", new_callable=AsyncMock) as mp:
        mp.return_value.send = AsyncMock()
        resp = await client.post(f"/api/identity/users/{user_id}/block", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "blocked"


@pytest.mark.asyncio
async def test_user_lifecycle_events(client):
    token = await _get_token(client)
    resp = await client.get("/api/identity/events", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert "items" in resp.json()


@pytest.mark.asyncio
async def test_positions_list(client):
    token = await _get_token(client)
    resp = await client.get("/api/identity/positions", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_departments_list(client):
    token = await _get_token(client)
    resp = await client.get("/api/identity/departments", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


async def _get_token(client) -> str:
    """Создаёт admin-пользователя и возвращает JWT токен."""
    from app.core.security import hash_password
    from app.database import AsyncSessionLocal
    from app.models.admin import AdminRole, AdminUser
    import uuid

    async with AsyncSessionLocal() as db:
        user = (await db.execute(
            __import__("sqlalchemy").select(AdminUser).where(AdminUser.username == "_test_admin")
        )).scalar_one_or_none()
        if not user:
            user = AdminUser(
                id=uuid.uuid4(),
                username="_test_admin",
                email="_test@test.com",
                full_name="Test Admin",
                hashed_password=hash_password("Password123!"),
                role=AdminRole.system_admin,
            )
            db.add(user)
            await db.commit()

    resp = await client.post("/api/auth/login", json={"username": "_test_admin", "password": "Password123!"})
    return resp.json()["access_token"]
