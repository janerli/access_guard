"""Tests for PATCH /api/auth/me/password."""
from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_change_password_success(client: AsyncClient, admin_token: str, seed_admin):
    """Successfully change password with correct current password."""
    # Change to a new password (must be ≥12 chars)
    resp = await client.patch(
        "/api/auth/me/password",
        json={"current_password": seed_admin["password"], "new_password": "NewPass456789!"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "id" in data or "username" in data

    # Restore original password so other tests still work
    new_token_resp = await client.post("/api/auth/login", json={
        "username": seed_admin["username"],
        "password": "NewPass456789!",
    })
    assert new_token_resp.status_code == 200
    new_token = new_token_resp.json()["access_token"]

    restore = await client.patch(
        "/api/auth/me/password",
        json={"current_password": "NewPass456789!", "new_password": seed_admin["password"]},
        headers={"Authorization": f"Bearer {new_token}"},
    )
    assert restore.status_code == 200


@pytest.mark.asyncio
async def test_change_password_wrong_current(client: AsyncClient, admin_token: str):
    """Returns 400 when current_password is wrong."""
    resp = await client.patch(
        "/api/auth/me/password",
        json={"current_password": "WrongPass999!", "new_password": "NewPass456!"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 400
    assert "неверен" in resp.json()["detail"].lower() or "current" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_change_password_weak_new_password(client: AsyncClient, admin_token: str, seed_admin):
    """Returns 400 when new_password is too weak."""
    resp = await client.patch(
        "/api/auth/me/password",
        json={"current_password": seed_admin["password"], "new_password": "abc"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_change_password_requires_auth(client: AsyncClient):
    """Returns 401 without token."""
    resp = await client.patch(
        "/api/auth/me/password",
        json={"current_password": "any", "new_password": "NewPass456!"},
    )
    assert resp.status_code == 401
