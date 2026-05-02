import uuid
from datetime import datetime
from enum import Enum as PyEnum

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AdminRole(str, PyEnum):
    system_admin = "system_admin"
    security_officer = "security_officer"
    hr_operator = "hr_operator"
    auditor = "auditor"


class AdminUser(Base):
    __tablename__ = "admin_users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(sa.String(100), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(sa.String(255), unique=True, nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    hashed_password: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    role: Mapped[str] = mapped_column(
        sa.Enum(AdminRole, name="admin_role", create_constraint=True),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(sa.Boolean, default=True, nullable=False)
    failed_login_count: Mapped[int] = mapped_column(sa.Integer, default=0, nullable=False)
    locked_until: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.text("now()"),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.text("now()"),
        onupdate=datetime.utcnow,
        nullable=False,
    )
