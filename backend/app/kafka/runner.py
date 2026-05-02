"""Kafka consumer runner — отдельный процесс, подписанный на топики."""
import asyncio

import structlog

logger = structlog.get_logger()


async def main() -> None:
    logger.info("kafka_runner_starting")
    from app.modules.identity.consumer import run_hr_consumer

    await asyncio.gather(
        run_hr_consumer(),
        # Access consumer добавляется в Этапе 4:
        # run_identity_consumer(),
    )


if __name__ == "__main__":
    asyncio.run(main())
