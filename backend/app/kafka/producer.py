import json
from contextlib import asynccontextmanager
from typing import AsyncIterator, Optional

import structlog
from aiokafka import AIOKafkaProducer

from app.config import settings
from app.kafka.events import KafkaEvent

logger = structlog.get_logger()

_producer: Optional[AIOKafkaProducer] = None


async def get_producer() -> AIOKafkaProducer:
    global _producer
    if _producer is None:
        _producer = AIOKafkaProducer(
            bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
            acks="all",
            enable_idempotence=True,
            value_serializer=lambda v: json.dumps(v, default=str).encode("utf-8"),
            key_serializer=lambda k: k.encode("utf-8") if k else None,
        )
        await _producer.start()
        logger.info("kafka_producer_started")
    return _producer


async def publish_event(
    topic: str,
    event: KafkaEvent,
    key: Optional[str] = None,
) -> None:
    producer = await get_producer()
    await producer.send(
        topic,
        value=event.model_dump(mode="json"),
        key=key,
    )
    logger.info("kafka_published", topic=topic, event_type=event.event_type, event_id=str(event.event_id))


@asynccontextmanager
async def task_producer() -> AsyncIterator[AIOKafkaProducer]:
    """Fresh producer for Celery tasks.

    Each asyncio.run() creates a new event loop, so the module-level
    _producer singleton would be bound to a dead loop. Use this context
    manager instead — it creates, starts, and stops its own producer.
    """
    producer = AIOKafkaProducer(
        bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
        acks="all",
        enable_idempotence=True,
        value_serializer=lambda v: json.dumps(v, default=str).encode("utf-8"),
        key_serializer=lambda k: k.encode("utf-8") if k else None,
    )
    await producer.start()
    try:
        yield producer
    finally:
        await producer.stop()


async def close_producer() -> None:
    global _producer
    if _producer:
        await _producer.stop()
        _producer = None
        logger.info("kafka_producer_stopped")
