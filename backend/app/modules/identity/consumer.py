"""Identity consumer — обрабатывает события из топика hr.events."""
import uuid

import structlog
from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.kafka.consumer import consume_topic
from app.kafka.events import KafkaEvent
from app.kafka.topics import TOPIC_HR_EVENTS
from app.models.identity import UserExt

logger = structlog.get_logger()


async def handle_hr_event(event: KafkaEvent) -> None:
    payload = event.payload
    event_type = event.event_type
    employee_id = payload.get("employee_id", "")
    correlation_id = event.correlation_id

    async with AsyncSessionLocal() as db:
        try:
            if event_type == "hire":
                await _handle_hire(db, employee_id, payload, correlation_id)
            elif event_type == "transfer":
                await _handle_transfer(db, employee_id, payload, correlation_id)
            elif event_type in ("leave_start", "leave_end", "terminate"):
                await _handle_simple_status(db, employee_id, event_type, correlation_id)
            else:
                logger.warning("unknown_hr_event_type", event_type=event_type)
                return
            await db.commit()  # commit здесь, т.к. сервис только делает flush
        except Exception as exc:
            await db.rollback()
            logger.error("hr_event_processing_failed", event_type=event_type, employee_id=employee_id, error=str(exc))
            raise


async def _get_user(db, employee_id: str):
    result = await db.execute(select(UserExt).where(UserExt.employee_id == employee_id))
    return result.scalar_one_or_none()


async def _handle_hire(db, employee_id: str, payload: dict, correlation_id: uuid.UUID) -> None:
    from app.modules.identity.service import create_user

    existing = await _get_user(db, employee_id)
    if existing:
        logger.info("hire_skipped_user_exists", employee_id=employee_id)
        return

    email = payload.get("email", f"{employee_id.lower().replace('-', '_')}@accessguard.local")
    username = email.split("@")[0].replace(".", "_")[:50]

    await create_user(
        db=db,
        employee_id=employee_id,
        username=username,
        email=email,
        full_name=payload.get("full_name", employee_id),
        position_code=payload.get("position_code"),
        department_code=payload.get("department_code"),
        correlation_id=correlation_id,
    )


async def _handle_transfer(db, employee_id: str, payload: dict, correlation_id: uuid.UUID) -> None:
    from app.modules.identity.service import transfer_user

    user = await _get_user(db, employee_id)
    if not user:
        logger.warning("transfer_user_not_found", employee_id=employee_id)
        return
    await transfer_user(db=db, user=user, position_code=payload.get("position_code"),
                        department_code=payload.get("department_code"), correlation_id=correlation_id)


async def _handle_simple_status(db, employee_id: str, action: str, correlation_id: uuid.UUID) -> None:
    from app.modules.identity import service as svc

    user = await _get_user(db, employee_id)
    if not user:
        logger.warning("status_change_user_not_found", employee_id=employee_id, action=action)
        return
    if action == "leave_start":
        await svc.suspend_user(db, user, correlation_id)
    elif action == "leave_end":
        await svc.restore_user(db, user, correlation_id)
    elif action == "terminate":
        await svc.block_user(db, user, correlation_id)


async def run_hr_consumer() -> None:
    logger.info("hr_consumer_starting")
    await consume_topic(TOPIC_HR_EVENTS, "identity-hr", handle_hr_event)
