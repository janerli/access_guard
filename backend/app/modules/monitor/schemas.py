from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel

from app.models.monitor import (
    AlertConditionType,
    AlertDataSource,
    AlertSeverity,
    AlertStatus,
    AuditModule,
    AuditOperation,
    AuditResult,
    AuditTargetType,
    NotificationChannelType,
    OutboxStatus,
)


# ── AuditLog ──────────────────────────────────────────────────────────────────

class AuditLogOut(BaseModel):
    id: int
    event_id: UUID
    timestamp: datetime
    actor_id: Optional[UUID]
    actor_username: str
    target_type: AuditTargetType
    target_id: str
    operation: AuditOperation
    module: AuditModule
    result: AuditResult
    ip_address: Optional[str]
    user_agent: Optional[str]
    details: Optional[dict]
    correlation_id: Optional[UUID]
    published_to_kafka: bool

    model_config = {"from_attributes": True}


class AuditLogCreate(BaseModel):
    operation: AuditOperation
    module: AuditModule
    target_type: AuditTargetType
    target_id: str = ""
    result: AuditResult = AuditResult.success
    actor_id: Optional[UUID] = None
    actor_username: str = ""
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    details: Optional[dict] = None
    correlation_id: Optional[UUID] = None


class AuditLogListResponse(BaseModel):
    items: list[AuditLogOut]
    total: int
    page: int
    page_size: int


# ── AlertRule ─────────────────────────────────────────────────────────────────

class AlertRuleOut(BaseModel):
    id: UUID
    code: str
    name: str
    description: str
    condition_type: AlertConditionType
    condition_config: dict
    severity: AlertSeverity
    is_enabled: bool
    cooldown_seconds: int
    data_source: AlertDataSource

    model_config = {"from_attributes": True}


class AlertRuleCreate(BaseModel):
    code: str
    name: str
    description: str = ""
    condition_type: AlertConditionType
    condition_config: dict = {}
    severity: AlertSeverity
    cooldown_seconds: int = 300
    data_source: AlertDataSource


class AlertRuleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    condition_config: Optional[dict] = None
    severity: Optional[AlertSeverity] = None
    cooldown_seconds: Optional[int] = None
    is_enabled: Optional[bool] = None


class AlertRulesListResponse(BaseModel):
    items: list[AlertRuleOut]
    total: int


# ── Alert ─────────────────────────────────────────────────────────────────────

class AlertOut(BaseModel):
    id: UUID
    rule_id: UUID
    triggered_at: datetime
    subject_user_id: Optional[UUID]
    severity: AlertSeverity
    status: AlertStatus
    correlation_id: Optional[UUID]
    details: dict
    acknowledged_at: Optional[datetime]
    acknowledged_by: Optional[UUID]
    resolution_comment: Optional[str]
    rule: Optional[AlertRuleOut] = None

    model_config = {"from_attributes": True}


class AlertsListResponse(BaseModel):
    items: list[AlertOut]
    total: int
    page: int
    page_size: int


class AlertDecisionBody(BaseModel):
    comment: Optional[str] = None


# ── NotificationChannel ───────────────────────────────────────────────────────

class NotificationChannelOut(BaseModel):
    id: UUID
    code: str
    type: NotificationChannelType
    config: dict
    is_enabled: bool

    model_config = {"from_attributes": True}


class NotificationChannelCreate(BaseModel):
    code: str
    type: NotificationChannelType
    config: dict = {}
    is_enabled: bool = True


class NotificationChannelUpdate(BaseModel):
    config: Optional[dict] = None
    is_enabled: Optional[bool] = None


# ── Dashboard ─────────────────────────────────────────────────────────────────

class DashboardMetrics(BaseModel):
    total_events_today: int
    failed_logins_today: int
    active_alerts: int
    critical_alerts: int
    events_by_module: dict[str, int]
    events_by_result: dict[str, int]


# ── RuleTest ──────────────────────────────────────────────────────────────────

class RuleTestResult(BaseModel):
    rule_code: str
    matched: bool
    details: dict
