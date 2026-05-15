"""Data collectors for report generators."""
from datetime import datetime, timedelta, timezone
from typing import Any

import structlog
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger()


class PostgresCollector:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def users_report(self, parameters: dict) -> dict:
        from app.models.identity import UserExt, Department, Position
        from sqlalchemy.orm import selectinload

        q = select(UserExt).options(
            selectinload(UserExt.position),
            selectinload(UserExt.department),
        )
        if parameters.get("status"):
            from app.models.identity import UserStatus
            q = q.where(UserExt.status == UserStatus(parameters["status"]))
        if parameters.get("department_id"):
            q = q.where(UserExt.department_id == parameters["department_id"])
        if parameters.get("position_id"):
            q = q.where(UserExt.position_id == parameters["position_id"])
        rows = (await self.db.execute(q.order_by(UserExt.full_name))).scalars().all()
        return {
            "title": "Список пользователей",
            "headers": ["ФИО", "Логин", "Email", "Должность", "Отдел", "Статус"],
            "rows": [
                [
                    u.full_name, u.username, u.email,
                    u.position.name if u.position else "—",
                    u.department.name if u.department else "—",
                    u.status.value,
                ]
                for u in rows
            ],
            "count": len(rows),
        }

    async def roles_matrix(self, parameters: dict) -> dict:
        from app.models.identity import UserExt, Department
        from app.models.access import UserRole, Role
        from sqlalchemy.orm import selectinload

        q = (
            select(UserExt, UserRole, Role)
            .join(UserRole, UserRole.user_id == UserExt.id, isouter=True)
            .join(Role, Role.id == UserRole.role_id, isouter=True)
            .options(selectinload(UserExt.department))
        )
        if parameters.get("department_id"):
            q = q.where(UserExt.department_id == parameters["department_id"])
        rows = (await self.db.execute(q)).all()

        matrix: dict[str, dict[str, list[str]]] = {}
        for user, user_role, role in rows:
            dept = user.department.name if user.department else "Без отдела"
            if dept not in matrix:
                matrix[dept] = {}
            if user.full_name not in matrix[dept]:
                matrix[dept][user.full_name] = []
            if role:
                matrix[dept][user.full_name].append(role.name)

        data_rows = []
        for dept, users in matrix.items():
            for user_name, roles in users.items():
                data_rows.append([dept, user_name, ", ".join(roles) or "—"])

        return {
            "title": "Матрица ролей",
            "headers": ["Отдел", "Сотрудник", "Роли"],
            "rows": data_rows,
            "count": len(data_rows),
        }

    async def access_requests_report(self, parameters: dict) -> dict:
        from app.models.access import AccessRequest, Role
        from app.models.identity import UserExt
        from sqlalchemy.orm import selectinload

        q = (
            select(AccessRequest)
            .options(selectinload(AccessRequest.role))
            .order_by(AccessRequest.created_at.desc())
        )
        if parameters.get("date_from"):
            q = q.where(AccessRequest.created_at >= datetime.fromisoformat(parameters["date_from"]))
        if parameters.get("date_to"):
            q = q.where(AccessRequest.created_at <= datetime.fromisoformat(parameters["date_to"]))
        if parameters.get("status"):
            from app.models.access import AccessRequestStatus
            q = q.where(AccessRequest.status == AccessRequestStatus(parameters["status"]))

        rows = (await self.db.execute(q)).scalars().all()
        return {
            "title": "Заявки на доступ",
            "headers": ["ID", "Роль", "Статус", "Дата создания", "Дата решения", "Обоснование"],
            "rows": [
                [
                    str(r.id)[:8],
                    r.role.name if r.role else str(r.role_id)[:8],
                    r.status.value,
                    r.created_at.strftime("%Y-%m-%d %H:%M") if r.created_at else "—",
                    r.decided_at.strftime("%Y-%m-%d %H:%M") if r.decided_at else "—",
                    (r.justification or "")[:80],
                ]
                for r in rows
            ],
            "count": len(rows),
        }

    async def permissions_audit(self, parameters: dict) -> dict:
        from app.models.monitor import AuditLog, AuditOperation
        from sqlalchemy import and_, cast, String

        q = select(AuditLog).where(
            AuditLog.operation == AuditOperation.role_assign,
            AuditLog.details.isnot(None),
        ).order_by(AuditLog.timestamp.desc()).limit(5000)
        if parameters.get("date_from"):
            q = q.where(AuditLog.timestamp >= datetime.fromisoformat(parameters["date_from"]))
        if parameters.get("date_to"):
            q = q.where(AuditLog.timestamp <= datetime.fromisoformat(parameters["date_to"]))

        rows = (await self.db.execute(q)).scalars().all()
        privileged = [
            r for r in rows
            if (r.details or {}).get("is_privileged") is True
        ]
        return {
            "title": "Аудит привилегированных ролей",
            "headers": ["Время", "Администратор", "Объект", "Роль", "Результат"],
            "rows": [
                [
                    r.timestamp.strftime("%Y-%m-%d %H:%M") if r.timestamp else "—",
                    r.actor_username,
                    r.target_id,
                    (r.details or {}).get("role_code", "—"),
                    r.result.value,
                ]
                for r in privileged
            ],
            "count": len(privileged),
        }

    async def compliance_pg_part(self, parameters: dict) -> dict:
        from app.models.identity import UserExt, UserStatus
        from app.models.access import Role, UserRole
        from app.models.monitor import Alert, AlertStatus

        total_users = (await self.db.execute(select(func.count(UserExt.id)))).scalar_one()
        active_users = (await self.db.execute(
            select(func.count(UserExt.id)).where(UserExt.status == UserStatus.active)
        )).scalar_one()
        blocked_users = (await self.db.execute(
            select(func.count(UserExt.id)).where(UserExt.status == UserStatus.blocked)
        )).scalar_one()
        open_alerts = (await self.db.execute(
            select(func.count(Alert.id)).where(Alert.status == AlertStatus.new)
        )).scalar_one()
        total_roles = (await self.db.execute(select(func.count(Role.id)))).scalar_one()

        return {
            "total_users": total_users,
            "active_users": active_users,
            "blocked_users": blocked_users,
            "open_alerts": open_alerts,
            "total_roles": total_roles,
        }


class ElasticCollector:
    def __init__(self, es: Any):
        self.es = es

    async def audit_summary(self, parameters: dict) -> dict:
        date_from = parameters.get("date_from", (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%d"))
        date_to = parameters.get("date_to", datetime.now(timezone.utc).strftime("%Y-%m-%d"))
        try:
            resp = await self.es.search(
                index="audit-events-*",
                body={
                    "query": {"range": {"@timestamp": {"gte": date_from, "lte": date_to}}},
                    "aggs": {
                        "by_module": {"terms": {"field": "module.keyword", "size": 10}},
                        "by_operation": {"terms": {"field": "operation.keyword", "size": 20}},
                        "by_result": {"terms": {"field": "result.keyword", "size": 5}},
                        "by_day": {"date_histogram": {"field": "@timestamp", "calendar_interval": "day"}},
                    },
                    "size": 0,
                },
            )
            aggs = resp.get("aggregations", {})
            rows = []
            for bucket in aggs.get("by_operation", {}).get("buckets", []):
                rows.append([bucket["key"], bucket["doc_count"]])

            return {
                "title": f"Сводка по аудиту ({date_from} — {date_to})",
                "headers": ["Операция", "Количество"],
                "rows": rows,
                "count": resp["hits"]["total"]["value"],
                "by_module": {b["key"]: b["doc_count"] for b in aggs.get("by_module", {}).get("buckets", [])},
                "by_result": {b["key"]: b["doc_count"] for b in aggs.get("by_result", {}).get("buckets", [])},
            }
        except Exception as exc:
            logger.warning("audit_summary_es_failed", error=str(exc))
            return {
                "title": "Сводка по аудиту (ES недоступен)",
                "headers": ["Операция", "Количество"],
                "rows": [],
                "count": 0,
            }

    async def inactive_users(self, parameters: dict) -> dict:
        inactive_days = parameters.get("inactive_days", 90)
        threshold = (datetime.now(timezone.utc) - timedelta(days=inactive_days)).isoformat()
        try:
            resp = await self.es.search(
                index="audit-events-*",
                body={
                    "query": {"range": {"@timestamp": {"gte": threshold}}},
                    "aggs": {"active_users": {"terms": {"field": "actor_username.keyword", "size": 10000}}},
                    "size": 0,
                },
            )
            active = {b["key"] for b in resp["aggregations"]["active_users"]["buckets"]}

            all_resp = await self.es.search(
                index="audit-events-*",
                body={"aggs": {"all_users": {"terms": {"field": "actor_username.keyword", "size": 10000}}}, "size": 0},
            )
            all_users = {b["key"] for b in all_resp["aggregations"]["all_users"]["buckets"]}
            inactive = all_users - active
            rows = [[u, f"> {inactive_days} дней"] for u in sorted(inactive)]
            return {
                "title": f"Неактивные пользователи (>{inactive_days} дней)",
                "headers": ["Пользователь", "Бездействие"],
                "rows": rows,
                "count": len(rows),
            }
        except Exception as exc:
            logger.warning("inactive_users_es_failed", error=str(exc))
            return {
                "title": "Неактивные пользователи (ES недоступен)",
                "headers": ["Пользователь", "Бездействие"],
                "rows": [],
                "count": 0,
            }

    async def compliance_es_part(self, parameters: dict) -> dict:
        date_from = parameters.get("date_from", (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%d"))
        date_to = parameters.get("date_to", datetime.now(timezone.utc).strftime("%Y-%m-%d"))
        try:
            resp = await self.es.search(
                index="audit-events-*",
                body={
                    "query": {"range": {"@timestamp": {"gte": date_from, "lte": date_to}}},
                    "aggs": {"by_result": {"terms": {"field": "result.keyword", "size": 5}}},
                    "size": 0,
                },
            )
            by_result = {b["key"]: b["doc_count"] for b in resp["aggregations"]["by_result"]["buckets"]}
            return {"total_audit_events": resp["hits"]["total"]["value"], "by_result": by_result}
        except Exception as exc:
            logger.warning("compliance_es_part_failed", error=str(exc))
            return {"total_audit_events": 0, "by_result": {}}
