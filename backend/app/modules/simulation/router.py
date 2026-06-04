"""Threat simulation — creates synthetic audit events and fires detection rules.

For demo / test purposes only. All endpoints require system_admin or security_officer role.
Simple rules are triggered via real audit_log entries + direct rule evaluation.
Complex (ES-based) rules create alerts directly (bypassing ES since data may not be indexed yet).
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_admin, require_roles
from app.database import get_db
from app.models.admin import AdminRole, AdminUser
from app.models.monitor import (
    Alert,
    AlertDataSource,
    AlertRule,
    AlertSeverity,
    AlertStatus,
    AuditLog,
    AuditModule,
    AuditOperation,
    AuditResult,
    AuditTargetType,
)
from app.modules.monitor import alert_service

router = APIRouter()
_ALLOWED = (AdminRole.system_admin, AdminRole.security_officer)


# ── Schemas ───────────────────────────────────────────────────────────────────

class SimScenario(BaseModel):
    code: str
    name: str
    description: str
    severity: str
    data_source: str
    how: str  # human-readable explanation of what will be simulated


class SimResult(BaseModel):
    scenario_code: str
    success: bool
    alert_id: str | None = None
    alert_severity: str | None = None
    message: str
    audit_entries_created: int = 0


# ── Scenario catalogue ────────────────────────────────────────────────────────

SCENARIOS: list[SimScenario] = [
    SimScenario(
        code="multiple_failed_logins",
        name="Множественные неудачные входы",
        severity="high",
        data_source="postgres",
        description="5+ неудачных попыток входа за 15 минут от одного пользователя",
        how="Создаёт 6 записей login_failure для одного тестового пользователя и немедленно проверяет правило",
    ),
    SimScenario(
        code="privileged_role_assigned",
        name="Назначение привилегированной роли",
        severity="high",
        data_source="postgres",
        description="Назначение роли с флагом is_privileged",
        how="Создаёт запись role_assign с is_privileged=true и проверяет правило",
    ),
    SimScenario(
        code="audit_log_tampering_attempt",
        name="Попытка изменить журнал аудита",
        severity="critical",
        data_source="postgres",
        description="Попытка UPDATE/DELETE в таблице audit_log",
        how="Создаёт запись operation=delete, target_type=system, details.table=audit_log",
    ),
    SimScenario(
        code="admin_password_reset",
        name="Сброс пароля администратора",
        severity="high",
        data_source="postgres",
        description="Сброс пароля пользователя с привилегированной ролью",
        how="Создаёт запись password_reset с target_is_privileged=true",
    ),
    SimScenario(
        code="login_outside_hours",
        name="Вход в нерабочее время",
        severity="medium",
        data_source="elasticsearch",
        description="Успешный вход с 22:00 до 06:00",
        how="Создаёт alert напрямую (данные в ES могут появиться позже через outbox)",
    ),
    SimScenario(
        code="mass_permission_failures",
        name="Массовые отказы в доступе",
        severity="medium",
        data_source="elasticsearch",
        description="10+ отказов в доступе за 5 минут от одного пользователя",
        how="Создаёт 12 записей permission_check/denied в audit_log и alert напрямую",
    ),
    SimScenario(
        code="bulk_user_changes",
        name="Массовые изменения учётных записей",
        severity="medium",
        data_source="elasticsearch",
        description="20+ операций изменения за 10 минут от одного администратора",
        how="Создаёт 25 записей изменений пользователей и alert напрямую",
    ),
    SimScenario(
        code="inactive_user_login",
        name="Вход под неактивной учётной записью",
        severity="high",
        data_source="elasticsearch",
        description="Вход под записью без активности более 90 дней",
        how="Создаёт alert напрямую с указанием тестового пользователя",
    ),
    SimScenario(
        code="unusual_geo_login",
        name="Вход с нового IP-адреса",
        severity="high",
        data_source="elasticsearch",
        description="Вход с IP из необычной страны (не из истории)",
        how="Создаёт alert напрямую с новым IP-адресом",
    ),
    SimScenario(
        code="data_exfiltration_pattern",
        name="Признаки массовой выгрузки данных",
        severity="high",
        data_source="elasticsearch",
        description="Массовое чтение документов одним пользователем за короткий период",
        how="Создаёт 150 записей чтения ресурсов и alert напрямую",
    ),
]

SCENARIOS_MAP = {s.code: s for s in SCENARIOS}


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_rule(db: AsyncSession, code: str) -> AlertRule:
    rule = (await db.execute(select(AlertRule).where(AlertRule.code == code))).scalar_one_or_none()
    if not rule:
        raise HTTPException(
            status_code=404,
            detail=f"Правило '{code}' не найдено в БД. Выполните alembic upgrade head.",
        )
    return rule


def _sim_username() -> str:
    return f"sim_user_{uuid4().hex[:6]}"


def _make_audit(
    *,
    operation: AuditOperation,
    module: AuditModule,
    target_type: AuditTargetType,
    actor_username: str,
    result: AuditResult = AuditResult.success,
    details: dict | None = None,
    ts: datetime | None = None,
    correlation_id: "UUID | None" = None,
) -> AuditLog:
    from uuid import UUID as _UUID
    return AuditLog(
        event_id=uuid4(),
        timestamp=ts or datetime.now(timezone.utc),
        actor_username=actor_username,
        target_type=target_type,
        target_id=str(uuid4())[:8],
        operation=operation,
        module=module,
        result=result,
        ip_address=f"10.99.{random.randint(1,254)}.{random.randint(1,254)}",
        user_agent="ThreatSimulator/1.0",
        details=details,
        correlation_id=correlation_id if correlation_id is not None else uuid4(),
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/scenarios", response_model=list[SimScenario])
async def list_scenarios():
    """Список всех сценариев симуляции угроз."""
    return SCENARIOS


@router.post(
    "/run/{rule_code}",
    response_model=SimResult,
    dependencies=[require_roles(*_ALLOWED)],
)
async def run_simulation(
    rule_code: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_admin: Annotated[AdminUser, Depends(get_current_admin)],
) -> SimResult:
    """Запустить симуляцию для конкретного правила."""
    if rule_code not in SCENARIOS_MAP:
        raise HTTPException(status_code=404, detail=f"Сценарий '{rule_code}' не найден")
    rule = await _get_rule(db, rule_code)
    actor = current_admin.username

    if rule_code == "multiple_failed_logins":
        return await _sim_multiple_failed_logins(db, rule, actor)
    elif rule_code == "privileged_role_assigned":
        return await _sim_privileged_role(db, rule, actor)
    elif rule_code == "audit_log_tampering_attempt":
        return await _sim_tampering(db, rule, actor)
    elif rule_code == "admin_password_reset":
        return await _sim_password_reset(db, rule, actor)
    elif rule_code == "mass_permission_failures":
        return await _sim_mass_permission_failures(db, rule, actor)
    elif rule_code == "bulk_user_changes":
        return await _sim_bulk_user_changes(db, rule, actor)
    else:
        # ES-based rules that need no prior data: create alert directly
        return await _sim_es_direct(db, rule, rule_code, actor)


@router.post(
    "/run-all",
    response_model=list[SimResult],
    dependencies=[require_roles(*_ALLOWED)],
)
async def run_all_simulations(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_admin: Annotated[AdminUser, Depends(get_current_admin)],
) -> list[SimResult]:
    """Запустить все 10 сценариев последовательно."""
    results = []
    for scenario in SCENARIOS:
        try:
            result = await run_simulation(scenario.code, db, current_admin)
            results.append(result)
        except Exception as exc:
            results.append(SimResult(
                scenario_code=scenario.code,
                success=False,
                message=str(exc),
            ))
    return results


# ── Simple rule simulations ───────────────────────────────────────────────────

async def _sim_multiple_failed_logins(db: AsyncSession, rule: AlertRule, actor: str) -> SimResult:
    username = _sim_username()
    threshold = rule.condition_config.get("threshold", 5)
    shared_corr = uuid4()  # все события одной атаки — одна цепочка
    entries = [
        _make_audit(
            operation=AuditOperation.login_failure,
            module=AuditModule.auth,
            target_type=AuditTargetType.system,
            actor_username=username,
            result=AuditResult.failure,
            correlation_id=shared_corr,
        )
        for _ in range(threshold + 1)
    ]
    db.add_all(entries)
    await db.flush()

    # Evaluate rule against the last entry
    from app.modules.monitor.rules import check_multiple_failed_logins
    match = await check_multiple_failed_logins(db, rule.condition_config, entries[-1])
    if not match.matched:
        return SimResult(
            scenario_code=rule.code, success=False,
            message="Правило не сработало — проверьте threshold в condition_config",
            audit_entries_created=len(entries),
        )
    alert = await alert_service.fire_alert(
        db, rule, subject_user_id=None,
        details={**match.details, "simulated_by": actor},
        correlation_id=entries[-1].correlation_id,
    )
    return SimResult(
        scenario_code=rule.code, success=True,
        alert_id=str(alert.id) if alert else None,
        alert_severity=rule.severity.value,
        message=f"Создано {len(entries)} записей login_failure для '{username}', правило сработало",
        audit_entries_created=len(entries),
    )


async def _sim_privileged_role(db: AsyncSession, rule: AlertRule, actor: str) -> SimResult:
    entry = _make_audit(
        operation=AuditOperation.role_assign,
        module=AuditModule.access,
        target_type=AuditTargetType.role,
        actor_username=actor,
        details={"role_code": "system_admin", "is_privileged": True, "simulated_by": actor},
    )
    db.add(entry)
    await db.flush()

    from app.modules.monitor.rules import check_privileged_role_assigned
    match = await check_privileged_role_assigned(db, rule.condition_config, entry)
    if not match.matched:
        return SimResult(
            scenario_code=rule.code, success=False,
            message="Правило не сработало",
            audit_entries_created=1,
        )
    alert = await alert_service.fire_alert(
        db, rule,
        details={**match.details, "simulated_by": actor},
        correlation_id=entry.correlation_id,
    )
    return SimResult(
        scenario_code=rule.code, success=True,
        alert_id=str(alert.id) if alert else None,
        alert_severity=rule.severity.value,
        message=f"Запись role_assign(is_privileged=true) создана от '{actor}', правило сработало",
        audit_entries_created=1,
    )


async def _sim_tampering(db: AsyncSession, rule: AlertRule, actor: str) -> SimResult:
    entry = _make_audit(
        operation=AuditOperation.delete,
        module=AuditModule.monitor,
        target_type=AuditTargetType.system,
        actor_username=actor,
        result=AuditResult.denied,
        details={"table": "audit_log", "simulated_by": actor},
    )
    db.add(entry)
    await db.flush()

    from app.modules.monitor.rules import check_audit_log_tampering
    match = await check_audit_log_tampering(db, rule.condition_config, entry)
    if not match.matched:
        return SimResult(
            scenario_code=rule.code, success=False,
            message="Правило не сработало",
            audit_entries_created=1,
        )
    alert = await alert_service.fire_alert(
        db, rule,
        details={**match.details, "simulated_by": actor},
        correlation_id=entry.correlation_id,
    )
    return SimResult(
        scenario_code=rule.code, success=True,
        alert_id=str(alert.id) if alert else None,
        alert_severity=rule.severity.value,
        message=f"Попытка удаления audit_log зафиксирована от '{actor}', правило сработало",
        audit_entries_created=1,
    )


async def _sim_password_reset(db: AsyncSession, rule: AlertRule, actor: str) -> SimResult:
    target_user = _sim_username()
    entry = _make_audit(
        operation=AuditOperation.password_reset,
        module=AuditModule.identity,
        target_type=AuditTargetType.user,
        actor_username=actor,
        details={"target_is_privileged": True, "target_user": target_user, "simulated_by": actor},
    )
    db.add(entry)
    await db.flush()

    from app.modules.monitor.rules import check_admin_password_reset
    match = await check_admin_password_reset(db, rule.condition_config, entry)
    if not match.matched:
        return SimResult(
            scenario_code=rule.code, success=False,
            message="Правило не сработало",
            audit_entries_created=1,
        )
    alert = await alert_service.fire_alert(
        db, rule,
        details={**match.details, "simulated_by": actor},
        correlation_id=entry.correlation_id,
    )
    return SimResult(
        scenario_code=rule.code, success=True,
        alert_id=str(alert.id) if alert else None,
        alert_severity=rule.severity.value,
        message=f"Сброс пароля привилегированного пользователя '{target_user}' от '{actor}', правило сработало",
        audit_entries_created=1,
    )


async def _sim_mass_permission_failures(db: AsyncSession, rule: AlertRule, actor: str) -> SimResult:
    username = _sim_username()
    count = rule.condition_config.get("threshold", 10) + 2
    entries = [
        _make_audit(
            operation=AuditOperation.permission_check,
            module=AuditModule.access,
            target_type=AuditTargetType.resource,
            actor_username=username,
            result=AuditResult.denied,
            details={"permission": "documents:write", "reason": "insufficient_role", "simulated_by": actor},
        )
        for _ in range(count)
    ]
    db.add_all(entries)
    await db.flush()

    alert = await alert_service.fire_alert(
        db, rule,
        details={
            "username": username, "count": count,
            "window_minutes": rule.condition_config.get("window_minutes", 5),
            "simulated_by": actor,
        },
        correlation_id=entries[0].correlation_id,
    )
    return SimResult(
        scenario_code=rule.code, success=True,
        alert_id=str(alert.id) if alert else None,
        alert_severity=rule.severity.value,
        message=f"Создано {count} отказов permission_check для '{username}'",
        audit_entries_created=count,
    )


async def _sim_bulk_user_changes(db: AsyncSession, rule: AlertRule, actor: str) -> SimResult:
    count = rule.condition_config.get("threshold", 20) + 5
    operations = [AuditOperation.create, AuditOperation.update, AuditOperation.block, AuditOperation.suspend]
    entries = [
        _make_audit(
            operation=random.choice(operations),
            module=AuditModule.identity,
            target_type=AuditTargetType.user,
            actor_username=actor,
            details={"simulated_by": actor, "index": i},
        )
        for i in range(count)
    ]
    db.add_all(entries)
    await db.flush()

    alert = await alert_service.fire_alert(
        db, rule,
        details={
            "admin": actor, "count": count,
            "window_minutes": rule.condition_config.get("window_minutes", 10),
            "simulated_by": actor,
        },
        correlation_id=entries[0].correlation_id,
    )
    return SimResult(
        scenario_code=rule.code, success=True,
        alert_id=str(alert.id) if alert else None,
        alert_severity=rule.severity.value,
        message=f"Создано {count} операций изменения учётных записей от '{actor}'",
        audit_entries_created=count,
    )


# ── ES-rule direct alert ──────────────────────────────────────────────────────

_ES_DETAILS: dict[str, dict] = {
    "login_outside_hours": {
        "username": "sim_nightowl",
        "hour": 23,
        "count": 3,
        "note": "Вход в 23:00 — нерабочее время",
    },
    "inactive_user_login": {
        "username": "sim_ghost_user",
        "inactive_days": 120,
        "note": "Последний вход был 120 дней назад",
    },
    "unusual_geo_login": {
        "username": "sim_traveler",
        "new_ips": ["185.220.101.42", "194.165.16.53"],
        "note": "IP не встречались в истории последних 30 дней",
    },
    "data_exfiltration_pattern": {
        "username": "sim_exfiltrator",
        "read_count": 157,
        "window_minutes": 30,
        "note": "157 операций чтения ресурсов за 30 минут",
    },
}


async def _sim_es_direct(db: AsyncSession, rule: AlertRule, code: str, actor: str) -> SimResult:
    details = {**_ES_DETAILS.get(code, {}), "simulated_by": actor, "note": "Симуляция — данные в ES могут появиться позже"}
    alert = await alert_service.fire_alert(db, rule, details=details)
    # Alert may be None if cooldown is active
    if alert is None:
        return SimResult(
            scenario_code=code, success=False,
            message=f"Alert не создан — активен cooldown ({rule.cooldown_seconds}s). Подождите или сбросьте cooldown.",
        )
    return SimResult(
        scenario_code=code, success=True,
        alert_id=str(alert.id),
        alert_severity=rule.severity.value,
        message=f"Alert создан напрямую (ES-правило). {details.get('note', '')}",
        audit_entries_created=0,
    )
