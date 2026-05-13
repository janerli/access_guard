"""Identity service — бизнес-логика управления учётными записями.

Соглашение: сервис вызывает только flush() для получения ID.
Commit выполняется вызывающей стороной:
  - get_db() в роутере (автоматически)
  - consumer (явно после вызова сервиса)
"""
import uuid
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

import structlog
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.kafka.events import KafkaEvent
from app.kafka.producer import publish_event
from app.kafka.topics import TOPIC_IDENTITY_LIFECYCLE, TOPIC_IDENTITY_USERS
from app.models.identity import (
    Department,
    LifecycleEvent,
    LifecycleEventSource,
    LifecycleEventStatus,
    LifecycleEventType,
    Position,
    UserExt,
    UserStatus,
)

logger = structlog.get_logger()


async def _prepare_user_response(db: AsyncSession, user: UserExt) -> UserExt:
    await db.refresh(user, attribute_names=["created_at", "updated_at", "position", "department"])
    return user


async def _get_position(db: AsyncSession, code: str) -> Optional[Position]:
    result = await db.execute(select(Position).where(Position.code == code))
    return result.scalar_one_or_none()


async def _get_department(db: AsyncSession, code: str) -> Optional[Department]:
    result = await db.execute(select(Department).where(Department.code == code))
    return result.scalar_one_or_none()


async def _publish_user_event(event_type: str, user: UserExt, correlation_id: UUID) -> None:
    try:
        await publish_event(
            TOPIC_IDENTITY_USERS,
            KafkaEvent(
                event_type=event_type,
                producer="identity",
                correlation_id=correlation_id,
                payload={
                    "user_id": str(user.id),
                    "employee_id": user.employee_id,
                    "username": user.username,
                    "email": user.email,
                    "full_name": user.full_name,
                    "status": user.status.value,
                    "position_id": str(user.position_id) if user.position_id else None,
                    "department_id": str(user.department_id) if user.department_id else None,
                },
            ),
            key=str(user.id),
        )
    except Exception as exc:
        logger.warning("kafka_publish_failed", topic=TOPIC_IDENTITY_USERS, error=str(exc))


async def _publish_lifecycle_event(event_type: str, user: UserExt, correlation_id: UUID) -> None:
    try:
        await publish_event(
            TOPIC_IDENTITY_LIFECYCLE,
            KafkaEvent(
                event_type=event_type,
                producer="identity",
                correlation_id=correlation_id,
                payload={"user_id": str(user.id), "employee_id": user.employee_id},
            ),
            key=str(user.id),
        )
    except Exception as exc:
        logger.warning("kafka_publish_failed", topic=TOPIC_IDENTITY_LIFECYCLE, error=str(exc))


async def create_user(
    db: AsyncSession,
    employee_id: str,
    username: str,
    email: str,
    full_name: str,
    position_code: Optional[str] = None,
    department_code: Optional[str] = None,
    correlation_id: Optional[UUID] = None,
) -> UserExt:
    position = await _get_position(db, position_code) if position_code else None
    department = await _get_department(db, department_code) if department_code else None

    user = UserExt(
        id=uuid.uuid4(),
        employee_id=employee_id,
        username=username,
        email=email,
        full_name=full_name,
        position_id=position.id if position else None,
        department_id=department.id if department else None,
        status=UserStatus.active,
    )
    db.add(user)
    await db.flush()  # get user.id

    lifecycle = LifecycleEvent(
        id=uuid.uuid4(),
        user_id=user.id,
        event_type=LifecycleEventType.hire,
        source=LifecycleEventSource.hr_system,
        payload={"employee_id": employee_id, "email": email, "full_name": full_name},
        status=LifecycleEventStatus.processed,
        processed_at=datetime.now(timezone.utc),
    )
    db.add(lifecycle)
    await db.flush()

    # Best-effort LDAP
    try:
        from app.core.ldap_client import ldap_create_user
        ldap_dn = ldap_create_user(user.username, user.full_name, user.email, department_code)
        user.ldap_dn = ldap_dn
        await db.flush()
    except Exception as exc:
        logger.warning("ldap_create_failed", employee_id=employee_id, error=str(exc))

    # Publish after flush — commit happens upstream (get_db or consumer)
    corr = correlation_id or uuid.uuid4()
    await _publish_user_event("user.created", user, corr)
    await _publish_lifecycle_event("lifecycle.hired", user, corr)

    logger.info("user_created", user_id=str(user.id), employee_id=employee_id)
    return await _prepare_user_response(db, user)


async def update_user(
    db: AsyncSession,
    user: UserExt,
    email: Optional[str] = None,
    full_name: Optional[str] = None,
    position_code: Optional[str] = None,
    department_code: Optional[str] = None,
    correlation_id: Optional[UUID] = None,
) -> UserExt:
    if email:
        user.email = email
    if full_name:
        user.full_name = full_name
    if position_code:
        position = await _get_position(db, position_code)
        if position:
            user.position_id = position.id
    if department_code:
        department = await _get_department(db, department_code)
        if department:
            user.department_id = department.id
    await db.flush()

    if user.ldap_dn:
        try:
            from app.core.ldap_client import ldap_modify_user
            ldap_modify_user(user.ldap_dn, cn=full_name, mail=email)
        except Exception as exc:
            logger.warning("ldap_modify_failed", error=str(exc))

    await _publish_user_event("user.updated", user, correlation_id or uuid.uuid4())
    return await _prepare_user_response(db, user)


async def _change_status(
    db: AsyncSession,
    user: UserExt,
    new_status: UserStatus,
    lifecycle_type: LifecycleEventType,
    kafka_event_type: str,
    source: LifecycleEventSource = LifecycleEventSource.manual,
    correlation_id: Optional[UUID] = None,
) -> UserExt:
    user.status = new_status

    lifecycle = LifecycleEvent(
        id=uuid.uuid4(),
        user_id=user.id,
        event_type=lifecycle_type,
        source=source,
        payload={"user_id": str(user.id)},
        status=LifecycleEventStatus.processed,
        processed_at=datetime.now(timezone.utc),
    )
    db.add(lifecycle)
    await db.flush()

    if new_status == UserStatus.blocked and user.ldap_dn:
        try:
            from app.core.ldap_client import ldap_block_user
            ldap_block_user(user.ldap_dn)
        except Exception as exc:
            logger.warning("ldap_block_failed", error=str(exc))
    elif new_status == UserStatus.deleted and user.ldap_dn:
        try:
            from app.core.ldap_client import ldap_delete_user
            ldap_delete_user(user.ldap_dn)
        except Exception as exc:
            logger.warning("ldap_delete_failed", error=str(exc))

    corr = correlation_id or uuid.uuid4()
    await _publish_user_event(kafka_event_type, user, corr)

    lc_map = {
        LifecycleEventType.terminate: "lifecycle.terminated",
        LifecycleEventType.leave_start: "lifecycle.transferred",
        LifecycleEventType.leave_end: "lifecycle.transferred",
    }
    if lifecycle_type in lc_map:
        await _publish_lifecycle_event(lc_map[lifecycle_type], user, corr)

    return await _prepare_user_response(db, user)


async def suspend_user(db: AsyncSession, user: UserExt, correlation_id: Optional[UUID] = None) -> UserExt:
    return await _change_status(db, user, UserStatus.suspended, LifecycleEventType.leave_start, "user.suspended", correlation_id=correlation_id)


async def restore_user(db: AsyncSession, user: UserExt, correlation_id: Optional[UUID] = None) -> UserExt:
    return await _change_status(db, user, UserStatus.active, LifecycleEventType.leave_end, "user.restored", correlation_id=correlation_id)


async def block_user(db: AsyncSession, user: UserExt, correlation_id: Optional[UUID] = None) -> UserExt:
    return await _change_status(db, user, UserStatus.blocked, LifecycleEventType.terminate, "user.blocked", correlation_id=correlation_id)


async def delete_user(db: AsyncSession, user: UserExt, correlation_id: Optional[UUID] = None) -> UserExt:
    return await _change_status(
        db, user, UserStatus.deleted, LifecycleEventType.terminate, "user.deleted",
        source=LifecycleEventSource.scheduled, correlation_id=correlation_id,
    )


async def transfer_user(
    db: AsyncSession,
    user: UserExt,
    position_code: Optional[str] = None,
    department_code: Optional[str] = None,
    correlation_id: Optional[UUID] = None,
) -> UserExt:
    if position_code:
        pos = await _get_position(db, position_code)
        if pos:
            user.position_id = pos.id
    if department_code:
        dept = await _get_department(db, department_code)
        if dept:
            user.department_id = dept.id

    lifecycle = LifecycleEvent(
        id=uuid.uuid4(),
        user_id=user.id,
        event_type=LifecycleEventType.transfer,
        source=LifecycleEventSource.hr_system,
        payload={"user_id": str(user.id), "position_code": position_code, "department_code": department_code},
        status=LifecycleEventStatus.processed,
        processed_at=datetime.now(timezone.utc),
    )
    db.add(lifecycle)
    await db.flush()

    corr = correlation_id or uuid.uuid4()
    await _publish_user_event("user.updated", user, corr)
    await _publish_lifecycle_event("lifecycle.transferred", user, corr)
    return user


async def reset_password(db: AsyncSession, user: UserExt, new_password: str) -> None:
    if user.ldap_dn:
        try:
            from app.core.ldap_client import ldap_reset_password
            ldap_reset_password(user.ldap_dn, new_password)
        except Exception as exc:
            logger.warning("ldap_reset_password_failed", error=str(exc))
    logger.info("password_reset", user_id=str(user.id))


async def list_users(
    db: AsyncSession,
    status: Optional[UserStatus] = None,
    department_id: Optional[UUID] = None,
    position_id: Optional[UUID] = None,
    search: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[UserExt], int]:
    query = select(UserExt).where(UserExt.status != UserStatus.deleted)
    if status:
        query = query.where(UserExt.status == status)
    if department_id:
        query = query.where(UserExt.department_id == department_id)
    if position_id:
        query = query.where(UserExt.position_id == position_id)
    if search:
        like = f"%{search}%"
        query = query.where(
            or_(UserExt.full_name.ilike(like), UserExt.username.ilike(like),
                UserExt.email.ilike(like), UserExt.employee_id.ilike(like))
        )

    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar_one()
    query = query.offset((page - 1) * page_size).limit(page_size).order_by(UserExt.full_name)
    result = await db.execute(query)
    return list(result.scalars().all()), total


async def list_lifecycle_events(
    db: AsyncSession,
    user_id: Optional[UUID] = None,
    event_type: Optional[LifecycleEventType] = None,
    status: Optional[LifecycleEventStatus] = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[LifecycleEvent], int]:
    query = select(LifecycleEvent)
    if user_id:
        query = query.where(LifecycleEvent.user_id == user_id)
    if event_type:
        query = query.where(LifecycleEvent.event_type == event_type)
    if status:
        query = query.where(LifecycleEvent.status == status)

    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar_one()
    query = query.offset((page - 1) * page_size).limit(page_size).order_by(LifecycleEvent.created_at.desc())
    result = await db.execute(query)
    return list(result.scalars().all()), total
