"""Unit-tests for Monitor detection rules (simple + complex)."""
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.models.monitor import AuditLog, AuditModule, AuditOperation, AuditResult, AuditTargetType
from app.modules.monitor.rules import (
    BaseRule,
    RuleMatch,
    COMPLEX_RULES,
    SIMPLE_RULES,
    check_admin_password_reset,
    check_audit_log_tampering,
    check_bulk_user_changes,
    check_data_exfiltration,
    check_inactive_user_login,
    check_login_outside_hours,
    check_mass_permission_failures,
    check_multiple_failed_logins,
    check_privileged_role_assigned,
    check_unusual_geo_login,
)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _audit(operation: AuditOperation, target_type: AuditTargetType = AuditTargetType.system,
           details: dict | None = None, username: str = "user") -> AuditLog:
    return AuditLog(
        operation=operation,
        module=AuditModule.auth,
        target_type=target_type,
        actor_username=username,
        result=AuditResult.success,
        details=details,
    )


def _es_resp(buckets: list[dict], agg_key: str = "by_user") -> dict:
    """Build a minimal ES aggregation response."""
    return {"aggregations": {agg_key: {"buckets": buckets}}, "hits": {"total": {"value": len(buckets)}}}


# ── BaseRule ──────────────────────────────────────────────────────────────────

def test_base_rule_is_abstract():
    with pytest.raises(TypeError):
        BaseRule()  # type: ignore[abstract]


def test_rule_registries_complete():
    assert set(SIMPLE_RULES.keys()) == {
        "multiple_failed_logins",
        "privileged_role_assigned",
        "audit_log_tampering_attempt",
        "admin_password_reset",
    }
    assert set(COMPLEX_RULES.keys()) == {
        "login_outside_hours",
        "mass_permission_failures",
        "bulk_user_changes",
        "inactive_user_login",
        "unusual_geo_login",
        "data_exfiltration_pattern",
    }


# ── Simple rules ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_multiple_failed_logins_no_match(db_session):
    entry = _audit(AuditOperation.login_failure, username="victim")
    result = await check_multiple_failed_logins(db_session, {"threshold": 999, "window_minutes": 15}, entry)
    assert result.matched is False


@pytest.mark.asyncio
async def test_multiple_failed_logins_wrong_operation(db_session):
    entry = _audit(AuditOperation.login_success)
    result = await check_multiple_failed_logins(db_session, {"threshold": 1}, entry)
    assert result.matched is False


@pytest.mark.asyncio
async def test_multiple_failed_logins_fires_at_threshold(db_session):
    username = f"brute_{uuid4().hex[:8]}"
    # Insert threshold-1 failures so one more will trigger
    for _ in range(5):
        db_session.add(_audit(AuditOperation.login_failure, username=username))
    await db_session.flush()

    entry = _audit(AuditOperation.login_failure, username=username)
    result = await check_multiple_failed_logins(db_session, {"threshold": 5, "window_minutes": 15}, entry)
    assert result.matched is True
    assert result.details["username"] == username


@pytest.mark.asyncio
async def test_privileged_role_assigned_matches():
    entry = _audit(AuditOperation.role_assign, target_type=AuditTargetType.role,
                   details={"is_privileged": True, "role_code": "system_admin"})
    result = await check_privileged_role_assigned(None, {}, entry)
    assert result.matched is True
    assert result.details["role"] == "system_admin"


@pytest.mark.asyncio
async def test_privileged_role_assigned_no_match_regular_role():
    entry = _audit(AuditOperation.role_assign, target_type=AuditTargetType.role,
                   details={"is_privileged": False, "role_code": "employee"})
    result = await check_privileged_role_assigned(None, {}, entry)
    assert result.matched is False


@pytest.mark.asyncio
async def test_privileged_role_assigned_wrong_operation():
    entry = _audit(AuditOperation.create)
    result = await check_privileged_role_assigned(None, {}, entry)
    assert result.matched is False


@pytest.mark.asyncio
async def test_audit_log_tampering_matches():
    entry = _audit(AuditOperation.delete, target_type=AuditTargetType.system,
                   details={"table": "audit_log"})
    result = await check_audit_log_tampering(None, {}, entry)
    assert result.matched is True


@pytest.mark.asyncio
async def test_audit_log_tampering_update_also_matches():
    entry = _audit(AuditOperation.update, target_type=AuditTargetType.system,
                   details={"table": "audit_log"})
    result = await check_audit_log_tampering(None, {}, entry)
    assert result.matched is True


@pytest.mark.asyncio
async def test_audit_log_tampering_different_table_no_match():
    entry = _audit(AuditOperation.delete, target_type=AuditTargetType.system,
                   details={"table": "users_ext"})
    result = await check_audit_log_tampering(None, {}, entry)
    assert result.matched is False


@pytest.mark.asyncio
async def test_admin_password_reset_matches():
    entry = _audit(AuditOperation.password_reset, details={"target_is_privileged": True})
    result = await check_admin_password_reset(None, {}, entry)
    assert result.matched is True


@pytest.mark.asyncio
async def test_admin_password_reset_non_privileged_no_match():
    entry = _audit(AuditOperation.password_reset, details={"target_is_privileged": False})
    result = await check_admin_password_reset(None, {}, entry)
    assert result.matched is False


@pytest.mark.asyncio
async def test_admin_password_reset_wrong_operation():
    entry = _audit(AuditOperation.create)
    result = await check_admin_password_reset(None, {}, entry)
    assert result.matched is False


# ── Complex rules (mocked Elasticsearch) ──────────────────────────────────────

@pytest.mark.asyncio
async def test_login_outside_hours_returns_matches():
    es = AsyncMock()
    es.search = AsyncMock(return_value=_es_resp([
        {"key": "nightowl", "doc_count": 3},
    ]))
    results = await check_login_outside_hours(es, {"start_hour": 22, "end_hour": 6})
    assert len(results) == 1
    assert results[0].matched is True
    assert results[0].details["username"] == "nightowl"


@pytest.mark.asyncio
async def test_login_outside_hours_empty_buckets():
    es = AsyncMock()
    es.search = AsyncMock(return_value=_es_resp([]))
    results = await check_login_outside_hours(es, {})
    assert results == []


@pytest.mark.asyncio
async def test_login_outside_hours_es_error_returns_empty():
    es = AsyncMock()
    es.search = AsyncMock(side_effect=Exception("ES down"))
    results = await check_login_outside_hours(es, {})
    assert results == []


@pytest.mark.asyncio
async def test_mass_permission_failures_matches():
    es = AsyncMock()
    es.search = AsyncMock(return_value=_es_resp([
        {"key": "attacker", "doc_count": 15},
    ]))
    results = await check_mass_permission_failures(es, {"threshold": 10, "window_minutes": 5})
    assert len(results) == 1
    assert results[0].details["count"] == 15


@pytest.mark.asyncio
async def test_mass_permission_failures_empty():
    es = AsyncMock()
    es.search = AsyncMock(return_value=_es_resp([]))
    results = await check_mass_permission_failures(es, {})
    assert results == []


@pytest.mark.asyncio
async def test_bulk_user_changes_matches():
    es = AsyncMock()
    es.search = AsyncMock(return_value=_es_resp([
        {"key": "rogue_admin", "doc_count": 25},
    ], agg_key="by_actor"))
    results = await check_bulk_user_changes(es, {"threshold": 20, "window_minutes": 10})
    assert len(results) == 1
    assert results[0].details["admin"] == "rogue_admin"


@pytest.mark.asyncio
async def test_bulk_user_changes_es_error():
    es = AsyncMock()
    es.search = AsyncMock(side_effect=RuntimeError("timeout"))
    results = await check_bulk_user_changes(es, {})
    assert results == []


@pytest.mark.asyncio
async def test_inactive_user_login_detects_inactive():
    es = AsyncMock()
    # Call 1: users who logged in recently
    # Call 2: 0 logins in dormancy window [threshold .. now) → potentially inactive
    # Call 3: >0 logins before threshold → was active before, so it's a real dormant account
    es.search = AsyncMock(side_effect=[
        _es_resp([{"key": "ghost_user", "doc_count": 1}], agg_key="users"),
        {"hits": {"total": {"value": 0}}, "aggregations": {}},
        {"hits": {"total": {"value": 3}}, "aggregations": {}},
    ])
    results = await check_inactive_user_login(es, {"inactive_days": 90})
    assert len(results) == 1
    assert results[0].details["username"] == "ghost_user"


@pytest.mark.asyncio
async def test_inactive_user_login_active_user_no_match():
    es = AsyncMock()
    es.search = AsyncMock(side_effect=[
        _es_resp([{"key": "active_user", "doc_count": 1}], agg_key="users"),
        {"hits": {"total": {"value": 5}}, "aggregations": {}},
    ])
    results = await check_inactive_user_login(es, {"inactive_days": 90})
    assert results == []


@pytest.mark.asyncio
async def test_unusual_geo_login_new_ip_flagged():
    es = AsyncMock()
    # Recent logins with new IP
    recent_resp = {
        "aggregations": {
            "by_user": {
                "buckets": [{
                    "key": "traveler",
                    "ips": {"buckets": [{"key": "1.2.3.4"}]},
                }]
            }
        }
    }
    # Historical logins: known IPs are different
    hist_resp = {
        "aggregations": {"ips": {"buckets": [{"key": "10.0.0.1"}]}}
    }
    es.search = AsyncMock(side_effect=[recent_resp, hist_resp])
    results = await check_unusual_geo_login(es, {"history_days": 30})
    assert len(results) == 1
    assert "1.2.3.4" in results[0].details["new_ips"]


@pytest.mark.asyncio
async def test_unusual_geo_login_known_ip_no_match():
    es = AsyncMock()
    recent_resp = {
        "aggregations": {
            "by_user": {
                "buckets": [{"key": "regular", "ips": {"buckets": [{"key": "10.0.0.1"}]}}]
            }
        }
    }
    hist_resp = {"aggregations": {"ips": {"buckets": [{"key": "10.0.0.1"}]}}}
    es.search = AsyncMock(side_effect=[recent_resp, hist_resp])
    results = await check_unusual_geo_login(es, {})
    assert results == []


@pytest.mark.asyncio
async def test_data_exfiltration_matches():
    es = AsyncMock()
    es.search = AsyncMock(return_value=_es_resp([
        {"key": "data_thief", "doc_count": 250},
    ]))
    results = await check_data_exfiltration(es, {"threshold": 100, "window_minutes": 30})
    assert len(results) == 1
    assert results[0].details["read_count"] == 250


@pytest.mark.asyncio
async def test_data_exfiltration_below_threshold_empty():
    es = AsyncMock()
    es.search = AsyncMock(return_value=_es_resp([]))
    results = await check_data_exfiltration(es, {"threshold": 100})
    assert results == []
