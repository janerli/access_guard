from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel

from app.models.access import AccessRequestStatus, ResourceType


# ── Permissions ────────────────────────────────────────────────────────────────

class PermissionOut(BaseModel):
    id: UUID
    code: str
    description: str

    model_config = {"from_attributes": True}


# ── Roles ──────────────────────────────────────────────────────────────────────

class RoleOut(BaseModel):
    id: UUID
    code: str
    name: str
    description: str
    is_privileged: bool
    owner_user_id: Optional[UUID]

    model_config = {"from_attributes": True}


class RoleDetailOut(RoleOut):
    permissions: list[PermissionOut] = []


class RoleCreate(BaseModel):
    code: str
    name: str
    description: str = ""
    is_privileged: bool = False


class RoleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_privileged: Optional[bool] = None


class RolesListResponse(BaseModel):
    items: list[RoleOut]
    total: int
    page: int
    page_size: int


# ── UserRoles ──────────────────────────────────────────────────────────────────

class UserRoleOut(BaseModel):
    id: UUID
    user_id: UUID
    role_id: UUID
    role: RoleOut
    granted_at: datetime
    granted_by: Optional[UUID]
    expires_at: Optional[datetime]
    request_id: Optional[UUID]

    model_config = {"from_attributes": True}


class AssignRoleBody(BaseModel):
    role_id: UUID
    expires_at: Optional[datetime] = None


# ── Permission check ───────────────────────────────────────────────────────────

class CheckPermissionBody(BaseModel):
    user_id: UUID
    permission_code: str


class CheckPermissionResult(BaseModel):
    user_id: UUID
    permission_code: str
    allowed: bool


# ── Access Requests ────────────────────────────────────────────────────────────

class AccessRequestOut(BaseModel):
    id: UUID
    user_id: UUID
    role_id: UUID
    role: RoleOut
    justification: str
    status: AccessRequestStatus
    created_at: datetime
    decided_at: Optional[datetime]
    decided_by: Optional[UUID]
    decision_comment: Optional[str]

    model_config = {"from_attributes": True}


class AccessRequestCreate(BaseModel):
    user_id: UUID
    role_id: UUID
    justification: str


class RequestDecisionBody(BaseModel):
    comment: Optional[str] = None


class AccessRequestsListResponse(BaseModel):
    items: list[AccessRequestOut]
    total: int
    page: int
    page_size: int


# ── Resources ──────────────────────────────────────────────────────────────────

class ResourceOut(BaseModel):
    id: UUID
    code: str
    name: str
    type: ResourceType
    owner_user_id: Optional[UUID]

    model_config = {"from_attributes": True}


# ── Permission Matrix ──────────────────────────────────────────────────────────

class PositionMatrixRow(BaseModel):
    position_id: UUID
    position_code: str
    position_name: str
    role_ids: list[UUID]
    roles: list[RoleOut]


class MatrixUpdateBody(BaseModel):
    position_id: UUID
    role_ids: list[UUID]
