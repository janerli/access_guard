from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.deps import CurrentAdmin, get_current_admin
from app.core.security import create_access_token, create_refresh_token, decode_token, verify_password
from app.database import get_db
from app.models.admin import AdminUser
from app.schemas.auth import AdminUserOut, LoginRequest, TokenResponse

router = APIRouter()

_MAX_FAILED = 5
_LOCK_MINUTES = 15


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(select(AdminUser).where(AdminUser.username == body.username))
    user: AdminUser | None = result.scalar_one_or_none()

    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Неверные учётные данные")

    if user.locked_until and user.locked_until > datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Аккаунт заблокирован до {user.locked_until.isoformat()}",
        )

    if not verify_password(body.password, user.hashed_password):
        user.failed_login_count += 1
        if user.failed_login_count >= _MAX_FAILED:
            user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=_LOCK_MINUTES)
            user.failed_login_count = 0
        audit_id = await _write_login_failure_audit(db, body.username)
        await db.commit()
        import asyncio
        asyncio.ensure_future(_run_evaluate_after_login(audit_id))
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Неверные учётные данные")

    user.failed_login_count = 0
    user.locked_until = None
    await db.commit()

    access_token = create_access_token(str(user.id), user.role)
    refresh_token = create_refresh_token(str(user.id))

    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=settings.JWT_REFRESH_TTL_DAYS * 86400,
        path="/api/auth",
    )

    return TokenResponse(access_token=access_token)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
    refresh_token: Annotated[str | None, Cookie()] = None,
):
    if not refresh_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh-токен отсутствует")

    try:
        payload = decode_token(refresh_token)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Недействительный refresh-токен")

    if payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Неверный тип токена")

    user_id = payload.get("sub")
    result = await db.execute(
        select(AdminUser).where(AdminUser.id == user_id, AdminUser.is_active.is_(True))
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Пользователь не найден")

    new_access = create_access_token(str(user.id), user.role)
    new_refresh = create_refresh_token(str(user.id))

    response.set_cookie(
        key="refresh_token",
        value=new_refresh,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=settings.JWT_REFRESH_TTL_DAYS * 86400,
        path="/api/auth",
    )

    return TokenResponse(access_token=new_access)


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie("refresh_token", path="/api/auth")
    return {"detail": "Выход выполнен"}


@router.get("/me", response_model=AdminUserOut)
async def me(current: CurrentAdmin):
    return current


async def _write_login_failure_audit(db: AsyncSession, username: str) -> int:
    import uuid as _uuid
    from app.models.monitor import (
        AuditLog, AuditModule, AuditOperation, AuditResult,
        AuditTargetType, OutboxEvent, OutboxStatus,
    )
    from app.kafka.topics import TOPIC_AUDIT_EVENTS

    corr = _uuid.uuid4()
    entry = AuditLog(
        event_id=_uuid.uuid4(),
        actor_id=None,
        actor_username=username,
        target_type=AuditTargetType.system,
        target_id=username,
        operation=AuditOperation.login_failure,
        module=AuditModule.identity,
        result=AuditResult.failure,
        details={"username": username},
        correlation_id=corr,
        published_to_kafka=False,
    )
    db.add(entry)
    await db.flush()
    payload = {
        "event_id": str(entry.event_id), "audit_log_id": entry.id,
        "timestamp": entry.timestamp.isoformat() if entry.timestamp else datetime.now(timezone.utc).isoformat(),
        "actor_id": None, "actor_username": username,
        "target_type": "system", "target_id": username,
        "operation": "login_failure", "module": "identity", "result": "failure",
        "details": entry.details, "correlation_id": str(corr),
    }
    db.add(OutboxEvent(audit_log_id=entry.id, topic=TOPIC_AUDIT_EVENTS, payload=payload, status=OutboxStatus.pending))
    return entry.id


async def _run_evaluate_after_login(audit_log_id: int) -> None:
    import asyncio
    await asyncio.sleep(0.5)
    try:
        from app.modules.monitor.tasks import _evaluate_simple_async
        result = await _evaluate_simple_async(audit_log_id)
        if result.get("fired", 0):
            import structlog
            structlog.get_logger().info("login_failure_alert_fired", audit_log_id=audit_log_id, fired=result["fired"])
    except Exception as exc:
        import structlog
        structlog.get_logger().warning("login_failure_evaluate_failed", error=str(exc))
