import json
from typing import Awaitable, Callable

import structlog
from aiokafka import AIOKafkaConsumer

from app.config import settings
from app.kafka.events import KafkaEvent

logger = structlog.get_logger()


async def consume_topic(
    topic: str,
    group_id: str,
    handler: Callable[[KafkaEvent], Awaitable[None]],
) -> None:
    consumer = AIOKafkaConsumer(
        topic,
        bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
        group_id=f"{settings.KAFKA_CONSUMER_GROUP_PREFIX}.{group_id}",
        auto_offset_reset="earliest",
        enable_auto_commit=False,
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
        fetch_max_bytes=1048576,
    )

    await consumer.start()
    logger.info("kafka_consumer_started", topic=topic, group_id=group_id)

    try:
        async for msg in consumer:
            try:
                event = KafkaEvent(**msg.value)
                await handler(event)
                await consumer.commit()
                logger.debug("kafka_message_processed", topic=topic, event_type=event.event_type)
            except Exception as exc:
                logger.error(
                    "kafka_message_failed",
                    topic=topic,
                    offset=msg.offset,
                    error=str(exc),
                    exc_info=True,
                )
    finally:
        await consumer.stop()
        logger.info("kafka_consumer_stopped", topic=topic)
