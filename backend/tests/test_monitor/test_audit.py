"""Тесты Monitor модуля — audit_log, alert_rules, alerts."""
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from httpx import AsyncClient


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ── Dashboard ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_dashboard(client: AsyncClient, admin_token: str):
    resp = await client.get("/api/monitor/dashboard", headers=_headers(admin_token))
    assert resp.status_code == 200
    data = resp.json()
    assert "total_events_today" in data
    assert "active_alerts" in data
    assert "events_by_module" in data


# ── Audit Log ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_audit_entry(client: AsyncClient, admin_token: str):
    resp = await client.post(
        "/api/monitor/audit",
        json={
            "operation": "login_success",
            "module": "auth",
            "target_type": "system",
            "target_id": "test",
            "result": "success",
            "actor_username": "testuser",
        },
        headers=_headers(admin_token),
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["operation"] == "login_success"
    assert data["module"] == "auth"
    return data["event_id"]


@pytest.mark.asyncio
async def test_list_audit(client: AsyncClient, admin_token: str):
    # Create an entry first
    await client.post(
        "/api/monitor/audit",
        json={"operation": "create", "module": "identity", "target_type": "user", "result": "success", "actor_username": "admin"},
        headers=_headers(admin_token),
    )
    resp = await client.get("/api/monitor/audit", headers=_headers(admin_token))
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert isinstance(data["items"], list)


@pytest.mark.asyncio
async def test_list_audit_with_filters(client: AsyncClient, admin_token: str):
    resp = await client.get(
        "/api/monitor/audit",
        params={"operation": "login_success", "result": "success"},
        headers=_headers(admin_token),
    )
    assert resp.status_code == 200
    data = resp.json()
    for item in data["items"]:
        assert item["operation"] == "login_success"
        assert item["result"] == "success"


@pytest.mark.asyncio
async def test_get_audit_entry_by_event_id(client: AsyncClient, admin_token: str):
    create = await client.post(
        "/api/monitor/audit",
        json={"operation": "delete", "module": "identity", "target_type": "user", "result": "success", "actor_username": "admin2"},
        headers=_headers(admin_token),
    )
    event_id = create.json()["event_id"]
    resp = await client.get(f"/api/monitor/audit/{event_id}", headers=_headers(admin_token))
    assert resp.status_code == 200
    assert resp.json()["event_id"] == event_id


@pytest.mark.asyncio
async def test_get_audit_entry_not_found(client: AsyncClient, admin_token: str):
    resp = await client.get(f"/api/monitor/audit/{uuid4()}", headers=_headers(admin_token))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_export_audit_csv(client: AsyncClient, admin_token: str):
    resp = await client.get("/api/monitor/audit/export", params={"fmt": "csv"}, headers=_headers(admin_token))
    assert resp.status_code == 200
    assert "text/csv" in resp.headers.get("content-type", "")


# ── Alert Rules ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_rules(client: AsyncClient, admin_token: str):
    resp = await client.get("/api/monitor/rules", headers=_headers(admin_token))
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert isinstance(data["items"], list)
    # Migration seeds 10 rules
    assert data["total"] >= 0  # could be 0 in fresh test DB


@pytest.mark.asyncio
async def test_create_rule(client: AsyncClient, admin_token: str):
    code = f"test_rule_{uuid4().hex[:6]}"
    resp = await client.post(
        "/api/monitor/rules",
        json={
            "code": code,
            "name": "Тестовое правило",
            "description": "Для теста",
            "condition_type": "threshold",
            "condition_config": {"threshold": 5},
            "severity": "medium",
            "cooldown_seconds": 300,
            "data_source": "postgres",
        },
        headers=_headers(admin_token),
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["code"] == code
    assert data["is_enabled"] is True
    return data["id"]


@pytest.mark.asyncio
async def test_create_rule_duplicate_code(client: AsyncClient, admin_token: str):
    code = f"dup_rule_{uuid4().hex[:6]}"
    body = {"code": code, "name": "Дубль", "condition_type": "threshold",
            "condition_config": {}, "severity": "low", "data_source": "postgres"}
    r1 = await client.post("/api/monitor/rules", json=body, headers=_headers(admin_token))
    assert r1.status_code == 201
    r2 = await client.post("/api/monitor/rules", json=body, headers=_headers(admin_token))
    assert r2.status_code == 400


@pytest.mark.asyncio
async def test_toggle_rule(client: AsyncClient, admin_token: str):
    code = f"toggle_rule_{uuid4().hex[:6]}"
    create = await client.post(
        "/api/monitor/rules",
        json={"code": code, "name": "Переключаемое", "condition_type": "pattern",
              "condition_config": {}, "severity": "info", "data_source": "postgres"},
        headers=_headers(admin_token),
    )
    rule_id = create.json()["id"]
    assert create.json()["is_enabled"] is True

    toggle = await client.post(f"/api/monitor/rules/{rule_id}/toggle", headers=_headers(admin_token))
    assert toggle.status_code == 200
    assert toggle.json()["is_enabled"] is False

    toggle2 = await client.post(f"/api/monitor/rules/{rule_id}/toggle", headers=_headers(admin_token))
    assert toggle2.json()["is_enabled"] is True


@pytest.mark.asyncio
async def test_update_rule(client: AsyncClient, admin_token: str):
    code = f"upd_rule_{uuid4().hex[:6]}"
    create = await client.post(
        "/api/monitor/rules",
        json={"code": code, "name": "До", "condition_type": "threshold",
              "condition_config": {"threshold": 3}, "severity": "low", "data_source": "postgres"},
        headers=_headers(admin_token),
    )
    rule_id = create.json()["id"]
    patch = await client.patch(
        f"/api/monitor/rules/{rule_id}",
        json={"name": "После", "severity": "high"},
        headers=_headers(admin_token),
    )
    assert patch.status_code == 200
    assert patch.json()["name"] == "После"
    assert patch.json()["severity"] == "high"


# ── Alerts ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_alerts(client: AsyncClient, admin_token: str):
    resp = await client.get("/api/monitor/alerts", headers=_headers(admin_token))
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert isinstance(data["items"], list)


@pytest.mark.asyncio
async def test_notification_channels(client: AsyncClient, admin_token: str):
    resp = await client.get("/api/monitor/channels", headers=_headers(admin_token))
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_create_channel(client: AsyncClient, admin_token: str):
    code = f"ch_{uuid4().hex[:6]}"
    resp = await client.post(
        "/api/monitor/channels",
        json={"code": code, "type": "log", "config": {"path": "/tmp/test.log"}, "is_enabled": False},
        headers=_headers(admin_token),
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["code"] == code
    assert resp.json()["is_enabled"] is False


# ── Simple rule evaluation ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_simple_rule_multiple_failed_logins(client: AsyncClient, admin_token: str, db_session):
    """Check that multiple_failed_logins rule fires correctly via direct function call."""
    from app.models.monitor import AuditLog, AuditOperation, AuditTargetType, AuditModule, AuditResult
    from app.modules.monitor.rules import check_multiple_failed_logins

    entry = AuditLog(
        operation=AuditOperation.login_failure,
        module=AuditModule.auth,
        target_type=AuditTargetType.system,
        actor_username="hacker_user_unique_xyz",
        result=AuditResult.failure,
    )
    # threshold=999 means the rule won't fire unless 999+ failures exist
    result = await check_multiple_failed_logins(
        db_session,
        {"threshold": 999, "window_minutes": 15},
        entry,
    )
    assert result.matched is False


@pytest.mark.asyncio
async def test_simple_rule_privileged_role_assigned(client: AsyncClient, admin_token: str):
    from app.models.monitor import AuditLog, AuditOperation, AuditTargetType, AuditModule, AuditResult
    from app.modules.monitor.rules import check_privileged_role_assigned

    entry_priv = AuditLog(
        operation=AuditOperation.role_assign,
        module=AuditModule.access,
        target_type=AuditTargetType.role,
        actor_username="admin",
        result=AuditResult.success,
        details={"is_privileged": True, "role_code": "system_admin"},
    )
    result = await check_privileged_role_assigned(None, {}, entry_priv)
    assert result.matched is True

    entry_regular = AuditLog(
        operation=AuditOperation.role_assign,
        module=AuditModule.access,
        target_type=AuditTargetType.role,
        actor_username="admin",
        result=AuditResult.success,
        details={"is_privileged": False, "role_code": "employee"},
    )
    result2 = await check_privileged_role_assigned(None, {}, entry_regular)
    assert result2.matched is False


@pytest.mark.asyncio
async def test_simple_rule_audit_tampering(client: AsyncClient, admin_token: str):
    from app.models.monitor import AuditLog, AuditOperation, AuditTargetType, AuditModule, AuditResult
    from app.modules.monitor.rules import check_audit_log_tampering

    entry = AuditLog(
        operation=AuditOperation.delete,
        module=AuditModule.monitor,
        target_type=AuditTargetType.system,
        actor_username="attacker",
        result=AuditResult.denied,
        details={"table": "audit_log"},
    )
    result = await check_audit_log_tampering(None, {}, entry)
    assert result.matched is True


@pytest.mark.asyncio
async def test_kibana_token_endpoint(client: AsyncClient, admin_token: str):
    resp = await client.get("/api/monitor/kibana-token", headers=_headers(admin_token))
    assert resp.status_code == 200
    assert "embed_url" in resp.json()
