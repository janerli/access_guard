from typing import Annotated, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_admin, require_roles
from app.database import get_db
from app.models.access import AccessRequest, AccessRequestStatus, Permission, Role
from app.models.admin import AdminRole
from app.modules.access import service
from app.modules.access.schemas import (
    AccessRequestCreate,
    AccessRequestOut,
    AccessRequestsListResponse,
    AssignRoleBody,
    CheckPermissionBody,
    CheckPermissionResult,
    MatrixUpdateBody,
    PermissionOut,
    PositionMatrixRow,
    RequestDecisionBody,
    RoleCreate,
    RoleDetailOut,
    RoleOut,
    RolesListResponse,
    RoleUpdate,
    UserRoleOut,
)

router = APIRouter()

_CAN_READ = (AdminRole.system_admin, AdminRole.security_officer, AdminRole.hr_operator, AdminRole.auditor)
_CAN_MANAGE = (AdminRole.system_admin, AdminRole.security_officer)
_CAN_APPROVE = (AdminRole.system_admin, AdminRole.security_officer)


# ── Permissions ────────────────────────────────────────────────────────────────

@router.get("/permissions", response_model=list[PermissionOut], dependencies=[require_roles(*_CAN_READ)])
async def list_permissions(db: Annotated[AsyncSession, Depends(get_db)]):
    return await service.list_permissions(db)


# ── Roles ──────────────────────────────────────────────────────────────────────

@router.get("/roles", response_model=RolesListResponse, dependencies=[require_roles(*_CAN_READ)])
async def list_roles(
    db: Annotated[AsyncSession, Depends(get_db)],
    search: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    roles, total = await service.list_roles(db, search=search, page=page, page_size=page_size)
    return RolesListResponse(items=roles, total=total, page=page, page_size=page_size)


@router.post("/roles", response_model=RoleOut, status_code=201, dependencies=[require_roles(*_CAN_MANAGE)])
async def create_role(body: RoleCreate, db: Annotated[AsyncSession, Depends(get_db)]):
    existing = (await db.execute(select(Role).where(Role.code == body.code))).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="Роль с таким кодом уже существует")
    return await service.create_role(db, code=body.code, name=body.name, description=body.description, is_privileged=body.is_privileged)


@router.get("/roles/{role_id}", response_model=RoleDetailOut, dependencies=[require_roles(*_CAN_READ)])
async def get_role(role_id: UUID, db: Annotated[AsyncSession, Depends(get_db)]):
    role = await service.get_role(db, role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Роль не найдена")
    permissions = [rp.permission for rp in role.role_permissions]
    return RoleDetailOut(
        **RoleOut.model_validate(role).model_dump(),
        permissions=[PermissionOut.model_validate(p) for p in permissions],
    )


@router.patch("/roles/{role_id}", response_model=RoleOut, dependencies=[require_roles(*_CAN_MANAGE)])
async def update_role(role_id: UUID, body: RoleUpdate, db: Annotated[AsyncSession, Depends(get_db)]):
    role = (await db.execute(select(Role).where(Role.id == role_id))).scalar_one_or_none()
    if not role:
        raise HTTPException(status_code=404, detail="Роль не найдена")
    return await service.update_role(db, role, name=body.name, description=body.description, is_privileged=body.is_privileged)


@router.delete("/roles/{role_id}", status_code=204, dependencies=[require_roles(AdminRole.system_admin)])
async def delete_role(role_id: UUID, db: Annotated[AsyncSession, Depends(get_db)]):
    role = (await db.execute(select(Role).where(Role.id == role_id))).scalar_one_or_none()
    if not role:
        raise HTTPException(status_code=404, detail="Роль не найдена")
    await service.delete_role(db, role)


@router.post("/roles/{role_id}/permissions/{permission_id}", status_code=204, dependencies=[require_roles(*_CAN_MANAGE)])
async def add_permission(role_id: UUID, permission_id: UUID, db: Annotated[AsyncSession, Depends(get_db)]):
    role = (await db.execute(select(Role).where(Role.id == role_id))).scalar_one_or_none()
    if not role:
        raise HTTPException(status_code=404, detail="Роль не найдена")
    perm = (await db.execute(select(Permission).where(Permission.id == permission_id))).scalar_one_or_none()
    if not perm:
        raise HTTPException(status_code=404, detail="Разрешение не найдено")
    await service.add_permission_to_role(db, role_id, permission_id)


@router.delete("/roles/{role_id}/permissions/{permission_id}", status_code=204, dependencies=[require_roles(*_CAN_MANAGE)])
async def remove_permission(role_id: UUID, permission_id: UUID, db: Annotated[AsyncSession, Depends(get_db)]):
    await service.remove_permission_from_role(db, role_id, permission_id)


# ── User roles ─────────────────────────────────────────────────────────────────

@router.get("/users/{user_id}/roles", response_model=list[UserRoleOut], dependencies=[require_roles(*_CAN_READ)])
async def get_user_roles(user_id: UUID, db: Annotated[AsyncSession, Depends(get_db)]):
    return await service.list_user_roles(db, user_id)


@router.post("/users/{user_id}/roles", response_model=UserRoleOut, status_code=201, dependencies=[require_roles(*_CAN_MANAGE)])
async def assign_role(
    user_id: UUID,
    body: AssignRoleBody,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_admin=Depends(get_current_admin),
):
    role = (await db.execute(select(Role).where(Role.id == body.role_id))).scalar_one_or_none()
    if not role:
        raise HTTPException(status_code=404, detail="Роль не найдена")
    user_role = await service.assign_role(
        db,
        user_id=user_id,
        role_id=body.role_id,
        granted_by=current_admin.id,
        expires_at=body.expires_at,
        actor_username=current_admin.username,
    )
    await db.refresh(user_role, ["role"])
    return user_role


@router.delete("/users/{user_id}/roles/{user_role_id}", status_code=204, dependencies=[require_roles(*_CAN_MANAGE)])
async def revoke_role(user_id: UUID, user_role_id: UUID, db: Annotated[AsyncSession, Depends(get_db)]):
    await service.revoke_role(db, user_role_id)


# ── Permission check ───────────────────────────────────────────────────────────

@router.post("/check", response_model=CheckPermissionResult, dependencies=[require_roles(*_CAN_READ)])
async def check_permission(body: CheckPermissionBody, db: Annotated[AsyncSession, Depends(get_db)]):
    allowed = await service.has_permission(db, body.user_id, body.permission_code)
    return CheckPermissionResult(user_id=body.user_id, permission_code=body.permission_code, allowed=allowed)


# ── Access Requests ────────────────────────────────────────────────────────────

@router.get("/requests", response_model=AccessRequestsListResponse, dependencies=[require_roles(*_CAN_READ)])
async def list_requests(
    db: Annotated[AsyncSession, Depends(get_db)],
    user_id: Optional[UUID] = None,
    req_status: Optional[AccessRequestStatus] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    items, total = await service.list_access_requests(db, user_id=user_id, status=req_status, page=page, page_size=page_size)
    return AccessRequestsListResponse(items=items, total=total, page=page, page_size=page_size)


@router.post("/requests", response_model=AccessRequestOut, status_code=201, dependencies=[require_roles(*_CAN_READ)])
async def create_request(
    body: AccessRequestCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    role = (await db.execute(select(Role).where(Role.id == body.role_id))).scalar_one_or_none()
    if not role:
        raise HTTPException(status_code=404, detail="Роль не найдена")
    return await service.create_access_request(
        db,
        user_id=body.user_id,
        role_id=body.role_id,
        justification=body.justification,
    )


@router.get("/requests/{request_id}", response_model=AccessRequestOut, dependencies=[require_roles(*_CAN_READ)])
async def get_request(request_id: UUID, db: Annotated[AsyncSession, Depends(get_db)]):
    req = await service.get_access_request(db, request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Заявка не найдена")
    return req


@router.post("/requests/{request_id}/approve", response_model=AccessRequestOut, dependencies=[require_roles(*_CAN_APPROVE)])
async def approve_request(
    request_id: UUID,
    body: RequestDecisionBody,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_admin=Depends(get_current_admin),
):
    req = await service.get_access_request(db, request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Заявка не найдена")
    if req.status != AccessRequestStatus.pending:
        raise HTTPException(status_code=400, detail="Заявка не в статусе pending")
    return await service.approve_request(db, req, decided_by=current_admin.id, comment=body.comment, actor_username=current_admin.username)


@router.post("/requests/{request_id}/reject", response_model=AccessRequestOut, dependencies=[require_roles(*_CAN_APPROVE)])
async def reject_request(
    request_id: UUID,
    body: RequestDecisionBody,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_admin=Depends(get_current_admin),
):
    req = await service.get_access_request(db, request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Заявка не найдена")
    if req.status != AccessRequestStatus.pending:
        raise HTTPException(status_code=400, detail="Заявка не в статусе pending")
    return await service.reject_request(db, req, decided_by=current_admin.id, comment=body.comment)


@router.delete("/requests/{request_id}", status_code=204, dependencies=[require_roles(*_CAN_READ)])
async def withdraw_request(
    request_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    req = await service.get_access_request(db, request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Заявка не найдена")
    if req.status != AccessRequestStatus.pending:
        raise HTTPException(status_code=400, detail="Можно отозвать только pending заявку")
    await service.withdraw_request(db, req)


# ── Permission Matrix ──────────────────────────────────────────────────────────

@router.get("/matrix", response_model=list[PositionMatrixRow], dependencies=[require_roles(*_CAN_READ)])
async def get_matrix(db: Annotated[AsyncSession, Depends(get_db)]):
    return await service.get_permission_matrix(db)


@router.patch("/matrix", status_code=204, dependencies=[require_roles(*_CAN_MANAGE)])
async def update_matrix(body: MatrixUpdateBody, db: Annotated[AsyncSession, Depends(get_db)]):
    from app.models.identity import Position
    pos = (await db.execute(select(Position).where(Position.id == body.position_id))).scalar_one_or_none()
    if not pos:
        raise HTTPException(status_code=404, detail="Должность не найдена")
    await service.update_position_defaults(db, body.position_id, body.role_ids)
