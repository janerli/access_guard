import enum
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, DateTime, Enum, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class UserStatus(str, enum.Enum):
    new = "new"
    active = "active"
    suspended = "suspended"
    blocked = "blocked"
    deleted = "deleted"


class LifecycleEventType(str, enum.Enum):
    hire = "hire"
    transfer = "transfer"
    leave_start = "leave_start"
    leave_end = "leave_end"
    terminate = "terminate"


class LifecycleEventSource(str, enum.Enum):
    hr_system = "hr_system"
    manual = "manual"
    scheduled = "scheduled"


class LifecycleEventStatus(str, enum.Enum):
    pending = "pending"
    processed = "processed"
    failed = "failed"


class Position(Base):
    __tablename__ = "positions"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    level: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class Department(Base):
    __tablename__ = "departments"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    parent_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("departments.id"), nullable=True
    )
    manager_user_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users_ext.id", use_alter=True, name="fk_department_manager"),
        nullable=True,
    )

    parent: Mapped["Department | None"] = relationship(
        "Department",
        remote_side="Department.id",
        back_populates="children",
        foreign_keys="[Department.parent_id]",
    )
    children: Mapped[list["Department"]] = relationship(
        "Department",
        back_populates="parent",
        foreign_keys="[Department.parent_id]",
    )


class UserExt(Base):
    __tablename__ = "users_ext"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    ldap_dn: Mapped[str | None] = mapped_column(String(512), unique=True, nullable=True)
    employee_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    position_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("positions.id"), nullable=True
    )
    department_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("departments.id"), nullable=True
    )
    status: Mapped[UserStatus] = mapped_column(
        Enum(UserStatus, name="user_status"), nullable=False, default=UserStatus.active
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    position: Mapped["Position | None"] = relationship(
        "Position", foreign_keys=[position_id], lazy="selectin"
    )
    department: Mapped["Department | None"] = relationship(
        "Department", foreign_keys=[department_id], lazy="selectin"
    )
    lifecycle_events: Mapped[list["LifecycleEvent"]] = relationship(
        "LifecycleEvent", back_populates="user", foreign_keys="[LifecycleEvent.user_id]"
    )


class LifecycleEvent(Base):
    __tablename__ = "lifecycle_events"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users_ext.id"), nullable=True
    )
    event_type: Mapped[LifecycleEventType] = mapped_column(
        Enum(LifecycleEventType, name="lifecycle_event_type"), nullable=False
    )
    source: Mapped[LifecycleEventSource] = mapped_column(
        Enum(LifecycleEventSource, name="lifecycle_event_source"), nullable=False
    )
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[LifecycleEventStatus] = mapped_column(
        Enum(LifecycleEventStatus, name="lifecycle_event_status"),
        nullable=False,
        default=LifecycleEventStatus.pending,
    )
    kafka_offset: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    user: Mapped["UserExt | None"] = relationship(
        "UserExt", back_populates="lifecycle_events", foreign_keys=[user_id]
    )
