"""Тесты Access модуля — роли, разрешения, назначение, заявки."""
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from httpx import AsyncClient


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ── Roles CRUD ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_roles(client: AsyncClient, admin_token: str):
    resp = await client.get("/api/access/roles", headers=_headers(admin_token))
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    # Migration seeds 7 roles — but test DB may be clean, just check structure
    assert isinstance(data["items"], list)


@pytest.mark.asyncio
async def test_create_role(client: AsyncClient, admin_token: str):
    code = f"test_role_{uuid4().hex[:6]}"
    resp = await client.post(
        "/api/access/roles",
        json={"code": code, "name": "Тестовая роль", "description": "Для теста", "is_privileged": False},
        headers=_headers(admin_token),
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["code"] == code
    assert data["is_privileged"] is False
    return data["id"]


@pytest.mark.asyncio
async def test_create_role_duplicate_code(client: AsyncClient, admin_token: str):
    code = f"dup_role_{uuid4().hex[:6]}"
    body = {"code": code, "name": "Дубль", "description": ""}
    resp1 = await client.post("/api/access/roles", json=body, headers=_headers(admin_token))
    assert resp1.status_code == 201
    resp2 = await client.post("/api/access/roles", json=body, headers=_headers(admin_token))
    assert resp2.status_code == 400


@pytest.mark.asyncio
async def test_get_role_detail(client: AsyncClient, admin_token: str):
    code = f"detail_role_{uuid4().hex[:6]}"
    create = await client.post(
        "/api/access/roles",
        json={"code": code, "name": "Детальная роль"},
        headers=_headers(admin_token),
    )
    role_id = create.json()["id"]

    resp = await client.get(f"/api/access/roles/{role_id}", headers=_headers(admin_token))
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == role_id
    assert "permissions" in data
    assert isinstance(data["permissions"], list)


@pytest.mark.asyncio
async def test_update_role(client: AsyncClient, admin_token: str):
    code = f"upd_role_{uuid4().hex[:6]}"
    create = await client.post(
        "/api/access/roles",
        json={"code": code, "name": "До обновления"},
        headers=_headers(admin_token),
    )
    role_id = create.json()["id"]

    resp = await client.patch(
        f"/api/access/roles/{role_id}",
        json={"name": "После обновления"},
        headers=_headers(admin_token),
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "После обновления"


@pytest.mark.asyncio
async def test_delete_role(client: AsyncClient, admin_token: str):
    code = f"del_role_{uuid4().hex[:6]}"
    create = await client.post(
        "/api/access/roles",
        json={"code": code, "name": "Удаляемая"},
        headers=_headers(admin_token),
    )
    role_id = create.json()["id"]

    resp = await client.delete(f"/api/access/roles/{role_id}", headers=_headers(admin_token))
    assert resp.status_code == 204

    get_resp = await client.get(f"/api/access/roles/{role_id}", headers=_headers(admin_token))
    assert get_resp.status_code == 404


# ── Permissions ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_permissions(client: AsyncClient, admin_token: str):
    resp = await client.get("/api/access/permissions", headers=_headers(admin_token))
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_add_remove_permission_to_role(client: AsyncClient, admin_token: str, db_session):
    # Create a role and a second role to borrow its permission id from list
    code = f"perm_role_{uuid4().hex[:6]}"
    role_resp = await client.post(
        "/api/access/roles",
        json={"code": code, "name": "Роль для разрешений"},
        headers=_headers(admin_token),
    )
    role_id = role_resp.json()["id"]

    perms_resp = await client.get("/api/access/permissions", headers=_headers(admin_token))
    perms = perms_resp.json()
    if not perms:
        from app.models.access import Permission

        code = f"perm_{uuid4().hex[:8]}"
        permission = Permission(code=code, description="Test permission")
        db_session.add(permission)
        await db_session.commit()

        perms_resp = await client.get("/api/access/permissions", headers=_headers(admin_token))
        perms = perms_resp.json()
        assert perms

    perm_id = perms[0]["id"]

    # Add permission
    add = await client.post(
        f"/api/access/roles/{role_id}/permissions/{perm_id}",
        headers=_headers(admin_token),
    )
    assert add.status_code == 204

    # Check it's there
    detail = await client.get(f"/api/access/roles/{role_id}", headers=_headers(admin_token))
    perm_ids = [p["id"] for p in detail.json()["permissions"]]
    assert perm_id in perm_ids

    # Remove permission
    remove = await client.delete(
        f"/api/access/roles/{role_id}/permissions/{perm_id}",
        headers=_headers(admin_token),
    )
    assert remove.status_code == 204


# ── Access Requests ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_access_request(client: AsyncClient, admin_token: str, seed_user_ext: str):
    code = f"req_role_{uuid4().hex[:6]}"
    role_resp = await client.post(
        "/api/access/roles",
        json={"code": code, "name": "Роль заявки"},
        headers=_headers(admin_token),
    )
    role_id = role_resp.json()["id"]

    resp = await client.post(
        "/api/access/requests",
        json={"user_id": seed_user_ext, "role_id": role_id, "justification": "Нужна для работы"},
        headers=_headers(admin_token),
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["status"] == "pending"
    assert data["role"]["id"] == role_id
    return data["id"]


@pytest.mark.asyncio
async def test_approve_access_request(client: AsyncClient, admin_token: str, seed_user_ext: str):
    code = f"apr_role_{uuid4().hex[:6]}"
    role_resp = await client.post(
        "/api/access/roles",
        json={"code": code, "name": "Роль для одобрения"},
        headers=_headers(admin_token),
    )
    role_id = role_resp.json()["id"]

    req_resp = await client.post(
        "/api/access/requests",
        json={"user_id": seed_user_ext, "role_id": role_id, "justification": "Обоснование"},
        headers=_headers(admin_token),
    )
    req_id = req_resp.json()["id"]

    approve = await client.post(
        f"/api/access/requests/{req_id}/approve",
        json={"comment": "Одобрено"},
        headers=_headers(admin_token),
    )
    assert approve.status_code == 200
    assert approve.json()["status"] == "approved"


@pytest.mark.asyncio
async def test_reject_access_request(client: AsyncClient, admin_token: str, seed_user_ext: str):
    code = f"rej_role_{uuid4().hex[:6]}"
    role_resp = await client.post(
        "/api/access/roles",
        json={"code": code, "name": "Роль для отклонения"},
        headers=_headers(admin_token),
    )
    role_id = role_resp.json()["id"]

    req_resp = await client.post(
        "/api/access/requests",
        json={"user_id": seed_user_ext, "role_id": role_id, "justification": "Обоснование"},
        headers=_headers(admin_token),
    )
    req_id = req_resp.json()["id"]

    reject = await client.post(
        f"/api/access/requests/{req_id}/reject",
        json={"comment": "Отклонено по политике"},
        headers=_headers(admin_token),
    )
    assert reject.status_code == 200
    assert reject.json()["status"] == "rejected"


# ── Permission Matrix ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_matrix(client: AsyncClient, admin_token: str):
    resp = await client.get("/api/access/matrix", headers=_headers(admin_token))
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    if data:
        row = data[0]
        assert "position_id" in row
        assert "position_code" in row
        assert "role_ids" in row
        assert "roles" in row


@pytest.mark.asyncio
async def test_check_permission(client: AsyncClient, admin_token: str):
    # Just verify the endpoint responds (admin user has no user_ext record in test DB)
    resp = await client.post(
        "/api/access/check",
        json={"user_id": str(uuid4()), "permission_code": "users.read"},
        headers=_headers(admin_token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "allowed" in data
    assert data["allowed"] is False  # no roles assigned to random UUID
