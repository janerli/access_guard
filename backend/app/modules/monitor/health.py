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
    celery_tasks_in_redis: int
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

    # Elasticsearch — create a fresh client per health check to avoid
    # stale singleton connections and event-loop issues.
    es_status = ServiceStatus(status="down")
    try:
        from elasticsearch import AsyncElasticsearch
        from app.config import settings as _s
        _es = AsyncElasticsearch(
            hosts=[_s.ELASTICSEARCH_URL],
            request_timeout=3,
            max_retries=1,
            retry_on_timeout=False,
        )
        t0 = time.monotonic()
        info = await _es.cluster.health(timeout="3s")
        es_latency = round((time.monotonic() - t0) * 1000, 2)
        await _es.close()
        cluster_status = info.get("status", "red")
        if cluster_status == "green":
            es_status = ServiceStatus(status="ok", latency_ms=es_latency)
        elif cluster_status == "yellow":
            es_status = ServiceStatus(status="degraded", latency_ms=es_latency)
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

    # Outbox stats — use explicit select_from so SQLAlchemy can build the query
    outbox_pending = 0
    outbox_failed = 0
    try:
        from sqlalchemy import select, func
        from app.models.monitor import OutboxEvent, OutboxStatus
        outbox_pending = (await db.execute(
            select(func.count(OutboxEvent.id)).where(OutboxEvent.status == OutboxStatus.pending)
        )).scalar_one()
        outbox_failed = (await db.execute(
            select(func.count(OutboxEvent.id)).where(OutboxEvent.status == OutboxStatus.failed)
        )).scalar_one()
    except Exception:
        pass

    # Also report total processed today for context
    celery_workers_count = 0
    try:
        import redis.asyncio as _aioredis
        from app.config import settings as _s2
        _r2 = _aioredis.from_url(_s2.REDIS_URL, decode_responses=True)
        celery_keys = await _r2.keys("celery-task-meta-*")
        celery_workers_count = len(celery_keys)
        await _r2.aclose()
    except Exception:
        pass

    return HealthResponse(
        postgres=pg_status,
        redis=redis_status,
        elasticsearch=es_status,
        kafka=kafka_status,
        outbox_pending=outbox_pending,
        outbox_failed=outbox_failed,
        celery_tasks_in_redis=celery_workers_count,
        last_celery_beat=last_celery_beat,
        checked_at=datetime.now(timezone.utc).isoformat(),
    )
