"""Celery tasks for Monitor module."""
import logging
from datetime import datetime, timezone

import structlog

from app.celery_app import celery_app

logger = structlog.get_logger()


@celery_app.task(name="monitor.publish_outbox")
def publish_outbox() -> dict:
    """Read pending outbox events and publish to Kafka."""
    import asyncio
    return asyncio.run(_publish_outbox_async())


async def _publish_outbox_async() -> dict:
    from sqlalchemy import select, update as sa_update
    from app.database import TaskAsyncSessionLocal
    from app.kafka.producer import publish_event
    from app.kafka.events import KafkaEvent
    from app.models.monitor import OutboxEvent, OutboxStatus

    published = 0
    failed = 0
    async with TaskAsyncSessionLocal() as db:
        try:
            rows = (await db.execute(
                select(OutboxEvent)
                .where(OutboxEvent.status == OutboxStatus.pending)
                .limit(100)
                .with_for_update(skip_locked=True)
            )).scalars().all()

            for row in rows:
                row_id = row.id
                audit_log_id = row.audit_log_id
                current_attempts = row.attempts or 0

                sp = await db.begin_nested()
                try:
                    event = KafkaEvent(
                        event_type="audit.event",
                        producer="monitor",
                        payload=row.payload,
                    )
                    await publish_event(row.topic, event)
                    await db.execute(
                        sa_update(OutboxEvent)
                        .where(OutboxEvent.id == row_id)
                        .values(status=OutboxStatus.published, published_at=datetime.now(timezone.utc))
                    )
                    await sp.commit()
                    published += 1
                except Exception as exc:
                    await sp.rollback()
                    new_attempts = current_attempts + 1
                    sp2 = await db.begin_nested()
                    try:
                        values: dict = {"attempts": new_attempts}
                        if new_attempts >= 3:
                            values["status"] = OutboxStatus.failed
                        await db.execute(
                            sa_update(OutboxEvent)
                            .where(OutboxEvent.id == row_id)
                            .values(**values)
                        )
                        await sp2.commit()
                    except Exception:
                        await sp2.rollback()
                    failed += 1
                    logger.warning("outbox_publish_failed", outbox_id=str(row_id), error=str(exc))

            await db.commit()
        except Exception:
            await db.rollback()
            raise

    return {"published": published, "failed": failed}


@celery_app.task(name="monitor.evaluate_simple_rules")
def evaluate_simple_rules(audit_log_id: int) -> dict:
    """Evaluate postgres-based rules against a newly written audit entry."""
    import asyncio
    return asyncio.run(_evaluate_simple_async(audit_log_id))


async def _evaluate_simple_async(audit_log_id: int) -> dict:
    from sqlalchemy import select
    from app.database import TaskAsyncSessionLocal
    from app.models.monitor import AuditLog, AlertRule, AlertDataSource
    from app.modules.monitor import alert_service
    from app.modules.monitor.rules import SIMPLE_RULES

    fired = 0
    async with TaskAsyncSessionLocal() as db:
        try:
            entry = (await db.execute(
                select(AuditLog).where(AuditLog.id == audit_log_id)
            )).scalar_one_or_none()
            if not entry:
                return {"fired": 0}

            rules = (await db.execute(
                select(AlertRule).where(
                    AlertRule.is_enabled == True,  # noqa: E712
                    AlertRule.data_source == AlertDataSource.postgres,
                )
            )).scalars().all()

            for rule in rules:
                checker = SIMPLE_RULES.get(rule.code)
                if not checker:
                    continue
                try:
                    match = await checker(db, rule.condition_config, entry)
                    if match.matched:
                        alert = await alert_service.fire_alert(
                            db,
                            rule,
                            subject_user_id=match.subject_user_id,
                            details=match.details,
                            correlation_id=entry.correlation_id,
                        )
                        if alert:
                            fired += 1
                except Exception as exc:
                    logger.warning("simple_rule_failed", rule=rule.code, error=str(exc))

            await db.commit()
        except Exception:
            await db.rollback()
            raise

    return {"fired": fired}


@celery_app.task(name="monitor.evaluate_complex_rules")
def evaluate_complex_rules() -> dict:
    """Evaluate elasticsearch-based rules (runs periodically)."""
    import asyncio
    return asyncio.run(_evaluate_complex_async())


async def _evaluate_complex_async() -> dict:
    from sqlalchemy import select
    from app.database import TaskAsyncSessionLocal
    from app.elastic.client import get_elastic_client as get_es_client
    from app.models.monitor import AlertRule, AlertDataSource
    from app.modules.monitor import alert_service
    from app.modules.monitor.rules import COMPLEX_RULES

    fired = 0
    async with TaskAsyncSessionLocal() as db:
        try:
            rules = (await db.execute(
                select(AlertRule).where(
                    AlertRule.is_enabled == True,  # noqa: E712
                    AlertRule.data_source == AlertDataSource.elasticsearch,
                )
            )).scalars().all()

            es = get_es_client()
            for rule in rules:
                checker = COMPLEX_RULES.get(rule.code)
                if not checker:
                    continue
                try:
                    matches = await checker(es, rule.condition_config)
                    for match in matches:
                        if match.matched:
                            alert = await alert_service.fire_alert(
                                db,
                                rule,
                                subject_user_id=match.subject_user_id,
                                details=match.details,
                            )
                            if alert:
                                fired += 1
                except Exception as exc:
                    logger.warning("complex_rule_failed", rule=rule.code, error=str(exc))

            await db.commit()
        except Exception:
            await db.rollback()
            raise

    return {"fired": fired}
