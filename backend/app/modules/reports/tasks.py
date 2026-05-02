"""Celery tasks for Reports module."""
import logging
import os
from datetime import datetime, timezone

import structlog

from app.celery_app import celery_app

logger = structlog.get_logger()
REPORTS_DIR = os.environ.get("REPORTS_DIR", "/tmp/reports")


@celery_app.task(name="reports.generate_report")
def generate_report(report_id: str) -> dict:
    import asyncio
    return asyncio.get_event_loop().run_until_complete(_generate_async(report_id))


async def _generate_async(report_id: str) -> dict:
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from app.database import AsyncSessionLocal
    from app.elastic.client import get_elastic_client
    from app.models.reports import Report, ReportStatus, ReportTemplate
    from app.modules.reports.generators.base import GENERATORS

    os.makedirs(REPORTS_DIR, exist_ok=True)

    async with AsyncSessionLocal() as db:
        try:
            report = (await db.execute(
                select(Report).options(selectinload(Report.template)).where(Report.id == report_id)
            )).scalar_one_or_none()

            if not report:
                return {"error": "Report not found"}

            report.status = ReportStatus.generating
            await db.commit()

            template = report.template
            generator = GENERATORS.get(template.code)
            if not generator:
                report.status = ReportStatus.failed
                report.error_message = f"No generator for template: {template.code}"
                await db.commit()
                return {"error": report.error_message}

            es = get_elastic_client()
            content = await generator.generate(db, es, report.parameters, report.format)

            ext = report.format.value
            file_path = os.path.join(REPORTS_DIR, f"{report_id}.{ext}")
            with open(file_path, "wb") as f:
                f.write(content)

            report.status = ReportStatus.ready
            report.completed_at = datetime.now(timezone.utc)
            report.file_path = file_path
            report.file_size = len(content)
            await db.commit()

            # Publish notification
            try:
                from app.kafka.events import KafkaEvent
                from app.kafka.producer import publish_event
                from app.kafka.topics import TOPIC_REPORTS_NOTIFICATIONS
                event = KafkaEvent(
                    event_type="report.ready",
                    producer="reports",
                    payload={"report_id": report_id, "template_code": template.code, "format": ext},
                )
                await publish_event(TOPIC_REPORTS_NOTIFICATIONS, event)
            except Exception as exc:
                logger.warning("report_notification_failed", error=str(exc))

            return {"report_id": report_id, "status": "ready", "file_size": len(content)}

        except Exception as exc:
            logger.error("report_generation_failed", report_id=report_id, error=str(exc))
            try:
                report.status = ReportStatus.failed
                report.error_message = str(exc)[:500]
                report.completed_at = datetime.now(timezone.utc)
                await db.commit()
            except Exception:
                await db.rollback()
            return {"error": str(exc)}


@celery_app.task(name="reports.check_schedules")
def check_report_schedules() -> dict:
    import asyncio
    return asyncio.get_event_loop().run_until_complete(_check_schedules_async())


async def _check_schedules_async() -> dict:
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from app.database import AsyncSessionLocal
    from app.models.reports import Report, ReportSchedule, ReportStatus

    triggered = 0
    async with AsyncSessionLocal() as db:
        try:
            schedules = (await db.execute(
                select(ReportSchedule)
                .options(selectinload(ReportSchedule.template))
                .where(ReportSchedule.is_enabled == True)  # noqa: E712
            )).scalars().all()

            now = datetime.now(timezone.utc)
            for schedule in schedules:
                if _should_run(schedule.cron_expression, schedule.last_run_at, now):
                    report = Report(
                        template_id=schedule.template_id,
                        parameters=schedule.parameters,
                        format=schedule.format,
                        status=ReportStatus.pending,
                    )
                    db.add(report)
                    await db.flush()
                    schedule.last_run_at = now
                    generate_report.delay(str(report.id))
                    triggered += 1

            await db.commit()
        except Exception:
            await db.rollback()
            raise

    return {"triggered": triggered}


def _should_run(cron_expr: str, last_run: datetime | None, now: datetime) -> bool:
    """Simple cron check: supports @daily, @weekly, @hourly, and HH:MM daily schedules."""
    from datetime import timedelta

    if not last_run:
        return True

    if cron_expr == "@hourly":
        return (now - last_run) >= timedelta(hours=1)
    if cron_expr in ("@daily", "@midnight"):
        return (now - last_run) >= timedelta(days=1)
    if cron_expr == "@weekly":
        return (now - last_run) >= timedelta(weeks=1)

    # Format "HH:MM" — run once per day at specified time
    try:
        hh, mm = cron_expr.split(":")
        target_hour, target_minute = int(hh), int(mm)
        # Check if it's the right time and hasn't run today
        if now.hour == target_hour and now.minute == target_minute:
            return last_run.date() < now.date()
    except ValueError:
        pass

    return False
