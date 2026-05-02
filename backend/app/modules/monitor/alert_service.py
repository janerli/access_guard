"""alert_service — creates alerts and fires notifications."""
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.monitor import Alert, AlertRule, AlertSeverity, AlertStatus, NotificationChannel
from app.modules.monitor import notification_service


async def fire_alert(
    db: AsyncSession,
    rule: AlertRule,
    subject_user_id: UUID | None = None,
    details: dict | None = None,
    correlation_id: UUID | None = None,
) -> Alert | None:
    """Create alert if cooldown passed; send notifications. Flush-only."""
    if rule.cooldown_seconds > 0:
        cooldown_since = datetime.now(timezone.utc) - timedelta(seconds=rule.cooldown_seconds)
        existing = (await db.execute(
            select(Alert).where(
                Alert.rule_id == rule.id,
                Alert.triggered_at >= cooldown_since,
                Alert.status != AlertStatus.false_positive,
            )
        )).scalar_one_or_none()
        if existing:
            return None

    alert = Alert(
        rule_id=rule.id,
        subject_user_id=subject_user_id,
        severity=rule.severity,
        details=details or {},
        correlation_id=correlation_id,
    )
    db.add(alert)
    await db.flush()

    channels = (await db.execute(
        select(NotificationChannel).where(NotificationChannel.is_enabled == True)  # noqa: E712
    )).scalars().all()

    await notification_service.send(alert, rule, list(channels))
    return alert


async def acknowledge_alert(db: AsyncSession, alert: Alert, admin_id: UUID, comment: str | None = None) -> Alert:
    alert.status = AlertStatus.acknowledged
    alert.acknowledged_at = datetime.now(timezone.utc)
    alert.acknowledged_by = admin_id
    if comment:
        alert.resolution_comment = comment
    await db.flush()
    return alert


async def resolve_alert(db: AsyncSession, alert: Alert, admin_id: UUID, comment: str | None = None) -> Alert:
    alert.status = AlertStatus.resolved
    alert.acknowledged_at = datetime.now(timezone.utc)
    alert.acknowledged_by = admin_id
    alert.resolution_comment = comment
    await db.flush()
    return alert


async def mark_false_positive(db: AsyncSession, alert: Alert, admin_id: UUID, comment: str | None = None) -> Alert:
    alert.status = AlertStatus.false_positive
    alert.acknowledged_at = datetime.now(timezone.utc)
    alert.acknowledged_by = admin_id
    alert.resolution_comment = comment
    await db.flush()
    return alert
