from celery import Celery
from app.config import settings

celery_app = Celery(
    "accessguard",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=[
        "app.modules.identity.tasks",
        # "app.modules.access.tasks",    # Этап 4
        # "app.modules.monitor.tasks",   # Этап 5
        # "app.modules.reports.tasks",   # Этап 6
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Europe/Moscow",
    enable_utc=True,
    task_track_started=True,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    beat_schedule={
        "identity-cleanup-blocked": {
            "task": "identity.cleanup_blocked_users",
            "schedule": 86400,  # ежесуточно
        },
        "identity-reconcile-hr": {
            "task": "identity.reconcile_with_hr",
            "schedule": 86400,
        },
    },
)
