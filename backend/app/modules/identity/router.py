from typing import Annotated, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentAdmin, require_roles
from app.database import get_db
from app.models.admin import AdminRole
from app.models.identity import (
    Department,
    LifecycleEventStatus,
    LifecycleEventType,
    Position,
    UserExt,
    UserStatus,
)
from app.modules.identity import service
from app.modules.identity.schemas import (
    DepartmentOut,
    DepartmentTreeOut,
    LifecycleEventOut,
    LifecycleEventsListResponse,
    PositionOut,
    UserExtCreate,
    UserExtOut,
    UserExtUpdate,
    UserResetPassword,
    UsersListResponse,
)

router = APIRouter()

_CAN_WRITE = [AdminRole.system_admin, AdminRole.hr_operator]
_CAN_READ = [AdminRole.system_admin, AdminRole.hr_operator, AdminRole.security_officer, AdminRole.auditor]


async def _get_user_or_404(db: AsyncSession, user_id: UUID) -> UserExt:
    result = await db.execute(select(UserExt).where(UserExt.id == user_id, UserExt.status != UserStatus.deleted))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Пользователь не найден")
    return user


# ── Users ─────────────────────────────────────────────────────────────────────

@router.post("/users", response_model=UserExtOut, status_code=201, dependencies=[Depends(require_roles(*_CAN_WRITE))])
async def create_user(
    body: UserExtCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    existing = (await db.execute(select(UserExt).where(UserExt.employee_id == body.employee_id))).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="Сотрудник с таким employee_id уже существует")

    user = await service.create_user(
        db=db,
        employee_id=body.employee_id,
        username=body.username,
        email=body.email,
        full_name=body.full_name,
        position_code=body.position_code,
        department_code=body.department_code,
    )
    return user


@router.get("/users", response_model=UsersListResponse, dependencies=[Depends(require_roles(*_CAN_READ))])
async def list_users(
    db: Annotated[AsyncSession, Depends(get_db)],
    status_filter: Optional[UserStatus] = Query(None, alias="status"),
    department_id: Optional[UUID] = None,
    position_id: Optional[UUID] = None,
    search: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    users, total = await service.list_users(
        db,
        status=status_filter,
        department_id=department_id,
        position_id=position_id,
        search=search,
        page=page,
        page_size=page_size,
    )
    return UsersListResponse(items=users, total=total, page=page, page_size=page_size)


@router.get("/users/{user_id}", response_model=UserExtOut, dependencies=[Depends(require_roles(*_CAN_READ))])
async def get_user(user_id: UUID, db: Annotated[AsyncSession, Depends(get_db)]):
    return await _get_user_or_404(db, user_id)


@router.patch("/users/{user_id}", response_model=UserExtOut, dependencies=[Depends(require_roles(*_CAN_WRITE))])
async def update_user(
    user_id: UUID,
    body: UserExtUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    user = await _get_user_or_404(db, user_id)
    return await service.update_user(
        db, user,
        email=body.email,
        full_name=body.full_name,
        position_code=body.position_code,
        department_code=body.department_code,
    )


@router.post("/users/{user_id}/suspend", response_model=UserExtOut, dependencies=[Depends(require_roles(*_CAN_WRITE))])
async def suspend_user(user_id: UUID, db: Annotated[AsyncSession, Depends(get_db)]):
    user = await _get_user_or_404(db, user_id)
    if user.status != UserStatus.active:
        raise HTTPException(status_code=400, detail="Пользователь не в статусе active")
    return await service.suspend_user(db, user)


@router.post("/users/{user_id}/restore", response_model=UserExtOut, dependencies=[Depends(require_roles(*_CAN_WRITE))])
async def restore_user(user_id: UUID, db: Annotated[AsyncSession, Depends(get_db)]):
    user = await _get_user_or_404(db, user_id)
    if user.status != UserStatus.suspended:
        raise HTTPException(status_code=400, detail="Пользователь не в статусе suspended")
    return await service.restore_user(db, user)


@router.post("/users/{user_id}/block", response_model=UserExtOut, dependencies=[Depends(require_roles(*_CAN_WRITE))])
async def block_user(user_id: UUID, db: Annotated[AsyncSession, Depends(get_db)]):
    user = await _get_user_or_404(db, user_id)
    if user.status == UserStatus.blocked:
        raise HTTPException(status_code=400, detail="Пользователь уже заблокирован")
    return await service.block_user(db, user)


@router.delete("/users/{user_id}", status_code=204, dependencies=[Depends(require_roles(AdminRole.system_admin))])
async def delete_user(user_id: UUID, db: Annotated[AsyncSession, Depends(get_db)]):
    user = await _get_user_or_404(db, user_id)
    await service.delete_user(db, user)


@router.post("/users/{user_id}/reset-password", status_code=204, dependencies=[Depends(require_roles(*_CAN_WRITE))])
async def reset_password(
    user_id: UUID,
    body: UserResetPassword,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    user = await _get_user_or_404(db, user_id)
    await service.reset_password(db, user, body.new_password)


# ── Lifecycle events ──────────────────────────────────────────────────────────

@router.get("/events", response_model=LifecycleEventsListResponse, dependencies=[Depends(require_roles(*_CAN_READ))])
async def list_events(
    db: Annotated[AsyncSession, Depends(get_db)],
    user_id: Optional[UUID] = None,
    event_type: Optional[LifecycleEventType] = None,
    event_status: Optional[LifecycleEventStatus] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    events, total = await service.list_lifecycle_events(
        db,
        user_id=user_id,
        event_type=event_type,
        status=event_status,
        page=page,
        page_size=page_size,
    )
    return LifecycleEventsListResponse(items=events, total=total)


@router.post("/events/hr", status_code=202)
async def webhook_hr_event(
    body: dict,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: CurrentAdmin = Depends(require_roles(*_CAN_WRITE)),
):
    """Резервный канал для кадровых событий (не через Kafka)."""
    from app.kafka.events import KafkaEvent
    from app.modules.identity.consumer import handle_hr_event

    event = KafkaEvent(
        event_type=body.get("event_type", "hire"),
        producer="webhook",
        payload=body,
    )
    import asyncio
    asyncio.create_task(handle_hr_event(event))
    return {"accepted": True}


@router.post("/sync", status_code=202, dependencies=[Depends(require_roles(*_CAN_WRITE))])
async def trigger_sync():
    """Запускает Celery задачу сверки с HR-системой."""
    from app.modules.identity.tasks import reconcile_with_hr
    reconcile_with_hr.delay()
    return {"queued": True}


# ── Reference data ────────────────────────────────────────────────────────────

@router.get("/positions", response_model=list[PositionOut], dependencies=[Depends(require_roles(*_CAN_READ))])
async def list_positions(db: Annotated[AsyncSession, Depends(get_db)]):
    result = await db.execute(select(Position).order_by(Position.level, Position.name))
    return result.scalars().all()


@router.get("/departments", response_model=list[DepartmentOut], dependencies=[Depends(require_roles(*_CAN_READ))])
async def list_departments(db: Annotated[AsyncSession, Depends(get_db)]):
    result = await db.execute(select(Department).order_by(Department.name))
    return result.scalars().all()
