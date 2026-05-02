from celery import Celery
from app.config import settings

celery_app = Celery(
    "accessguard",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=[
        "app.modules.identity.tasks",
        "app.modules.monitor.tasks",
        "app.modules.reports.tasks",
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
        "monitor-publish-outbox": {
            "task": "monitor.publish_outbox",
            "schedule": 10,  # каждые 10 секунд
        },
        "monitor-evaluate-complex-rules": {
            "task": "monitor.evaluate_complex_rules",
            "schedule": 60,
        },
        "reports-check-schedules": {
            "task": "reports.check_schedules",
            "schedule": 60,  # каждую минуту
        },
    },
)
