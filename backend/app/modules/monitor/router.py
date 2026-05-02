from datetime import datetime
from typing import Annotated, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import StreamingResponse
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_admin, require_roles
from app.database import get_db
from app.models.admin import AdminRole
from app.models.monitor import (
    Alert,
    AlertDataSource,
    AlertRule,
    AlertStatus,
    AuditLog,
    AuditModule,
    AuditOperation,
    AuditResult,
    AuditTargetType,
    NotificationChannel,
    OutboxEvent,
)
from app.modules.monitor import alert_service
from app.modules.monitor.schemas import (
    AlertDecisionBody,
    AlertOut,
    AlertRuleCreate,
    AlertRuleOut,
    AlertRulesListResponse,
    AlertsListResponse,
    AlertRuleUpdate,
    AuditLogCreate,
    AuditLogListResponse,
    AuditLogOut,
    DashboardMetrics,
    NotificationChannelCreate,
    NotificationChannelOut,
    NotificationChannelUpdate,
    RuleTestResult,
)

router = APIRouter()

_CAN_READ = (AdminRole.system_admin, AdminRole.security_officer, AdminRole.auditor)
_CAN_MANAGE = (AdminRole.system_admin, AdminRole.security_officer)
_INTERNAL = (AdminRole.system_admin, AdminRole.security_officer, AdminRole.hr_operator, AdminRole.auditor)


# ── Dashboard ─────────────────────────────────────────────────────────────────

@router.get("/dashboard", response_model=DashboardMetrics, dependencies=[require_roles(*_CAN_READ)])
async def get_dashboard(db: Annotated[AsyncSession, Depends(get_db)]):
    from datetime import date, timedelta, timezone
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    total_today = (await db.execute(
        select(func.count(AuditLog.id)).where(AuditLog.timestamp >= today_start)
    )).scalar_one()

    failed_logins_today = (await db.execute(
        select(func.count(AuditLog.id)).where(
            AuditLog.timestamp >= today_start,
            AuditLog.operation == AuditOperation.login_failure,
        )
    )).scalar_one()

    active_alerts = (await db.execute(
        select(func.count(Alert.id)).where(Alert.status == AlertStatus.new)
    )).scalar_one()

    from app.models.monitor import AlertSeverity
    critical_alerts = (await db.execute(
        select(func.count(Alert.id)).where(
            Alert.status == AlertStatus.new,
            Alert.severity == AlertSeverity.critical,
        )
    )).scalar_one()

    module_rows = (await db.execute(
        select(AuditLog.module, func.count(AuditLog.id))
        .where(AuditLog.timestamp >= today_start)
        .group_by(AuditLog.module)
    )).all()
    events_by_module = {row[0].value: row[1] for row in module_rows}

    result_rows = (await db.execute(
        select(AuditLog.result, func.count(AuditLog.id))
        .where(AuditLog.timestamp >= today_start)
        .group_by(AuditLog.result)
    )).all()
    events_by_result = {row[0].value: row[1] for row in result_rows}

    return DashboardMetrics(
        total_events_today=total_today,
        failed_logins_today=failed_logins_today,
        active_alerts=active_alerts,
        critical_alerts=critical_alerts,
        events_by_module=events_by_module,
        events_by_result=events_by_result,
    )


# ── Audit Log ─────────────────────────────────────────────────────────────────

@router.get("/audit", response_model=AuditLogListResponse, dependencies=[require_roles(*_CAN_READ)])
async def list_audit(
    db: Annotated[AsyncSession, Depends(get_db)],
    actor_username: Optional[str] = None,
    operation: Optional[AuditOperation] = None,
    module: Optional[AuditModule] = None,
    result: Optional[AuditResult] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
):
    q = select(AuditLog)
    if actor_username:
        q = q.where(AuditLog.actor_username.ilike(f"%{actor_username}%"))
    if operation:
        q = q.where(AuditLog.operation == operation)
    if module:
        q = q.where(AuditLog.module == module)
    if result:
        q = q.where(AuditLog.result == result)
    if date_from:
        q = q.where(AuditLog.timestamp >= date_from)
    if date_to:
        q = q.where(AuditLog.timestamp <= date_to)

    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar_one()
    items = (await db.execute(
        q.order_by(desc(AuditLog.timestamp)).offset((page - 1) * page_size).limit(page_size)
    )).scalars().all()

    return AuditLogListResponse(items=list(items), total=total, page=page, page_size=page_size)


@router.get("/audit/export", dependencies=[require_roles(*_CAN_READ)])
async def export_audit(
    db: Annotated[AsyncSession, Depends(get_db)],
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    fmt: str = Query("csv", pattern="^(csv|json)$"),
):
    import csv
    import io
    import json as jsonlib

    q = select(AuditLog).order_by(desc(AuditLog.timestamp)).limit(10000)
    if date_from:
        q = q.where(AuditLog.timestamp >= date_from)
    if date_to:
        q = q.where(AuditLog.timestamp <= date_to)
    rows = (await db.execute(q)).scalars().all()

    if fmt == "json":
        data = jsonlib.dumps(
            [AuditLogOut.model_validate(r).model_dump(mode="json") for r in rows],
            ensure_ascii=False,
        )
        return Response(content=data, media_type="application/json",
                        headers={"Content-Disposition": "attachment; filename=audit.json"})

    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=";")
    writer.writerow(["id", "timestamp", "actor_username", "target_type", "operation", "module", "result", "ip_address"])
    for r in rows:
        writer.writerow([r.id, r.timestamp, r.actor_username, r.target_type.value, r.operation.value, r.module.value, r.result.value, r.ip_address])
    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=audit.csv"},
    )


@router.get("/audit/{event_id}", response_model=AuditLogOut, dependencies=[require_roles(*_CAN_READ)])
async def get_audit_entry(event_id: UUID, db: Annotated[AsyncSession, Depends(get_db)]):
    row = (await db.execute(select(AuditLog).where(AuditLog.event_id == event_id))).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Запись не найдена")
    return row


@router.post("/audit", response_model=AuditLogOut, status_code=201, dependencies=[require_roles(*_INTERNAL)])
async def create_audit_entry(body: AuditLogCreate, db: Annotated[AsyncSession, Depends(get_db)]):
    from app.modules.monitor.audit_service import log
    entry = await log(
        db,
        operation=body.operation,
        module=body.module,
        target_type=body.target_type,
        target_id=body.target_id,
        result=body.result,
        actor_id=body.actor_id,
        actor_username=body.actor_username,
        ip_address=body.ip_address,
        user_agent=body.user_agent,
        details=body.details,
        correlation_id=body.correlation_id,
    )
    return entry


# ── Alert Rules ───────────────────────────────────────────────────────────────

@router.get("/rules", response_model=AlertRulesListResponse, dependencies=[require_roles(*_CAN_READ)])
async def list_rules(db: Annotated[AsyncSession, Depends(get_db)]):
    rows = (await db.execute(select(AlertRule).order_by(AlertRule.severity))).scalars().all()
    return AlertRulesListResponse(items=list(rows), total=len(rows))


@router.post("/rules", response_model=AlertRuleOut, status_code=201, dependencies=[require_roles(*_CAN_MANAGE)])
async def create_rule(body: AlertRuleCreate, db: Annotated[AsyncSession, Depends(get_db)]):
    existing = (await db.execute(select(AlertRule).where(AlertRule.code == body.code))).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="Правило с таким кодом уже существует")
    rule = AlertRule(
        code=body.code,
        name=body.name,
        description=body.description,
        condition_type=body.condition_type,
        condition_config=body.condition_config,
        severity=body.severity,
        cooldown_seconds=body.cooldown_seconds,
        data_source=body.data_source,
    )
    db.add(rule)
    await db.flush()
    return rule


@router.patch("/rules/{rule_id}", response_model=AlertRuleOut, dependencies=[require_roles(*_CAN_MANAGE)])
async def update_rule(rule_id: UUID, body: AlertRuleUpdate, db: Annotated[AsyncSession, Depends(get_db)]):
    rule = (await db.execute(select(AlertRule).where(AlertRule.id == rule_id))).scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Правило не найдено")
    if body.name is not None:
        rule.name = body.name
    if body.description is not None:
        rule.description = body.description
    if body.condition_config is not None:
        rule.condition_config = body.condition_config
    if body.severity is not None:
        rule.severity = body.severity
    if body.cooldown_seconds is not None:
        rule.cooldown_seconds = body.cooldown_seconds
    if body.is_enabled is not None:
        rule.is_enabled = body.is_enabled
    await db.flush()
    return rule


@router.post("/rules/{rule_id}/toggle", response_model=AlertRuleOut, dependencies=[require_roles(*_CAN_MANAGE)])
async def toggle_rule(rule_id: UUID, db: Annotated[AsyncSession, Depends(get_db)]):
    rule = (await db.execute(select(AlertRule).where(AlertRule.id == rule_id))).scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Правило не найдено")
    rule.is_enabled = not rule.is_enabled
    await db.flush()
    return rule


@router.post("/rules/{rule_id}/test", response_model=RuleTestResult, dependencies=[require_roles(*_CAN_MANAGE)])
async def test_rule(rule_id: UUID, db: Annotated[AsyncSession, Depends(get_db)]):
    rule = (await db.execute(select(AlertRule).where(AlertRule.id == rule_id))).scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Правило не найдено")
    if rule.data_source == AlertDataSource.postgres:
        from app.modules.monitor.rules import SIMPLE_RULES
        checker = SIMPLE_RULES.get(rule.code)
        if not checker:
            return RuleTestResult(rule_code=rule.code, matched=False, details={"info": "No checker implemented"})
        last_entry = (await db.execute(
            select(AuditLog).order_by(desc(AuditLog.id)).limit(1)
        )).scalar_one_or_none()
        if not last_entry:
            return RuleTestResult(rule_code=rule.code, matched=False, details={"info": "No audit entries"})
        match = await checker(db, rule.condition_config, last_entry)
        return RuleTestResult(rule_code=rule.code, matched=match.matched, details=match.details)
    else:
        return RuleTestResult(rule_code=rule.code, matched=False, details={"info": "ES rules require live Elasticsearch"})


# ── Alerts ────────────────────────────────────────────────────────────────────

@router.get("/alerts", response_model=AlertsListResponse, dependencies=[require_roles(*_CAN_READ)])
async def list_alerts(
    db: Annotated[AsyncSession, Depends(get_db)],
    status: Optional[AlertStatus] = None,
    severity: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    from sqlalchemy.orm import selectinload
    q = select(Alert).options(selectinload(Alert.rule))
    if status:
        q = q.where(Alert.status == status)
    if severity:
        from app.models.monitor import AlertSeverity as AS
        q = q.where(Alert.severity == AS(severity))
    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar_one()
    items = (await db.execute(
        q.order_by(desc(Alert.triggered_at)).offset((page - 1) * page_size).limit(page_size)
    )).scalars().all()
    return AlertsListResponse(items=list(items), total=total, page=page, page_size=page_size)


@router.get("/alerts/{alert_id}", response_model=AlertOut, dependencies=[require_roles(*_CAN_READ)])
async def get_alert(alert_id: UUID, db: Annotated[AsyncSession, Depends(get_db)]):
    from sqlalchemy.orm import selectinload
    row = (await db.execute(
        select(Alert).options(selectinload(Alert.rule)).where(Alert.id == alert_id)
    )).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Оповещение не найдено")
    return row


@router.post("/alerts/{alert_id}/acknowledge", response_model=AlertOut, dependencies=[require_roles(*_CAN_MANAGE)])
async def acknowledge_alert(
    alert_id: UUID,
    body: AlertDecisionBody,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_admin=Depends(get_current_admin),
):
    from sqlalchemy.orm import selectinload
    row = (await db.execute(
        select(Alert).options(selectinload(Alert.rule)).where(Alert.id == alert_id)
    )).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Оповещение не найдено")
    if row.status != AlertStatus.new:
        raise HTTPException(status_code=400, detail="Оповещение уже обработано")
    return await alert_service.acknowledge_alert(db, row, current_admin.id, body.comment)


@router.post("/alerts/{alert_id}/resolve", response_model=AlertOut, dependencies=[require_roles(*_CAN_MANAGE)])
async def resolve_alert(
    alert_id: UUID,
    body: AlertDecisionBody,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_admin=Depends(get_current_admin),
):
    from sqlalchemy.orm import selectinload
    row = (await db.execute(
        select(Alert).options(selectinload(Alert.rule)).where(Alert.id == alert_id)
    )).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Оповещение не найдено")
    return await alert_service.resolve_alert(db, row, current_admin.id, body.comment)


@router.post("/alerts/{alert_id}/false-positive", response_model=AlertOut, dependencies=[require_roles(*_CAN_MANAGE)])
async def mark_false_positive(
    alert_id: UUID,
    body: AlertDecisionBody,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_admin=Depends(get_current_admin),
):
    from sqlalchemy.orm import selectinload
    row = (await db.execute(
        select(Alert).options(selectinload(Alert.rule)).where(Alert.id == alert_id)
    )).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Оповещение не найдено")
    return await alert_service.mark_false_positive(db, row, current_admin.id, body.comment)


# ── Notification Channels ─────────────────────────────────────────────────────

@router.get("/channels", response_model=list[NotificationChannelOut], dependencies=[require_roles(*_CAN_READ)])
async def list_channels(db: Annotated[AsyncSession, Depends(get_db)]):
    rows = (await db.execute(select(NotificationChannel))).scalars().all()
    return list(rows)


@router.post("/channels", response_model=NotificationChannelOut, status_code=201, dependencies=[require_roles(*_CAN_MANAGE)])
async def create_channel(body: NotificationChannelCreate, db: Annotated[AsyncSession, Depends(get_db)]):
    ch = NotificationChannel(code=body.code, type=body.type, config=body.config, is_enabled=body.is_enabled)
    db.add(ch)
    await db.flush()
    return ch


@router.patch("/channels/{channel_id}", response_model=NotificationChannelOut, dependencies=[require_roles(*_CAN_MANAGE)])
async def update_channel(
    channel_id: UUID,
    body: NotificationChannelUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    ch = (await db.execute(select(NotificationChannel).where(NotificationChannel.id == channel_id))).scalar_one_or_none()
    if not ch:
        raise HTTPException(status_code=404, detail="Канал не найден")
    if body.config is not None:
        ch.config = body.config
    if body.is_enabled is not None:
        ch.is_enabled = body.is_enabled
    await db.flush()
    return ch


# ── Kibana ────────────────────────────────────────────────────────────────────

@router.get("/kibana-token", dependencies=[require_roles(*_CAN_READ)])
async def kibana_token():
    from app.config import settings
    return {"embed_url": settings.KIBANA_EMBED_URL, "token": None}
