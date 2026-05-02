from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.models.admin import AdminRole


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class AdminUserOut(BaseModel):
    id: UUID
    username: str
    email: str
    full_name: str
    role: AdminRole
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
