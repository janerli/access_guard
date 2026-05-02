import enum
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, Boolean, DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class AuditTargetType(str, enum.Enum):
    user = "user"
    role = "role"
    resource = "resource"
    system = "system"


class AuditOperation(str, enum.Enum):
    create = "create"
    read = "read"
    update = "update"
    delete = "delete"
    login_success = "login_success"
    login_failure = "login_failure"
    permission_check = "permission_check"
    role_assign = "role_assign"
    role_revoke = "role_revoke"
    password_reset = "password_reset"
    suspend = "suspend"
    restore = "restore"
    block = "block"
    request_submit = "request_submit"
    request_approve = "request_approve"
    request_reject = "request_reject"
    request_withdraw = "request_withdraw"


class AuditModule(str, enum.Enum):
    identity = "identity"
    access = "access"
    monitor = "monitor"
    reports = "reports"
    auth = "auth"


class AuditResult(str, enum.Enum):
    success = "success"
    failure = "failure"
    denied = "denied"


class OutboxStatus(str, enum.Enum):
    pending = "pending"
    published = "published"
    failed = "failed"


class AlertConditionType(str, enum.Enum):
    threshold = "threshold"
    pattern = "pattern"
    anomaly = "anomaly"


class AlertSeverity(str, enum.Enum):
    info = "info"
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class AlertDataSource(str, enum.Enum):
    postgres = "postgres"
    elasticsearch = "elasticsearch"


class AlertStatus(str, enum.Enum):
    new = "new"
    acknowledged = "acknowledged"
    resolved = "resolved"
    false_positive = "false_positive"


class NotificationChannelType(str, enum.Enum):
    email = "email"
    webhook = "webhook"
    log = "log"
    kafka = "kafka"


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    event_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), unique=True, nullable=False, default=uuid4)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
    actor_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users_ext.id", ondelete="SET NULL"), nullable=True
    )
    actor_username: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    target_type: Mapped[AuditTargetType] = mapped_column(
        Enum(AuditTargetType, name="audit_target_type"), nullable=False
    )
    target_id: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    operation: Mapped[AuditOperation] = mapped_column(
        Enum(AuditOperation, name="audit_operation"), nullable=False
    )
    module: Mapped[AuditModule] = mapped_column(
        Enum(AuditModule, name="audit_module"), nullable=False
    )
    result: Mapped[AuditResult] = mapped_column(
        Enum(AuditResult, name="audit_result"), nullable=False
    )
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
    details: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    correlation_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    published_to_kafka: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class OutboxEvent(Base):
    __tablename__ = "outbox_events"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    audit_log_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("audit_log.id", ondelete="CASCADE"), nullable=False
    )
    topic: Mapped[str] = mapped_column(String(100), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[OutboxStatus] = mapped_column(
        Enum(OutboxStatus, name="outbox_status"), nullable=False, default=OutboxStatus.pending
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class AlertRule(Base):
    __tablename__ = "alert_rules"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    condition_type: Mapped[AlertConditionType] = mapped_column(
        Enum(AlertConditionType, name="alert_condition_type"), nullable=False
    )
    condition_config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    severity: Mapped[AlertSeverity] = mapped_column(
        Enum(AlertSeverity, name="alert_severity"), nullable=False
    )
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    cooldown_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=300)
    data_source: Mapped[AlertDataSource] = mapped_column(
        Enum(AlertDataSource, name="alert_data_source"), nullable=False
    )

    alerts: Mapped[list["Alert"]] = relationship("Alert", back_populates="rule")


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    rule_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("alert_rules.id"), nullable=False
    )
    triggered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    subject_user_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users_ext.id", ondelete="SET NULL"), nullable=True
    )
    severity: Mapped[AlertSeverity] = mapped_column(
        Enum(AlertSeverity, name="alert_severity"), nullable=False
    )
    status: Mapped[AlertStatus] = mapped_column(
        Enum(AlertStatus, name="alert_status"), nullable=False, default=AlertStatus.new
    )
    correlation_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    details: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    acknowledged_by: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    resolution_comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    rule: Mapped["AlertRule"] = relationship("AlertRule", back_populates="alerts")


class NotificationChannel(Base):
    __tablename__ = "notification_channels"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    type: Mapped[NotificationChannelType] = mapped_column(
        Enum(NotificationChannelType, name="notification_channel_type"), nullable=False
    )
    config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
