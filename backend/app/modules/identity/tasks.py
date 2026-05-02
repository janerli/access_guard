"""Identity Celery tasks."""
import asyncio
from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import select

from app.celery_app import celery_app
from app.database import AsyncSessionLocal
from app.models.identity import UserExt, UserStatus

logger = structlog.get_logger()

_BLOCKED_DELETE_DAYS = 90


@celery_app.task(name="identity.cleanup_blocked_users")
def cleanup_blocked_users():
    """Переводит пользователей, пробывших в blocked > 90 дней, в deleted."""
    asyncio.run(_cleanup_blocked_users_async())


async def _cleanup_blocked_users_async():
    from app.modules.identity.service import delete_user

    cutoff = datetime.now(timezone.utc) - timedelta(days=_BLOCKED_DELETE_DAYS)
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(UserExt).where(
                UserExt.status == UserStatus.blocked,
                UserExt.updated_at < cutoff,
            )
        )
        users = result.scalars().all()
        for user in users:
            await delete_user(db, user)
            logger.info("user_auto_deleted", user_id=str(user.id), employee_id=user.employee_id)


@celery_app.task(name="identity.reconcile_with_hr")
def reconcile_with_hr():
    """Сверяет активных сотрудников с HR-mock."""
    asyncio.run(_reconcile_async())


async def _reconcile_async():
    import httpx
    from app.config import settings
    from app.modules.identity.service import create_user

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(f"{settings.HR_MOCK_URL}/employees", timeout=10)
            hr_employees = resp.json()
        except Exception as exc:
            logger.error("hr_reconcile_fetch_failed", error=str(exc))
            return

    async with AsyncSessionLocal() as db:
        for emp in hr_employees:
            if emp.get("status") != "active":
                continue
            result = await db.execute(
                select(UserExt).where(UserExt.employee_id == emp["employee_id"])
            )
            existing = result.scalar_one_or_none()
            if not existing:
                email = emp.get("email", f"{emp['employee_id']}@accessguard.local")
                await create_user(
                    db=db,
                    employee_id=emp["employee_id"],
                    username=email.split("@")[0].replace(".", "_")[:50],
                    email=email,
                    full_name=emp.get("full_name", emp["employee_id"]),
                    position_code=emp.get("position_code"),
                    department_code=emp.get("department_code"),
                )
                logger.info("hr_reconcile_user_created", employee_id=emp["employee_id"])
