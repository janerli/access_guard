"""notification_service — sends alerts through configured channels."""
import json
import logging
import smtplib
from email.mime.text import MIMEText

import httpx

from app.config import settings
from app.models.monitor import Alert, AlertRule, NotificationChannel, NotificationChannelType

logger = logging.getLogger(__name__)


async def send(alert: "Alert", rule: "AlertRule", channels: list["NotificationChannel"]) -> None:
    for channel in channels:
        if not channel.is_enabled:
            continue
        try:
            if channel.type == NotificationChannelType.email:
                await _send_email(alert, rule, channel)
            elif channel.type == NotificationChannelType.webhook:
                await _send_webhook(alert, rule, channel)
            elif channel.type == NotificationChannelType.log:
                _send_log(alert, rule, channel)
            elif channel.type == NotificationChannelType.kafka:
                await _send_kafka(alert, rule, channel)
        except Exception as exc:
            logger.error("notification_failed", channel=channel.code, error=str(exc))


async def _send_email(alert: "Alert", rule: "AlertRule", channel: "NotificationChannel") -> None:
    to_addr = channel.config.get("to", "security@accessguard.local")
    subject = f"[AccessGuard] {rule.severity.value.upper()}: {rule.name}"
    body = (
        f"Сработало правило: {rule.name}\n"
        f"Severity: {alert.severity.value}\n"
        f"Время: {alert.triggered_at}\n"
        f"Детали: {json.dumps(alert.details, ensure_ascii=False, indent=2)}\n"
    )
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = settings.SMTP_FROM
    msg["To"] = to_addr
    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=5) as smtp:
            smtp.sendmail(settings.SMTP_FROM, [to_addr], msg.as_string())
    except Exception as exc:
        logger.warning("smtp_send_failed", error=str(exc))


async def _send_webhook(alert: "Alert", rule: "AlertRule", channel: "NotificationChannel") -> None:
    url = channel.config.get("url")
    if not url:
        return
    payload = {
        "alert_id": str(alert.id),
        "rule_code": rule.code,
        "severity": alert.severity.value,
        "triggered_at": alert.triggered_at.isoformat(),
        "details": alert.details,
    }
    async with httpx.AsyncClient(timeout=5.0) as client:
        await client.post(url, json=payload)


def _send_log(alert: "Alert", rule: "AlertRule", channel: "NotificationChannel") -> None:
    log_path = channel.config.get("path", "/var/log/accessguard/alerts.log")
    line = (
        f"{alert.triggered_at.isoformat()} "
        f"[{alert.severity.value.upper()}] {rule.code}: {rule.name} "
        f"details={json.dumps(alert.details)}\n"
    )
    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(line)
    except OSError:
        logger.warning("alert_log_write_failed", path=log_path)


async def _send_kafka(alert: "Alert", rule: "AlertRule", channel: "NotificationChannel") -> None:
    from app.kafka.events import KafkaEvent
    from app.kafka.producer import publish_event

    topic = channel.config.get("topic", "monitor.alerts")
    event = KafkaEvent(
        event_type="alert.triggered",
        producer="monitor",
        payload={
            "alert_id": str(alert.id),
            "rule_code": rule.code,
            "severity": alert.severity.value,
            "triggered_at": alert.triggered_at.isoformat(),
            "details": alert.details,
        },
    )
    await publish_event(topic, event)
