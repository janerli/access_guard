import asyncio
import json
from typing import Awaitable, Callable

import structlog
from aiokafka import AIOKafkaConsumer

from app.config import settings
from app.kafka.events import KafkaEvent

logger = structlog.get_logger()

_MAX_RETRIES = 3
_RETRY_DELAY = 2  # seconds


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
            # Коммитим offset ТОЛЬКО после успешной обработки. При ошибке —
            # ретраим то же сообщение до _MAX_RETRIES раз, не продвигая offset.
            # Если сообщение «ядовитое» (стабильно падает) — логируем CRITICAL
            # с полным payload и коммитим, чтобы не застрять навсегда.
            # Дедупликация на стороне handler делает повторную доставку безопасной.
            processed = False
            for attempt in range(1, _MAX_RETRIES + 1):
                try:
                    event = KafkaEvent(**msg.value)
                    await handler(event)
                    await consumer.commit()
                    processed = True
                    logger.debug("kafka_message_processed", topic=topic, event_type=event.event_type)
                    break
                except Exception as exc:
                    logger.error(
                        "kafka_message_failed",
                        topic=topic,
                        offset=msg.offset,
                        attempt=attempt,
                        max_retries=_MAX_RETRIES,
                        error=str(exc),
                        exc_info=True,
                    )
                    if attempt < _MAX_RETRIES:
                        await asyncio.sleep(_RETRY_DELAY)

            if not processed:
                # Poison message — не теряем тихо: логируем как CRITICAL с payload,
                # затем коммитим, чтобы консьюмер не застрял на нём бесконечно.
                logger.critical(
                    "kafka_message_poison_skipped",
                    topic=topic,
                    offset=msg.offset,
                    partition=msg.partition,
                    payload=msg.value,
                )
                await consumer.commit()
    finally:
        await consumer.stop()
        logger.info("kafka_consumer_stopped", topic=topic)
