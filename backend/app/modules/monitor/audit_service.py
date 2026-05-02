"""audit_service — transactional outbox pattern for audit logging."""
from datetime import timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.kafka.topics import TOPIC_AUDIT_EVENTS
from app.models.monitor import (
    AuditLog,
    AuditModule,
    AuditOperation,
    AuditResult,
    AuditTargetType,
    OutboxEvent,
)


async def log(
    db: AsyncSession,
    *,
    operation: AuditOperation,
    module: AuditModule,
    target_type: AuditTargetType,
    target_id: str = "",
    result: AuditResult = AuditResult.success,
    actor_id: UUID | None = None,
    actor_username: str = "",
    ip_address: str | None = None,
    user_agent: str | None = None,
    details: dict | None = None,
    correlation_id: UUID | None = None,
) -> AuditLog:
    """Write audit entry + outbox event in the current transaction (flush-only)."""
    entry = AuditLog(
        operation=operation,
        module=module,
        target_type=target_type,
        target_id=target_id,
        result=result,
        actor_id=actor_id,
        actor_username=actor_username,
        ip_address=ip_address,
        user_agent=user_agent[:500] if user_agent else None,
        details=details,
        correlation_id=correlation_id,
    )
    db.add(entry)
    await db.flush()

    payload = {
        "event_id": str(entry.event_id),
        "audit_log_id": entry.id,
        "timestamp": entry.timestamp.isoformat() if entry.timestamp else None,
        "actor_id": str(actor_id) if actor_id else None,
        "actor_username": actor_username,
        "target_type": target_type.value,
        "target_id": target_id,
        "operation": operation.value,
        "module": module.value,
        "result": result.value,
        "ip_address": ip_address,
        "details": details or {},
        "correlation_id": str(correlation_id) if correlation_id else None,
    }
    outbox = OutboxEvent(
        audit_log_id=entry.id,
        topic=TOPIC_AUDIT_EVENTS,
        payload=payload,
    )
    db.add(outbox)
    await db.flush()
    return entry
