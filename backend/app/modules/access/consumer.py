"""Access module Kafka consumer — reacts to identity.users events."""
import structlog
from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.kafka.consumer import consume_topic
from app.kafka.events import KafkaEvent
from app.kafka.topics import TOPIC_IDENTITY_USERS
from app.models.access import ProcessedEvent
from app.models.identity import UserExt

logger = structlog.get_logger()

_GROUP_ID = "access.identity-users"


async def handle_identity_user_event(event: KafkaEvent) -> None:
    async with AsyncSessionLocal() as db:
        try:
            # Idempotency check
            already = (await db.execute(
                select(ProcessedEvent).where(
                    ProcessedEvent.event_id == event.event_id,
                    ProcessedEvent.consumer_group == _GROUP_ID,
                )
            )).scalar_one_or_none()
            if already:
                logger.debug("access_event_already_processed", event_id=str(event.event_id))
                return

            payload = event.payload
            user_id_str = payload.get("user_id")
            if not user_id_str:
                return

            from uuid import UUID
            user_id = UUID(user_id_str)

            if event.event_type == "user.created":
                await _on_user_created(db, user_id, payload)
            elif event.event_type == "user.updated":
                await _on_user_updated(db, user_id, payload)
            elif event.event_type == "user.blocked":
                await _on_user_blocked(db, user_id)

            db.add(ProcessedEvent(event_id=event.event_id, consumer_group=_GROUP_ID))
            await db.commit()
        except Exception as exc:
            await db.rollback()
            logger.error(
                "access_consumer_error",
                event_type=event.event_type,
                event_id=str(event.event_id),
                error=str(exc),
                exc_info=True,
            )
            raise


async def _on_user_created(db, user_id, payload) -> None:
    from app.modules.access.service import assign_default_roles_for_position

    user = (await db.execute(
        select(UserExt).where(UserExt.id == user_id)
    )).scalar_one_or_none()
    if not user or not user.position_id:
        return

    assigned = await assign_default_roles_for_position(db, user_id, user.position_id)
    logger.info(
        "access_default_roles_assigned",
        user_id=str(user_id),
        count=len(assigned),
    )


async def _on_user_updated(db, user_id, payload) -> None:
    from app.modules.access.service import (
        assign_default_roles_for_position,
        revoke_all_user_roles,
    )

    old_position_id = payload.get("old_position_id")
    new_position_id = payload.get("new_position_id")
    if not old_position_id or not new_position_id or old_position_id == new_position_id:
        return

    from uuid import UUID
    # Revoke all and re-assign defaults for new position
    await revoke_all_user_roles(db, user_id)
    await assign_default_roles_for_position(db, user_id, UUID(new_position_id))
    logger.info("access_roles_updated_on_transfer", user_id=str(user_id))


async def _on_user_blocked(db, user_id) -> None:
    from app.modules.access.service import revoke_all_user_roles

    count = await revoke_all_user_roles(db, user_id)
    logger.info("access_roles_revoked_on_block", user_id=str(user_id), count=count)


async def run_identity_user_consumer() -> None:
    await consume_topic(TOPIC_IDENTITY_USERS, _GROUP_ID, handle_identity_user_event)
