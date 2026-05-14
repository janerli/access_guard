"""Тесты Identity модуля — CRUD пользователей, жизненный цикл."""
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.identity import Department, Position


@pytest.fixture
async def seed_refs(db_session: AsyncSession):
    """Вставляет эталонную должность и отдел в тестовую сессию."""
    pos = Position(id=uuid4(), code="TEST-POS-1", name="Тестовая должность", level=1)
    dept = Department(id=uuid4(), code="TEST-DEPT-1", name="Тестовый отдел")
    db_session.add(pos)
    db_session.add(dept)
    await db_session.flush()
    return {"position_code": "TEST-POS-1", "department_code": "TEST-DEPT-1"}


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_list_users_empty(client: AsyncClient, admin_token: str):
    resp = await client.get("/api/identity/users", headers=_headers(admin_token))
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data


@pytest.mark.asyncio
async def test_create_user(client: AsyncClient, admin_token: str, seed_refs):
    with patch("app.kafka.producer.get_producer", new_callable=AsyncMock) as mp:
        mp.return_value.send = AsyncMock()
        resp = await client.post(
            "/api/identity/users",
            json={
                "employee_id": f"E-TEST-{uuid4().hex[:6]}",
                "username": f"u_{uuid4().hex[:8]}",
                "email": f"u_{uuid4().hex[:8]}@test.local",
                "full_name": "Иванов Иван Иванович",
                "position_code": seed_refs["position_code"],
                "department_code": seed_refs["department_code"],
            },
            headers=_headers(admin_token),
        )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["status"] == "active"
    assert data["full_name"] == "Иванов Иван Иванович"
    return data["id"]


@pytest.mark.asyncio
async def test_create_user_duplicate_employee_id(client: AsyncClient, admin_token: str):
    emp_id = f"E-DUP-{uuid4().hex[:6]}"
    payload = lambda: {
        "employee_id": emp_id,
        "username": f"u_{uuid4().hex[:8]}",
        "email": f"u_{uuid4().hex[:8]}@test.local",
        "full_name": "Дубликат",
    }
    with patch("app.kafka.producer.get_producer", new_callable=AsyncMock) as mp:
        mp.return_value.send = AsyncMock()
        r1 = await client.post("/api/identity/users", json=payload(), headers=_headers(admin_token))
    assert r1.status_code == 201

    with patch("app.kafka.producer.get_producer", new_callable=AsyncMock) as mp:
        mp.return_value.send = AsyncMock()
        r2 = await client.post("/api/identity/users", json=payload(), headers=_headers(admin_token))
    assert r2.status_code == 400


@pytest.mark.asyncio
async def test_get_user(client: AsyncClient, admin_token: str):
    # Сначала создаём
    with patch("app.kafka.producer.get_producer", new_callable=AsyncMock) as mp:
        mp.return_value.send = AsyncMock()
        create_resp = await client.post(
            "/api/identity/users",
            json={
                "employee_id": f"E-GET-{uuid4().hex[:6]}",
                "username": f"u_get_{uuid4().hex[:8]}",
                "email": f"get_{uuid4().hex[:8]}@test.local",
                "full_name": "Петров Пётр Петрович",
            },
            headers=_headers(admin_token),
        )
    assert create_resp.status_code == 201
    user_id = create_resp.json()["id"]

    resp = await client.get(f"/api/identity/users/{user_id}", headers=_headers(admin_token))
    assert resp.status_code == 200
    assert resp.json()["id"] == user_id


@pytest.mark.asyncio
async def test_block_user(client: AsyncClient, admin_token: str):
    with patch("app.kafka.producer.get_producer", new_callable=AsyncMock) as mp:
        mp.return_value.send = AsyncMock()
        create_resp = await client.post(
            "/api/identity/users",
            json={
                "employee_id": f"E-BLOCK-{uuid4().hex[:6]}",
                "username": f"u_blk_{uuid4().hex[:8]}",
                "email": f"blk_{uuid4().hex[:8]}@test.local",
                "full_name": "Блокируемый Пользователь",
            },
            headers=_headers(admin_token),
        )
    user_id = create_resp.json()["id"]

    with patch("app.kafka.producer.get_producer", new_callable=AsyncMock) as mp:
        mp.return_value.send = AsyncMock()
        resp = await client.post(f"/api/identity/users/{user_id}/block", headers=_headers(admin_token))
    assert resp.status_code == 200
    assert resp.json()["status"] == "blocked"


@pytest.mark.asyncio
async def test_suspend_restore_user(client: AsyncClient, admin_token: str):
    with patch("app.kafka.producer.get_producer", new_callable=AsyncMock) as mp:
        mp.return_value.send = AsyncMock()
        create_resp = await client.post(
            "/api/identity/users",
            json={
                "employee_id": f"E-SUSP-{uuid4().hex[:6]}",
                "username": f"u_susp_{uuid4().hex[:8]}",
                "email": f"susp_{uuid4().hex[:8]}@test.local",
                "full_name": "Отпускник",
            },
            headers=_headers(admin_token),
        )
    user_id = create_resp.json()["id"]

    with patch("app.kafka.producer.get_producer", new_callable=AsyncMock) as mp:
        mp.return_value.send = AsyncMock()
        r = await client.post(f"/api/identity/users/{user_id}/suspend", headers=_headers(admin_token))
    assert r.json()["status"] == "suspended"

    with patch("app.kafka.producer.get_producer", new_callable=AsyncMock) as mp:
        mp.return_value.send = AsyncMock()
        r = await client.post(f"/api/identity/users/{user_id}/restore", headers=_headers(admin_token))
    assert r.json()["status"] == "active"


@pytest.mark.asyncio
async def test_lifecycle_events_list(client: AsyncClient, admin_token: str):
    resp = await client.get("/api/identity/events", headers=_headers(admin_token))
    assert resp.status_code == 200
    assert "items" in resp.json()


@pytest.mark.asyncio
async def test_positions_list(client: AsyncClient, admin_token: str, seed_refs):
    resp = await client.get("/api/identity/positions", headers=_headers(admin_token))
    assert resp.status_code == 200
    items = resp.json()
    assert isinstance(items, list)
    codes = [p["code"] for p in items]
    assert "TEST-POS-1" in codes


@pytest.mark.asyncio
async def test_departments_list(client: AsyncClient, admin_token: str, seed_refs):
    resp = await client.get("/api/identity/departments", headers=_headers(admin_token))
    assert resp.status_code == 200
    codes = [d["code"] for d in resp.json()]
    assert "TEST-DEPT-1" in codes


async def _create_user_via_api(client: AsyncClient, admin_token: str) -> dict:
    with patch("app.kafka.producer.get_producer", new_callable=AsyncMock) as mp:
        mp.return_value.send = AsyncMock()
        resp = await client.post(
            "/api/identity/users",
            json={
                "employee_id": f"E-{uuid4().hex[:8]}",
                "username": f"u_{uuid4().hex[:8]}",
                "email": f"u_{uuid4().hex[:8]}@test.local",
                "full_name": "Тестовый Пользователь",
            },
            headers=_headers(admin_token),
        )
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest.mark.asyncio
async def test_update_user(client: AsyncClient, admin_token: str):
    user = await _create_user_via_api(client, admin_token)
    user_id = user["id"]

    with patch("app.kafka.producer.get_producer", new_callable=AsyncMock) as mp:
        mp.return_value.send = AsyncMock()
        resp = await client.patch(
            f"/api/identity/users/{user_id}",
            json={"full_name": "Обновлённое Имя", "email": f"updated_{uuid4().hex[:6]}@test.local"},
            headers=_headers(admin_token),
        )
    assert resp.status_code == 200
    assert resp.json()["full_name"] == "Обновлённое Имя"


@pytest.mark.asyncio
async def test_delete_user(client: AsyncClient, admin_token: str):
    user = await _create_user_via_api(client, admin_token)
    user_id = user["id"]

    with patch("app.kafka.producer.get_producer", new_callable=AsyncMock) as mp:
        mp.return_value.send = AsyncMock()
        resp = await client.delete(f"/api/identity/users/{user_id}", headers=_headers(admin_token))
    assert resp.status_code == 204

    get_resp = await client.get(f"/api/identity/users/{user_id}", headers=_headers(admin_token))
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_reset_password(client: AsyncClient, admin_token: str):
    user = await _create_user_via_api(client, admin_token)
    user_id = user["id"]

    resp = await client.post(
        f"/api/identity/users/{user_id}/reset-password",
        json={"new_password": "NewSecurePassword123!"},
        headers=_headers(admin_token),
    )
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_list_users_with_search(client: AsyncClient, admin_token: str):
    with patch("app.kafka.producer.get_producer", new_callable=AsyncMock) as mp:
        mp.return_value.send = AsyncMock()
        await client.post(
            "/api/identity/users",
            json={
                "employee_id": f"E-SRCH-{uuid4().hex[:6]}",
                "username": f"search_user_{uuid4().hex[:8]}",
                "email": f"search_{uuid4().hex[:6]}@test.local",
                "full_name": "Уникальное Поисковое Имя",
            },
            headers=_headers(admin_token),
        )

    resp = await client.get(
        "/api/identity/users",
        params={"search": "Уникальное Поисковое"},
        headers=_headers(admin_token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1


@pytest.mark.asyncio
async def test_get_user_not_found(client: AsyncClient, admin_token: str):
    resp = await client.get(f"/api/identity/users/{uuid4()}", headers=_headers(admin_token))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_suspend_non_active_user(client: AsyncClient, admin_token: str):
    user = await _create_user_via_api(client, admin_token)
    user_id = user["id"]

    with patch("app.kafka.producer.get_producer", new_callable=AsyncMock) as mp:
        mp.return_value.send = AsyncMock()
        await client.post(f"/api/identity/users/{user_id}/suspend", headers=_headers(admin_token))

    with patch("app.kafka.producer.get_producer", new_callable=AsyncMock) as mp:
        mp.return_value.send = AsyncMock()
        resp = await client.post(f"/api/identity/users/{user_id}/suspend", headers=_headers(admin_token))
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_restore_non_suspended_user(client: AsyncClient, admin_token: str):
    user = await _create_user_via_api(client, admin_token)
    user_id = user["id"]

    with patch("app.kafka.producer.get_producer", new_callable=AsyncMock) as mp:
        mp.return_value.send = AsyncMock()
        resp = await client.post(f"/api/identity/users/{user_id}/restore", headers=_headers(admin_token))
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_block_already_blocked_user(client: AsyncClient, admin_token: str):
    user = await _create_user_via_api(client, admin_token)
    user_id = user["id"]

    with patch("app.kafka.producer.get_producer", new_callable=AsyncMock) as mp:
        mp.return_value.send = AsyncMock()
        await client.post(f"/api/identity/users/{user_id}/block", headers=_headers(admin_token))

    with patch("app.kafka.producer.get_producer", new_callable=AsyncMock) as mp:
        mp.return_value.send = AsyncMock()
        resp = await client.post(f"/api/identity/users/{user_id}/block", headers=_headers(admin_token))
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_transfer_user_service(db_session):
    from unittest.mock import AsyncMock, patch
    from app.models.identity import UserExt, UserStatus, Position, Department
    from app.modules.identity import service

    pos = Position(id=uuid4(), code=f"POS-{uuid4().hex[:6]}", name="Должность", level=1)
    dept = Department(id=uuid4(), code=f"DEPT-{uuid4().hex[:6]}", name="Отдел")
    user = UserExt(
        id=uuid4(),
        employee_id=f"E-TR-{uuid4().hex[:6]}",
        username=f"tr_{uuid4().hex[:8]}",
        email=f"tr_{uuid4().hex[:6]}@test.local",
        full_name="Переводимый",
        status=UserStatus.active,
    )
    db_session.add(pos)
    db_session.add(dept)
    db_session.add(user)
    await db_session.flush()

    with patch("app.kafka.producer.get_producer", new_callable=AsyncMock) as mp:
        mp.return_value.send = AsyncMock()
        result = await service.transfer_user(
            db_session, user, position_code=pos.code, department_code=dept.code
        )
    assert result.position_id == pos.id
    assert result.department_id == dept.id
