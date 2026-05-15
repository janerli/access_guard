"""Access module service — RBAC, Redis permission cache, access requests."""
import json
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

import structlog
from redis.asyncio import Redis as AsyncRedis
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.models.access import (
    AccessRequest,
    AccessRequestStatus,
    Permission,
    PositionRoleDefault,
    Role,
    RolePermission,
    UserRole,
)
from app.models.identity import Position

logger = structlog.get_logger()

_PERM_CACHE_TTL = 60  # seconds


def _perm_cache_key(user_id: UUID) -> str:
    return f"perms:{user_id}"


async def _get_redis() -> AsyncRedis:
    return AsyncRedis.from_url(settings.REDIS_URL, decode_responses=True)


# ── Permission check (cached) ──────────────────────────────────────────────────

async def check_user_permission(user_id: UUID, permission_code: str) -> bool:
    redis = await _get_redis()
    try:
        cached = await redis.get(_perm_cache_key(user_id))
        if cached is not None:
            perms: list[str] = json.loads(cached)
            return permission_code in perms
    except Exception as exc:
        logger.warning("redis_get_failed", error=str(exc))
    finally:
        await redis.aclose()

    # Fallback: load from DB (no session available here — callers should use has_permission)
    return False


async def get_user_permissions(db: AsyncSession, user_id: UUID) -> list[str]:
    """Load all permission codes for a user via their active roles."""
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(Permission.code)
        .join(RolePermission, RolePermission.permission_id == Permission.id)
        .join(UserRole, UserRole.role_id == RolePermission.role_id)
        .where(
            UserRole.user_id == user_id,
            (UserRole.expires_at == None) | (UserRole.expires_at > now),  # noqa: E711
        )
        .distinct()
    )
    return list(result.scalars().all())


async def has_permission(db: AsyncSession, user_id: UUID, permission_code: str) -> bool:
    """Check permission with Redis cache; fallback to DB."""
    redis = await _get_redis()
    try:
        cached = await redis.get(_perm_cache_key(user_id))
        if cached is not None:
            perms: list[str] = json.loads(cached)
            return permission_code in perms

        perms = await get_user_permissions(db, user_id)
        await redis.setex(_perm_cache_key(user_id), _PERM_CACHE_TTL, json.dumps(perms))
        return permission_code in perms
    except Exception as exc:
        logger.warning("permission_check_cache_error", error=str(exc))
        perms = await get_user_permissions(db, user_id)
        return permission_code in perms
    finally:
        await redis.aclose()


async def invalidate_permission_cache(user_id: UUID) -> None:
    redis = await _get_redis()
    try:
        await redis.delete(_perm_cache_key(user_id))
    except Exception as exc:
        logger.warning("redis_delete_failed", error=str(exc))
    finally:
        await redis.aclose()


# ── Roles ──────────────────────────────────────────────────────────────────────

async def list_roles(
    db: AsyncSession,
    search: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[Role], int]:
    q = select(Role)
    if search:
        q = q.where(Role.name.ilike(f"%{search}%") | Role.code.ilike(f"%{search}%"))
    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar_one()
    result = await db.execute(q.order_by(Role.name).offset((page - 1) * page_size).limit(page_size))
    return list(result.scalars().all()), total


async def get_role(db: AsyncSession, role_id: UUID) -> Optional[Role]:
    result = await db.execute(
        select(Role).options(selectinload(Role.role_permissions).selectinload(RolePermission.permission))
        .where(Role.id == role_id)
    )
    return result.scalar_one_or_none()


async def create_role(
    db: AsyncSession,
    code: str,
    name: str,
    description: str = "",
    is_privileged: bool = False,
) -> Role:
    role = Role(code=code, name=name, description=description, is_privileged=is_privileged)
    db.add(role)
    await db.flush()
    return role


async def update_role(
    db: AsyncSession,
    role: Role,
    name: Optional[str] = None,
    description: Optional[str] = None,
    is_privileged: Optional[bool] = None,
) -> Role:
    if name is not None:
        role.name = name
    if description is not None:
        role.description = description
    if is_privileged is not None:
        role.is_privileged = is_privileged
    await db.flush()
    return role


async def delete_role(db: AsyncSession, role: Role) -> None:
    await db.delete(role)
    await db.flush()


async def add_permission_to_role(db: AsyncSession, role_id: UUID, permission_id: UUID) -> None:
    existing = (await db.execute(
        select(RolePermission).where(
            RolePermission.role_id == role_id,
            RolePermission.permission_id == permission_id,
        )
    )).scalar_one_or_none()
    if not existing:
        db.add(RolePermission(role_id=role_id, permission_id=permission_id))
        await db.flush()


async def remove_permission_from_role(db: AsyncSession, role_id: UUID, permission_id: UUID) -> None:
    await db.execute(
        delete(RolePermission).where(
            RolePermission.role_id == role_id,
            RolePermission.permission_id == permission_id,
        )
    )
    await db.flush()


# ── User Roles ─────────────────────────────────────────────────────────────────

async def list_user_roles(db: AsyncSession, user_id: UUID) -> list[UserRole]:
    result = await db.execute(
        select(UserRole).options(selectinload(UserRole.role))
        .where(UserRole.user_id == user_id)
        .order_by(UserRole.granted_at.desc())
    )
    return list(result.scalars().all())


async def _write_role_audit(
    db: AsyncSession,
    actor_id: Optional[UUID],
    actor_username: str,
    user_id: UUID,
    role: Role,
    operation: str,
) -> int:
    from app.models.monitor import (
        AuditLog, AuditModule, AuditOperation, AuditResult,
        AuditTargetType, OutboxEvent, OutboxStatus,
    )
    import uuid as _uuid
    from app.kafka.topics import TOPIC_AUDIT_EVENTS

    corr = _uuid.uuid4()
    entry = AuditLog(
        event_id=_uuid.uuid4(),
        actor_id=None,  # actor is an admin (not in users_ext), actor_username captures identity
        actor_username=actor_username,
        target_type=AuditTargetType.role,
        target_id=str(user_id),
        operation=AuditOperation(operation),
        module=AuditModule.access,
        result=AuditResult.success,
        details={"role_code": role.code, "role_name": role.name, "is_privileged": role.is_privileged},
        correlation_id=corr,
        published_to_kafka=False,
    )
    db.add(entry)
    await db.flush()
    payload = {
        "event_id": str(entry.event_id), "audit_log_id": entry.id,
        "timestamp": entry.timestamp.isoformat() if entry.timestamp else datetime.now(timezone.utc).isoformat(),
        "actor_id": None,
        "actor_username": actor_username,
        "target_type": "role", "target_id": str(user_id),
        "operation": operation, "module": "access", "result": "success",
        "details": entry.details, "correlation_id": str(corr),
    }
    db.add(OutboxEvent(audit_log_id=entry.id, topic=TOPIC_AUDIT_EVENTS, payload=payload, status=OutboxStatus.pending))
    return entry.id


async def assign_role(
    db: AsyncSession,
    user_id: UUID,
    role_id: UUID,
    granted_by: Optional[UUID] = None,
    expires_at: Optional[datetime] = None,
    request_id: Optional[UUID] = None,
    actor_username: str = "system",
) -> UserRole:
    # Prevent duplicate active assignment
    now = datetime.now(timezone.utc)
    existing = (await db.execute(
        select(UserRole).where(
            UserRole.user_id == user_id,
            UserRole.role_id == role_id,
            (UserRole.expires_at == None) | (UserRole.expires_at > now),  # noqa: E711
        )
    )).scalar_one_or_none()
    if existing:
        return existing

    role = (await db.execute(select(Role).where(Role.id == role_id))).scalar_one()
    user_role = UserRole(
        user_id=user_id,
        role_id=role_id,
        granted_by=granted_by,
        expires_at=expires_at,
        request_id=request_id,
    )
    db.add(user_role)
    await db.flush()
    await invalidate_permission_cache(user_id)

    audit_id = await _write_role_audit(db, granted_by, actor_username, user_id, role, "role_assign")
    logger.info("role_audit_written", audit_id=audit_id, user_id=str(user_id), role_code=role.code, is_privileged=role.is_privileged)

    import asyncio

    async def _run_evaluate(audit_log_id: int) -> None:
        await asyncio.sleep(0.5)  # ensure transaction commits before querying
        try:
            from app.modules.monitor.tasks import _evaluate_simple_async
            result = await _evaluate_simple_async(audit_log_id)
            logger.info("evaluate_simple_rules_done", audit_log_id=audit_log_id, fired=result.get("fired", 0))
        except Exception as exc:
            logger.warning("evaluate_simple_rules_failed", audit_log_id=audit_log_id, error=str(exc))

    asyncio.ensure_future(_run_evaluate(audit_id))

    return user_role


async def revoke_role(db: AsyncSession, user_role_id: UUID) -> None:
    result = await db.execute(select(UserRole).where(UserRole.id == user_role_id))
    user_role = result.scalar_one_or_none()
    if user_role:
        user_id = user_role.user_id
        await db.delete(user_role)
        await db.flush()
        await invalidate_permission_cache(user_id)


async def revoke_all_user_roles(db: AsyncSession, user_id: UUID) -> int:
    result = await db.execute(select(UserRole).where(UserRole.user_id == user_id))
    roles = result.scalars().all()
    count = len(roles)
    for ur in roles:
        await db.delete(ur)
    if count:
        await db.flush()
        await invalidate_permission_cache(user_id)
    return count


async def assign_default_roles_for_position(
    db: AsyncSession,
    user_id: UUID,
    position_id: UUID,
    granted_by: Optional[UUID] = None,
) -> list[UserRole]:
    result = await db.execute(
        select(PositionRoleDefault).where(PositionRoleDefault.position_id == position_id)
    )
    defaults = result.scalars().all()
    assigned = []
    for prd in defaults:
        ur = await assign_role(db, user_id, prd.role_id, granted_by=granted_by)
        assigned.append(ur)
    return assigned


# ── Permissions list ───────────────────────────────────────────────────────────

async def list_permissions(db: AsyncSession) -> list[Permission]:
    result = await db.execute(select(Permission).order_by(Permission.code))
    return list(result.scalars().all())


# ── Access Requests ────────────────────────────────────────────────────────────

async def list_access_requests(
    db: AsyncSession,
    user_id: Optional[UUID] = None,
    status: Optional[AccessRequestStatus] = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[AccessRequest], int]:
    q = select(AccessRequest).options(selectinload(AccessRequest.role))
    if user_id:
        q = q.where(AccessRequest.user_id == user_id)
    if status:
        q = q.where(AccessRequest.status == status)
    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar_one()
    result = await db.execute(q.order_by(AccessRequest.created_at.desc()).offset((page - 1) * page_size).limit(page_size))
    return list(result.scalars().all()), total


async def get_access_request(db: AsyncSession, request_id: UUID) -> Optional[AccessRequest]:
    result = await db.execute(
        select(AccessRequest).options(selectinload(AccessRequest.role))
        .where(AccessRequest.id == request_id)
    )
    return result.scalar_one_or_none()


async def create_access_request(
    db: AsyncSession,
    user_id: UUID,
    role_id: UUID,
    justification: str,
) -> AccessRequest:
    req = AccessRequest(user_id=user_id, role_id=role_id, justification=justification)
    db.add(req)
    await db.flush()
    await db.refresh(req, ["role"])
    return req


async def approve_request(
    db: AsyncSession,
    request: AccessRequest,
    decided_by: UUID,
    comment: Optional[str] = None,
    actor_username: str = "system",
) -> AccessRequest:
    request.status = AccessRequestStatus.approved
    request.decided_at = datetime.now(timezone.utc)
    request.decided_by = decided_by
    request.decision_comment = comment
    await db.flush()

    user_role = await assign_role(
        db,
        user_id=request.user_id,
        role_id=request.role_id,
        granted_by=decided_by,
        request_id=request.id,
        actor_username=actor_username,
    )
    logger.info("access_request_approved", request_id=str(request.id), user_role_id=str(user_role.id))
    return request


async def reject_request(
    db: AsyncSession,
    request: AccessRequest,
    decided_by: UUID,
    comment: Optional[str] = None,
) -> AccessRequest:
    request.status = AccessRequestStatus.rejected
    request.decided_at = datetime.now(timezone.utc)
    request.decided_by = decided_by
    request.decision_comment = comment
    await db.flush()
    return request


async def withdraw_request(db: AsyncSession, request: AccessRequest) -> AccessRequest:
    request.status = AccessRequestStatus.withdrawn
    await db.flush()
    return request


# ── Permission Matrix ──────────────────────────────────────────────────────────

async def get_permission_matrix(db: AsyncSession) -> list[dict]:
    positions = (await db.execute(select(Position).order_by(Position.level, Position.name))).scalars().all()
    defaults_result = await db.execute(
        select(PositionRoleDefault).options(selectinload(PositionRoleDefault.role))
    )
    defaults = defaults_result.scalars().all()

    defaults_by_position: dict[UUID, list[PositionRoleDefault]] = {}
    for d in defaults:
        defaults_by_position.setdefault(d.position_id, []).append(d)

    matrix = []
    for pos in positions:
        pos_defaults = defaults_by_position.get(pos.id, [])
        matrix.append({
            "position_id": pos.id,
            "position_code": pos.code,
            "position_name": pos.name,
            "role_ids": [d.role_id for d in pos_defaults],
            "roles": [d.role for d in pos_defaults],
        })
    return matrix


async def update_position_defaults(
    db: AsyncSession,
    position_id: UUID,
    role_ids: list[UUID],
) -> None:
    await db.execute(
        delete(PositionRoleDefault).where(PositionRoleDefault.position_id == position_id)
    )
    for role_id in role_ids:
        db.add(PositionRoleDefault(position_id=position_id, role_id=role_id))
    await db.flush()
