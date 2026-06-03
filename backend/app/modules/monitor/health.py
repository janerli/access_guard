"""System health check endpoint."""
from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Optional

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_roles
from app.database import get_db
from app.elastic.client import get_elastic_client
from app.kafka.producer import get_producer
from app.models.admin import AdminRole

router = APIRouter()

_CAN_READ = (AdminRole.system_admin, AdminRole.security_officer, AdminRole.auditor)


class ServiceStatus(BaseModel):
    status: str  # ok | degraded | down
    latency_ms: Optional[float] = None


class HealthResponse(BaseModel):
    postgres: ServiceStatus
    redis: ServiceStatus
    elasticsearch: ServiceStatus
    kafka: ServiceStatus
    outbox_pending: int
    outbox_failed: int
    last_celery_beat: Optional[str]
    checked_at: str


@router.get("/health", response_model=HealthResponse, dependencies=[require_roles(*_CAN_READ)])
async def system_health(db: AsyncSession = Depends(get_db)):
    # PostgreSQL
    pg_status = ServiceStatus(status="down")
    try:
        t0 = time.monotonic()
        await db.execute(text("SELECT 1"))
        pg_latency = round((time.monotonic() - t0) * 1000, 2)
        pg_status = ServiceStatus(status="ok", latency_ms=pg_latency)
    except Exception:
        pass

    # Redis
    redis_status = ServiceStatus(status="down")
    last_celery_beat: Optional[str] = None
    try:
        from app.config import settings
        t0 = time.monotonic()
        r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        await r.ping()
        redis_latency = round((time.monotonic() - t0) * 1000, 2)
        redis_status = ServiceStatus(status="ok", latency_ms=redis_latency)
        # Try reading celery beat last run
        beat_ts = await r.get("celery_beat_last_run")
        if beat_ts:
            last_celery_beat = beat_ts
        await r.aclose()
    except Exception:
        pass

    # Elasticsearch
    es_status = ServiceStatus(status="down")
    try:
        es = get_elastic_client()
        info = await es.cluster.health(timeout="2s")
        cluster_status = info.get("status", "red")
        if cluster_status == "green":
            es_status = ServiceStatus(status="ok")
        elif cluster_status == "yellow":
            es_status = ServiceStatus(status="degraded")
        else:
            es_status = ServiceStatus(status="down")
    except Exception:
        pass

    # Kafka
    kafka_status = ServiceStatus(status="down")
    try:
        producer = await get_producer()
        if producer:
            kafka_status = ServiceStatus(status="ok")
    except Exception:
        pass

    # Outbox stats
    outbox_pending = 0
    outbox_failed = 0
    try:
        from sqlalchemy import select, func
        from app.models.monitor import OutboxEvent, OutboxStatus
        outbox_pending = (await db.execute(
            select(func.count()).where(OutboxEvent.status == OutboxStatus.pending)
        )).scalar_one()
        outbox_failed = (await db.execute(
            select(func.count()).where(OutboxEvent.status == OutboxStatus.failed)
        )).scalar_one()
    except Exception:
        pass

    return HealthResponse(
        postgres=pg_status,
        redis=redis_status,
        elasticsearch=es_status,
        kafka=kafka_status,
        outbox_pending=outbox_pending,
        outbox_failed=outbox_failed,
        last_celery_beat=last_celery_beat,
        checked_at=datetime.now(timezone.utc).isoformat(),
    )
