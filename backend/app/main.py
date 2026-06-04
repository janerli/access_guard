import time
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.core.logging import configure_logging

configure_logging()
logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("accessguard_starting", version="1.0.0")
    # Инициализируем Kafka-producer на старте (в loop'е uvicorn) и корректно
    # закрываем при остановке — иначе несброшенные сообщения теряются.
    from app.kafka.producer import get_producer, close_producer
    try:
        await get_producer()
    except Exception as exc:
        logger.warning("kafka_producer_init_failed", error=str(exc))
    yield
    try:
        await close_producer()
    except Exception as exc:
        logger.warning("kafka_producer_close_failed", error=str(exc))
    logger.info("accessguard_stopping")


app = FastAPI(
    title="AccessGuard API",
    version="1.0.0",
    description="Система мониторинга и управления доступом к информационным ресурсам организации",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_logging(request: Request, call_next):
    start = time.monotonic()
    response = await call_next(request)
    duration_ms = round((time.monotonic() - start) * 1000)
    logger.info(
        "http",
        method=request.method,
        path=request.url.path,
        status=response.status_code,
        ms=duration_ms,
    )
    return response


# ── Роутеры ──────────────────────────────────────────────────────────────────
from app.core.auth import router as auth_router  # noqa: E402
from app.modules.identity.router import router as identity_router  # noqa: E402
from app.modules.access.router import router as access_router  # noqa: E402
from app.modules.monitor.router import router as monitor_router  # noqa: E402
from app.modules.reports.router import router as reports_router  # noqa: E402
from app.modules.simulation.router import router as simulation_router  # noqa: E402

app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
app.include_router(identity_router, prefix="/api/identity", tags=["identity"])
app.include_router(access_router, prefix="/api/access", tags=["access"])
app.include_router(monitor_router, prefix="/api/monitor", tags=["monitor"])
app.include_router(reports_router, prefix="/api/reports", tags=["reports"])
app.include_router(simulation_router, prefix="/api/simulation", tags=["simulation"])


@app.get("/health", tags=["system"])
async def health():
    return {"status": "ok", "version": "1.0.0"}
