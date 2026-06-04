"""Refresh-token denylist на Redis.

При logout и при ротации refresh-токена его jti заносится в denylist
с TTL = оставшийся срок жизни токена. /refresh проверяет denylist
и отклоняет отозванные токены. Это делает logout реальным
(а не только удалением cookie на клиенте) и защищает от повторного
использования украденного/ротированного токена.
"""
from __future__ import annotations

import time

import redis.asyncio as aioredis
import structlog

from app.config import settings

logger = structlog.get_logger()

_DENY_PREFIX = "revoked_jti:"


def _key(jti: str) -> str:
    return f"{_DENY_PREFIX}{jti}"


async def revoke(jti: str, exp_ts: int | None) -> None:
    """Заносит jti в denylist. TTL = время до истечения токена (или 7 дней)."""
    if not jti:
        return
    ttl = settings.JWT_REFRESH_TTL_DAYS * 86400
    if exp_ts:
        ttl = max(1, int(exp_ts - time.time()))
    try:
        r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        await r.setex(_key(jti), ttl, "1")
        await r.aclose()
    except Exception as exc:
        logger.warning("token_revoke_failed", jti=jti, error=str(exc))


async def is_revoked(jti: str | None) -> bool:
    if not jti:
        return False
    try:
        r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        exists = await r.exists(_key(jti))
        await r.aclose()
        return bool(exists)
    except Exception as exc:
        # Fail-open на доступности Redis, но логируем (для прототипа допустимо)
        logger.warning("token_denylist_check_failed", error=str(exc))
        return False
