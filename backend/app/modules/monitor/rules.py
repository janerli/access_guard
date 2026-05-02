"""Detection rules — 4 simple (postgres) + 6 complex (elasticsearch)."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.monitor import AuditLog, AuditModule, AuditOperation, AuditResult

logger = logging.getLogger(__name__)


class RuleMatch:
    def __init__(self, matched: bool, subject_user_id: UUID | None = None, details: dict | None = None):
        self.matched = matched
        self.subject_user_id = subject_user_id
        self.details = details or {}


# ── Simple rules (postgres) ───────────────────────────────────────────────────

async def check_multiple_failed_logins(db: AsyncSession, config: dict, audit_entry: AuditLog) -> RuleMatch:
    if audit_entry.operation != AuditOperation.login_failure:
        return RuleMatch(False)
    threshold = config.get("threshold", 5)
    window = config.get("window_minutes", 15)
    since = datetime.now(timezone.utc) - timedelta(minutes=window)
    count = (await db.execute(
        select(func.count(AuditLog.id)).where(
            AuditLog.actor_username == audit_entry.actor_username,
            AuditLog.operation == AuditOperation.login_failure,
            AuditLog.timestamp >= since,
        )
    )).scalar_one()
    if count >= threshold:
        return RuleMatch(
            True,
            subject_user_id=audit_entry.actor_id,
            details={"username": audit_entry.actor_username, "count": count, "window_minutes": window},
        )
    return RuleMatch(False)


async def check_privileged_role_assigned(db: AsyncSession, config: dict, audit_entry: AuditLog) -> RuleMatch:
    if audit_entry.operation != AuditOperation.role_assign:
        return RuleMatch(False)
    details = audit_entry.details or {}
    if details.get("is_privileged"):
        return RuleMatch(
            True,
            subject_user_id=audit_entry.actor_id,
            details={"role": details.get("role_code", ""), "target_user": audit_entry.target_id},
        )
    return RuleMatch(False)


async def check_audit_log_tampering(db: AsyncSession, config: dict, audit_entry: AuditLog) -> RuleMatch:
    if audit_entry.operation in (AuditOperation.update, AuditOperation.delete) and audit_entry.target_type.value == "system":
        details = audit_entry.details or {}
        if details.get("table") == "audit_log":
            return RuleMatch(True, subject_user_id=audit_entry.actor_id, details=details)
    return RuleMatch(False)


async def check_admin_password_reset(db: AsyncSession, config: dict, audit_entry: AuditLog) -> RuleMatch:
    if audit_entry.operation != AuditOperation.password_reset:
        return RuleMatch(False)
    details = audit_entry.details or {}
    if details.get("target_is_privileged"):
        return RuleMatch(
            True,
            subject_user_id=audit_entry.actor_id,
            details={"reset_by": audit_entry.actor_username, "target_user": audit_entry.target_id},
        )
    return RuleMatch(False)


SIMPLE_RULES: dict[str, Any] = {
    "multiple_failed_logins": check_multiple_failed_logins,
    "privileged_role_assigned": check_privileged_role_assigned,
    "audit_log_tampering_attempt": check_audit_log_tampering,
    "admin_password_reset": check_admin_password_reset,
}


# ── Complex rules (elasticsearch) ────────────────────────────────────────────

async def check_login_outside_hours(es_client: Any, config: dict) -> list[RuleMatch]:
    start_hour = config.get("start_hour", 22)
    end_hour = config.get("end_hour", 6)
    now = datetime.now(timezone.utc)
    since = (now - timedelta(minutes=5)).isoformat()
    try:
        resp = await es_client.search(
            index="audit-events-*",
            body={
                "query": {
                    "bool": {
                        "must": [
                            {"term": {"operation": "login_success"}},
                            {"range": {"timestamp": {"gte": since}}},
                        ],
                        "filter": [{"script": {"script": {
                            "source": (
                                f"int h = doc['timestamp'].value.getHour(); "
                                f"return h >= {start_hour} || h < {end_hour};"
                            )
                        }}}],
                    }
                },
                "aggs": {"by_user": {"terms": {"field": "actor_username", "size": 20}}},
                "size": 0,
            },
        )
        results = []
        for bucket in resp["aggregations"]["by_user"]["buckets"]:
            results.append(RuleMatch(
                True,
                details={"username": bucket["key"], "count": bucket["doc_count"]},
            ))
        return results
    except Exception as exc:
        logger.warning("es_rule_failed", rule="login_outside_hours", error=str(exc))
        return []


async def check_mass_permission_failures(es_client: Any, config: dict) -> list[RuleMatch]:
    threshold = config.get("threshold", 10)
    window = config.get("window_minutes", 5)
    since = (datetime.now(timezone.utc) - timedelta(minutes=window)).isoformat()
    try:
        resp = await es_client.search(
            index="audit-events-*",
            body={
                "query": {
                    "bool": {"must": [
                        {"term": {"operation": "permission_check"}},
                        {"term": {"result": "denied"}},
                        {"range": {"timestamp": {"gte": since}}},
                    ]}
                },
                "aggs": {"by_user": {"terms": {"field": "actor_username", "size": 20, "min_doc_count": threshold}}},
                "size": 0,
            },
        )
        return [
            RuleMatch(True, details={"username": b["key"], "count": b["doc_count"]})
            for b in resp["aggregations"]["by_user"]["buckets"]
        ]
    except Exception as exc:
        logger.warning("es_rule_failed", rule="mass_permission_failures", error=str(exc))
        return []


async def check_bulk_user_changes(es_client: Any, config: dict) -> list[RuleMatch]:
    threshold = config.get("threshold", 20)
    window = config.get("window_minutes", 10)
    since = (datetime.now(timezone.utc) - timedelta(minutes=window)).isoformat()
    try:
        resp = await es_client.search(
            index="audit-events-*",
            body={
                "query": {
                    "bool": {"must": [
                        {"terms": {"operation": ["create", "update", "delete", "block", "suspend"]}},
                        {"term": {"target_type": "user"}},
                        {"range": {"timestamp": {"gte": since}}},
                    ]}
                },
                "aggs": {"by_actor": {"terms": {"field": "actor_username", "size": 20, "min_doc_count": threshold}}},
                "size": 0,
            },
        )
        return [
            RuleMatch(True, details={"admin": b["key"], "count": b["doc_count"]})
            for b in resp["aggregations"]["by_actor"]["buckets"]
        ]
    except Exception as exc:
        logger.warning("es_rule_failed", rule="bulk_user_changes", error=str(exc))
        return []


async def check_inactive_user_login(es_client: Any, config: dict) -> list[RuleMatch]:
    inactive_days = config.get("inactive_days", 90)
    threshold_date = (datetime.now(timezone.utc) - timedelta(days=inactive_days)).isoformat()
    since = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
    try:
        # Find users who logged in recently
        resp = await es_client.search(
            index="audit-events-*",
            body={
                "query": {"bool": {"must": [
                    {"term": {"operation": "login_success"}},
                    {"range": {"timestamp": {"gte": since}}},
                ]}},
                "aggs": {"users": {"terms": {"field": "actor_username", "size": 50}}},
                "size": 0,
            },
        )
        recent_users = [b["key"] for b in resp["aggregations"]["users"]["buckets"]]
        results = []
        for username in recent_users:
            prev_resp = await es_client.search(
                index="audit-events-*",
                body={
                    "query": {"bool": {"must": [
                        {"term": {"actor_username": username}},
                        {"term": {"operation": "login_success"}},
                        {"range": {"timestamp": {"lt": since, "gte": threshold_date}}},
                    ]}},
                    "size": 0,
                },
            )
            if prev_resp["hits"]["total"]["value"] == 0:
                results.append(RuleMatch(True, details={"username": username, "inactive_days": inactive_days}))
        return results
    except Exception as exc:
        logger.warning("es_rule_failed", rule="inactive_user_login", error=str(exc))
        return []


async def check_unusual_geo_login(es_client: Any, config: dict) -> list[RuleMatch]:
    history_days = config.get("history_days", 30)
    since_history = (datetime.now(timezone.utc) - timedelta(days=history_days)).isoformat()
    since_recent = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
    try:
        resp = await es_client.search(
            index="audit-events-*",
            body={
                "query": {"bool": {"must": [
                    {"term": {"operation": "login_success"}},
                    {"range": {"timestamp": {"gte": since_recent}}},
                ]}},
                "aggs": {"by_user": {"terms": {"field": "actor_username", "size": 20},
                    "aggs": {"ips": {"terms": {"field": "ip_address", "size": 5}}}}},
                "size": 0,
            },
        )
        results = []
        for user_bucket in resp["aggregations"]["by_user"]["buckets"]:
            username = user_bucket["key"]
            current_ips = {b["key"] for b in user_bucket["ips"]["buckets"]}
            hist_resp = await es_client.search(
                index="audit-events-*",
                body={
                    "query": {"bool": {"must": [
                        {"term": {"actor_username": username}},
                        {"term": {"operation": "login_success"}},
                        {"range": {"timestamp": {"gte": since_history, "lt": since_recent}}},
                    ]}},
                    "aggs": {"ips": {"terms": {"field": "ip_address", "size": 100}}},
                    "size": 0,
                },
            )
            known_ips = {b["key"] for b in hist_resp["aggregations"]["ips"]["buckets"]}
            new_ips = current_ips - known_ips
            if new_ips:
                results.append(RuleMatch(True, details={"username": username, "new_ips": list(new_ips)}))
        return results
    except Exception as exc:
        logger.warning("es_rule_failed", rule="unusual_geo_login", error=str(exc))
        return []


async def check_data_exfiltration(es_client: Any, config: dict) -> list[RuleMatch]:
    threshold = config.get("threshold", 100)
    window = config.get("window_minutes", 30)
    since = (datetime.now(timezone.utc) - timedelta(minutes=window)).isoformat()
    try:
        resp = await es_client.search(
            index="audit-events-*",
            body={
                "query": {"bool": {"must": [
                    {"term": {"operation": "read"}},
                    {"term": {"target_type": "resource"}},
                    {"range": {"timestamp": {"gte": since}}},
                ]}},
                "aggs": {"by_user": {"terms": {"field": "actor_username", "size": 20, "min_doc_count": threshold}}},
                "size": 0,
            },
        )
        return [
            RuleMatch(True, details={"username": b["key"], "read_count": b["doc_count"]})
            for b in resp["aggregations"]["by_user"]["buckets"]
        ]
    except Exception as exc:
        logger.warning("es_rule_failed", rule="data_exfiltration_pattern", error=str(exc))
        return []


COMPLEX_RULES: dict[str, Any] = {
    "login_outside_hours": check_login_outside_hours,
    "mass_permission_failures": check_mass_permission_failures,
    "bulk_user_changes": check_bulk_user_changes,
    "inactive_user_login": check_inactive_user_login,
    "unusual_geo_login": check_unusual_geo_login,
    "data_exfiltration_pattern": check_data_exfiltration,
}
