from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.identity import LifecycleEventSource, LifecycleEventStatus, LifecycleEventType, UserStatus


class PositionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    name: str
    level: int


class DepartmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    name: str
    parent_id: Optional[UUID] = None
    manager_user_id: Optional[UUID] = None


class DepartmentTreeOut(DepartmentOut):
    children: list["DepartmentTreeOut"] = []


class UserExtOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    employee_id: str
    username: str
    email: str
    full_name: str
    status: UserStatus
    position_id: Optional[UUID] = None
    department_id: Optional[UUID] = None
    position: Optional[PositionOut] = None
    department: Optional[DepartmentOut] = None
    ldap_dn: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class UserExtCreate(BaseModel):
    employee_id: str
    username: str
    email: str
    full_name: str
    position_code: Optional[str] = None
    department_code: Optional[str] = None


class UserExtUpdate(BaseModel):
    email: Optional[str] = None
    full_name: Optional[str] = None
    position_code: Optional[str] = None
    department_code: Optional[str] = None


class UserResetPassword(BaseModel):
    new_password: str


class UsersListResponse(BaseModel):
    items: list[UserExtOut]
    total: int
    page: int
    page_size: int


class LifecycleEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: Optional[UUID] = None
    event_type: LifecycleEventType
    source: LifecycleEventSource
    status: LifecycleEventStatus
    processed_at: Optional[datetime] = None
    created_at: datetime
    payload: dict


class LifecycleEventsListResponse(BaseModel):
    items: list[LifecycleEventOut]
    total: int
