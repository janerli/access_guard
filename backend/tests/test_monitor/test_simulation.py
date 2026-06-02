"""Tests for the threat simulation endpoints."""
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from httpx import AsyncClient

from app.models.monitor import (
    AlertConditionType,
    AlertDataSource,
    AlertRule,
    AlertSeverity,
)


def _h(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _seed_rule(client: AsyncClient, code: str, token: str, data_source: str = "postgres") -> None:
    """Create an alert rule via API so simulation can find it."""
    await client.post(
        "/api/monitor/rules",
        json={
            "code": code,
            "name": f"Sim rule {code}",
            "description": "",
            "condition_type": "threshold",
            "condition_config": {"threshold": 5, "window_minutes": 15},
            "severity": "high",
            "cooldown_seconds": 0,
            "data_source": data_source,
        },
        headers=_h(token),
    )


# ── GET /scenarios ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_scenarios(client: AsyncClient):
    resp = await client.get("/api/simulation/scenarios")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 10
    codes = {s["code"] for s in data}
    assert "multiple_failed_logins" in codes
    assert "data_exfiltration_pattern" in codes


@pytest.mark.asyncio
async def test_list_scenarios_has_required_fields(client: AsyncClient):
    resp = await client.get("/api/simulation/scenarios")
    for s in resp.json():
        assert "code" in s
        assert "name" in s
        assert "severity" in s
        assert "data_source" in s
        assert "how" in s


# ── Auth guard ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_run_simulation_requires_auth(client: AsyncClient):
    resp = await client.post("/api/simulation/run/multiple_failed_logins")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_run_unknown_scenario_404(client: AsyncClient, admin_token: str):
    resp = await client.post(
        "/api/simulation/run/nonexistent_rule",
        headers=_h(admin_token),
    )
    assert resp.status_code == 404


# ── Simple rule simulations ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_sim_multiple_failed_logins(client: AsyncClient, admin_token: str):
    await _seed_rule(client, "multiple_failed_logins", admin_token, "postgres")
    with patch("app.modules.monitor.notification_service.send", new=AsyncMock()):
        with patch("app.modules.monitor.tasks.evaluate_simple_rules.apply_async"):
            resp = await client.post(
                "/api/simulation/run/multiple_failed_logins",
                headers=_h(admin_token),
            )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["scenario_code"] == "multiple_failed_logins"
    assert data["audit_entries_created"] >= 6
    assert data["alert_id"] is not None


@pytest.mark.asyncio
async def test_sim_privileged_role_assigned(client: AsyncClient, admin_token: str):
    await _seed_rule(client, "privileged_role_assigned", admin_token, "postgres")
    with patch("app.modules.monitor.notification_service.send", new=AsyncMock()):
        with patch("app.modules.monitor.tasks.evaluate_simple_rules.apply_async"):
            resp = await client.post(
                "/api/simulation/run/privileged_role_assigned",
                headers=_h(admin_token),
            )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["alert_id"] is not None


@pytest.mark.asyncio
async def test_sim_audit_log_tampering(client: AsyncClient, admin_token: str):
    await _seed_rule(client, "audit_log_tampering_attempt", admin_token, "postgres")
    with patch("app.modules.monitor.notification_service.send", new=AsyncMock()):
        with patch("app.modules.monitor.tasks.evaluate_simple_rules.apply_async"):
            resp = await client.post(
                "/api/simulation/run/audit_log_tampering_attempt",
                headers=_h(admin_token),
            )
    assert resp.status_code == 200
    assert resp.json()["success"] is True


@pytest.mark.asyncio
async def test_sim_admin_password_reset(client: AsyncClient, admin_token: str):
    await _seed_rule(client, "admin_password_reset", admin_token, "postgres")
    with patch("app.modules.monitor.notification_service.send", new=AsyncMock()):
        with patch("app.modules.monitor.tasks.evaluate_simple_rules.apply_async"):
            resp = await client.post(
                "/api/simulation/run/admin_password_reset",
                headers=_h(admin_token),
            )
    assert resp.status_code == 200
    assert resp.json()["success"] is True


# ── ES-direct simulations ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_sim_login_outside_hours(client: AsyncClient, admin_token: str):
    await _seed_rule(client, "login_outside_hours", admin_token, "elasticsearch")
    with patch("app.modules.monitor.notification_service.send", new=AsyncMock()):
        resp = await client.post(
            "/api/simulation/run/login_outside_hours",
            headers=_h(admin_token),
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["alert_id"] is not None


@pytest.mark.asyncio
async def test_sim_mass_permission_failures(client: AsyncClient, admin_token: str):
    await _seed_rule(client, "mass_permission_failures", admin_token, "elasticsearch")
    with patch("app.modules.monitor.notification_service.send", new=AsyncMock()):
        with patch("app.modules.monitor.tasks.evaluate_simple_rules.apply_async"):
            resp = await client.post(
                "/api/simulation/run/mass_permission_failures",
                headers=_h(admin_token),
            )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["audit_entries_created"] >= 12


@pytest.mark.asyncio
async def test_sim_inactive_user_login(client: AsyncClient, admin_token: str):
    await _seed_rule(client, "inactive_user_login", admin_token, "elasticsearch")
    with patch("app.modules.monitor.notification_service.send", new=AsyncMock()):
        resp = await client.post(
            "/api/simulation/run/inactive_user_login",
            headers=_h(admin_token),
        )
    assert resp.status_code == 200
    assert resp.json()["success"] is True


# ── run-all ───────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_run_all_returns_list(client: AsyncClient, admin_token: str):
    # Seed all 10 rules
    rules = [
        ("multiple_failed_logins", "postgres"),
        ("privileged_role_assigned", "postgres"),
        ("audit_log_tampering_attempt", "postgres"),
        ("admin_password_reset", "postgres"),
        ("login_outside_hours", "elasticsearch"),
        ("mass_permission_failures", "elasticsearch"),
        ("bulk_user_changes", "elasticsearch"),
        ("inactive_user_login", "elasticsearch"),
        ("unusual_geo_login", "elasticsearch"),
        ("data_exfiltration_pattern", "elasticsearch"),
    ]
    for code, ds in rules:
        await _seed_rule(client, code, admin_token, ds)

    with patch("app.modules.monitor.notification_service.send", new=AsyncMock()):
        with patch("app.modules.monitor.tasks.evaluate_simple_rules.apply_async"):
            resp = await client.post("/api/simulation/run-all", headers=_h(admin_token))

    assert resp.status_code == 200
    results = resp.json()
    assert isinstance(results, list)
    assert len(results) == 10
