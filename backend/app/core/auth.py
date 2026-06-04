from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from pydantic import BaseModel
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
        # Оценка правил — через Celery ПОСЛЕ коммита (не fire-and-forget ensure_future,
        # который привязан к временному event loop и может быть отменён GC).
        try:
            from app.modules.monitor.tasks import evaluate_simple_rules
            evaluate_simple_rules.apply_async(args=[audit_id], countdown=1)
        except Exception:
            pass
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
        secure=settings.COOKIE_SECURE,
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

    # Проверка denylist — отозванный (logout/ротация) токен использовать нельзя
    from app.core import token_denylist
    if await token_denylist.is_revoked(payload.get("jti")):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Токен отозван")

    user_id = payload.get("sub")
    result = await db.execute(
        select(AdminUser).where(AdminUser.id == user_id, AdminUser.is_active.is_(True))
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Пользователь не найден")

    # Ротация: отзываем старый refresh-токен, чтобы его нельзя было переиспользовать
    await token_denylist.revoke(payload.get("jti"), payload.get("exp"))

    new_access = create_access_token(str(user.id), user.role)
    new_refresh = create_refresh_token(str(user.id))

    response.set_cookie(
        key="refresh_token",
        value=new_refresh,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="lax",
        max_age=settings.JWT_REFRESH_TTL_DAYS * 86400,
        path="/api/auth",
    )

    return TokenResponse(access_token=new_access)


@router.post("/logout")
async def logout(
    response: Response,
    refresh_token: Annotated[str | None, Cookie()] = None,
):
    # Реальный logout: заносим jti refresh-токена в denylist, чтобы он
    # перестал работать на стороне сервера (а не только удаляем cookie).
    if refresh_token:
        try:
            payload = decode_token(refresh_token)
            if payload.get("type") == "refresh":
                from app.core import token_denylist
                await token_denylist.revoke(payload.get("jti"), payload.get("exp"))
        except ValueError:
            pass
    response.delete_cookie("refresh_token", path="/api/auth")
    return {"detail": "Выход выполнен"}


@router.get("/me", response_model=AdminUserOut)
async def me(current: CurrentAdmin):
    return current


class ChangePasswordBody(BaseModel):
    current_password: str
    new_password: str


@router.patch("/me/password", response_model=AdminUserOut)
async def change_password(
    body: ChangePasswordBody,
    current: CurrentAdmin,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    from app.core.security import hash_password, validate_password_strength
    if not verify_password(body.current_password, current.hashed_password):
        raise HTTPException(status_code=400, detail="Текущий пароль неверен")
    try:
        validate_password_strength(body.new_password)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    result = await db.execute(select(AdminUser).where(AdminUser.id == current.id))
    user = result.scalar_one()
    user.hashed_password = hash_password(body.new_password)
    await db.commit()
    await db.refresh(user)
    return user


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
