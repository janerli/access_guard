"""Tests for alert_service and audit_service (covers previously untested paths)."""
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.models.monitor import (
    Alert,
    AlertConditionType,
    AlertDataSource,
    AlertRule,
    AlertSeverity,
    AlertStatus,
    AuditLog,
    AuditModule,
    AuditOperation,
    AuditResult,
    AuditTargetType,
    NotificationChannel,
    NotificationChannelType,
)
from app.modules.monitor import alert_service, audit_service


# ── Fixtures ──────────────────────────────────────────────────────────────────

async def _make_rule(db, code_suffix: str = "") -> AlertRule:
    rule = AlertRule(
        id=uuid4(),
        code=f"test_svc_{uuid4().hex[:6]}{code_suffix}",
        name="Test Rule",
        description="",
        condition_type=AlertConditionType.threshold,
        condition_config={"threshold": 3},
        severity=AlertSeverity.high,
        is_enabled=True,
        cooldown_seconds=0,
        data_source=AlertDataSource.postgres,
    )
    db.add(rule)
    await db.flush()
    return rule


# ── alert_service ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_fire_alert_creates_alert(db_session):
    rule = await _make_rule(db_session)
    with patch("app.modules.monitor.notification_service.send", new=AsyncMock()):
        alert = await alert_service.fire_alert(
            db_session, rule,
            details={"test": True},
        )
    assert alert is not None
    assert alert.rule_id == rule.id
    assert alert.severity == AlertSeverity.high
    assert alert.status == AlertStatus.new
    assert alert.details == {"test": True}


@pytest.mark.asyncio
async def test_fire_alert_respects_cooldown(db_session):
    rule = await _make_rule(db_session)
    rule.cooldown_seconds = 3600  # 1 hour cooldown

    with patch("app.modules.monitor.notification_service.send", new=AsyncMock()):
        alert1 = await alert_service.fire_alert(db_session, rule)
        assert alert1 is not None
        # Second call within cooldown → should return None
        alert2 = await alert_service.fire_alert(db_session, rule)
        assert alert2 is None


@pytest.mark.asyncio
async def test_fire_alert_zero_cooldown_fires_multiple(db_session):
    rule = await _make_rule(db_session)
    rule.cooldown_seconds = 0

    with patch("app.modules.monitor.notification_service.send", new=AsyncMock()):
        a1 = await alert_service.fire_alert(db_session, rule, details={"i": 1})
        a2 = await alert_service.fire_alert(db_session, rule, details={"i": 2})
    assert a1 is not None
    assert a2 is not None
    assert a1.id != a2.id


@pytest.mark.asyncio
async def test_acknowledge_alert(db_session):
    rule = await _make_rule(db_session)
    with patch("app.modules.monitor.notification_service.send", new=AsyncMock()):
        alert = await alert_service.fire_alert(db_session, rule)
    assert alert is not None

    admin_id = uuid4()
    acked = await alert_service.acknowledge_alert(db_session, alert, admin_id, comment="Looking into it")
    assert acked.status == AlertStatus.acknowledged
    assert acked.acknowledged_by == admin_id
    assert acked.resolution_comment == "Looking into it"
    assert acked.acknowledged_at is not None


@pytest.mark.asyncio
async def test_resolve_alert(db_session):
    rule = await _make_rule(db_session)
    with patch("app.modules.monitor.notification_service.send", new=AsyncMock()):
        alert = await alert_service.fire_alert(db_session, rule)
    assert alert is not None

    admin_id = uuid4()
    resolved = await alert_service.resolve_alert(db_session, alert, admin_id, comment="Fixed")
    assert resolved.status == AlertStatus.resolved
    assert resolved.acknowledged_by == admin_id
    assert resolved.resolution_comment == "Fixed"


@pytest.mark.asyncio
async def test_mark_false_positive(db_session):
    rule = await _make_rule(db_session)
    with patch("app.modules.monitor.notification_service.send", new=AsyncMock()):
        alert = await alert_service.fire_alert(db_session, rule)
    assert alert is not None

    admin_id = uuid4()
    fp = await alert_service.mark_false_positive(db_session, alert, admin_id, comment="Not real")
    assert fp.status == AlertStatus.false_positive
    assert fp.resolution_comment == "Not real"


@pytest.mark.asyncio
async def test_fire_alert_with_subject_user(db_session, seed_user_ext):
    rule = await _make_rule(db_session)
    user_id = seed_user_ext  # str UUID from conftest

    with patch("app.modules.monitor.notification_service.send", new=AsyncMock()):
        alert = await alert_service.fire_alert(
            db_session, rule,
            subject_user_id=user_id,
            details={"reason": "test"},
        )
    assert alert is not None


# ── audit_service ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_audit_service_log_creates_entry_and_outbox(db_session):
    """audit_service.log() writes AuditLog + OutboxEvent in the same flush."""
    from app.models.monitor import OutboxEvent, OutboxStatus

    with patch(
        "app.modules.monitor.tasks.evaluate_simple_rules.apply_async"
    ):
        entry = await audit_service.log(
            db_session,
            operation=AuditOperation.login_success,
            module=AuditModule.auth,
            target_type=AuditTargetType.system,
            target_id="test",
            result=AuditResult.success,
            actor_username="testuser",
            ip_address="127.0.0.1",
            details={"sim": True},
        )

    assert entry.id is not None
    assert entry.operation == AuditOperation.login_success
    assert entry.actor_username == "testuser"

    # Outbox entry should exist
    outbox = (
        await db_session.execute(
            select(OutboxEvent).where(OutboxEvent.audit_log_id == entry.id)
        )
    ).scalar_one_or_none()
    assert outbox is not None
    assert outbox.status == OutboxStatus.pending
    assert outbox.payload["actor_username"] == "testuser"


@pytest.mark.asyncio
async def test_audit_service_log_user_agent_truncated(db_session):
    with patch("app.modules.monitor.tasks.evaluate_simple_rules.apply_async"):
        entry = await audit_service.log(
            db_session,
            operation=AuditOperation.create,
            module=AuditModule.identity,
            target_type=AuditTargetType.user,
            actor_username="admin",
            user_agent="A" * 600,
        )
    assert entry.user_agent is not None
    assert len(entry.user_agent) == 500


# ── notification_service._send_log ────────────────────────────────────────────

def test_send_log_writes_to_file(tmp_path):
    """_send_log writes alert details to a file without raising."""
    import asyncio
    from app.modules.monitor.notification_service import _send_log

    log_file = tmp_path / "alerts.log"
    rule = AlertRule(
        id=uuid4(), code="test_log", name="Log Test",
        condition_type=AlertConditionType.pattern,
        condition_config={}, severity=AlertSeverity.medium,
        is_enabled=True, cooldown_seconds=0,
        data_source=AlertDataSource.postgres,
    )
    alert = Alert(
        id=uuid4(), rule_id=rule.id,
        severity=AlertSeverity.medium,
        status=AlertStatus.new,
        details={"key": "value"},
    )
    channel = NotificationChannel(
        id=uuid4(), code="log_test",
        type=NotificationChannelType.log,
        config={"path": str(log_file)},
        is_enabled=True,
    )
    _send_log(alert, rule, channel)

    content = log_file.read_text(encoding="utf-8")
    assert "Log Test" in content
    assert "medium" in content.lower()
    assert "key" in content


def test_send_log_bad_path_does_not_raise():
    """_send_log swallows OSError silently."""
    from app.modules.monitor.notification_service import _send_log

    rule = AlertRule(
        id=uuid4(), code="x", name="x",
        condition_type=AlertConditionType.pattern,
        condition_config={}, severity=AlertSeverity.low,
        is_enabled=True, cooldown_seconds=0,
        data_source=AlertDataSource.postgres,
    )
    alert = Alert(
        id=uuid4(), rule_id=rule.id,
        severity=AlertSeverity.low, status=AlertStatus.new, details={},
    )
    channel = NotificationChannel(
        id=uuid4(), code="bad", type=NotificationChannelType.log,
        config={"path": "/nonexistent/dir/alerts.log"}, is_enabled=True,
    )
    # Should not raise
    _send_log(alert, rule, channel)
