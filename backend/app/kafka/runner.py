"""Kafka consumer runner — отдельный процесс, подписанный на топики."""
import asyncio

import structlog

logger = structlog.get_logger()


async def main() -> None:
    logger.info("kafka_runner_starting")
    from app.modules.identity.consumer import run_hr_consumer
    from app.modules.access.consumer import run_identity_user_consumer

    # outbox-публикацию диспатчит Celery beat (monitor.publish_outbox каждые 10с).
    # Дублирующий outbox_loop здесь приводил к двойной частоте и конкурентной
    # обработке одних и тех же pending-строк — убран.
    await asyncio.gather(
        run_hr_consumer(),
        run_identity_user_consumer(),
    )


if __name__ == "__main__":
    asyncio.run(main())
