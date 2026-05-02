"""Kafka consumer runner — отдельный процесс, подписанный на топики."""
import asyncio

import structlog

logger = structlog.get_logger()


async def main() -> None:
    logger.info("kafka_runner_starting")
    from app.modules.identity.consumer import run_hr_consumer
    from app.modules.access.consumer import run_identity_user_consumer

    from app.modules.monitor.tasks import publish_outbox as _outbox_beat

    async def outbox_loop() -> None:
        while True:
            try:
                _outbox_beat.delay()
            except Exception:
                pass
            await asyncio.sleep(10)

    await asyncio.gather(
        run_hr_consumer(),
        run_identity_user_consumer(),
        outbox_loop(),
    )


if __name__ == "__main__":
    asyncio.run(main())
