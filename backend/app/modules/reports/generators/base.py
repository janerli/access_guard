"""Base report generator and template registry."""
from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.reports import ReportFormat
from app.modules.reports.generators.renderers import CsvRenderer, PdfRenderer, XlsxRenderer


class BaseReportGenerator:
    template_code: str

    async def collect_data(
        self,
        db: AsyncSession,
        es: Any,
        parameters: dict,
    ) -> dict:
        raise NotImplementedError

    async def generate(
        self,
        db: AsyncSession,
        es: Any,
        parameters: dict,
        fmt: ReportFormat,
    ) -> bytes:
        data = await self.collect_data(db, es, parameters)
        if fmt == ReportFormat.pdf:
            return PdfRenderer().render(data)
        elif fmt == ReportFormat.xlsx:
            return XlsxRenderer().render(data)
        else:
            return CsvRenderer().render(data)


# ── Concrete generators ────────────────────────────────────────────────────────

class UsersReportGenerator(BaseReportGenerator):
    template_code = "users_report"

    async def collect_data(self, db, es, parameters):
        from app.modules.reports.generators.collectors import PostgresCollector
        return await PostgresCollector(db).users_report(parameters)


class RolesMatrixGenerator(BaseReportGenerator):
    template_code = "roles_matrix"

    async def collect_data(self, db, es, parameters):
        from app.modules.reports.generators.collectors import PostgresCollector
        return await PostgresCollector(db).roles_matrix(parameters)


class AccessRequestsReportGenerator(BaseReportGenerator):
    template_code = "access_requests_report"

    async def collect_data(self, db, es, parameters):
        from app.modules.reports.generators.collectors import PostgresCollector
        return await PostgresCollector(db).access_requests_report(parameters)


class AuditSummaryGenerator(BaseReportGenerator):
    template_code = "audit_summary"

    async def collect_data(self, db, es, parameters):
        from app.modules.reports.generators.collectors import ElasticCollector
        return await ElasticCollector(es).audit_summary(parameters)


class SecurityIncidentsGenerator(BaseReportGenerator):
    template_code = "security_incidents"

    async def collect_data(self, db, es, parameters):
        from app.models.monitor import Alert, AlertStatus, AlertSeverity
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload

        q = select(Alert).options(selectinload(Alert.rule)).order_by(Alert.triggered_at.desc())
        if parameters.get("date_from"):
            from datetime import datetime
            q = q.where(Alert.triggered_at >= datetime.fromisoformat(parameters["date_from"]))
        if parameters.get("date_to"):
            from datetime import datetime
            q = q.where(Alert.triggered_at <= datetime.fromisoformat(parameters["date_to"]))
        if parameters.get("severity"):
            q = q.where(Alert.severity == AlertSeverity(parameters["severity"]))

        rows = (await db.execute(q)).scalars().all()
        return {
            "title": "Инциденты безопасности",
            "headers": ["Время", "Правило", "Severity", "Статус", "Детали"],
            "rows": [
                [
                    r.triggered_at.strftime("%Y-%m-%d %H:%M") if r.triggered_at else "—",
                    r.rule.name if r.rule else str(r.rule_id)[:8],
                    r.severity.value,
                    r.status.value,
                    str(r.details)[:100],
                ]
                for r in rows
            ],
            "count": len(rows),
        }


class InactiveUsersGenerator(BaseReportGenerator):
    template_code = "inactive_users"

    async def collect_data(self, db, es, parameters):
        from app.modules.reports.generators.collectors import ElasticCollector
        return await ElasticCollector(es).inactive_users(parameters)


class PermissionsAuditGenerator(BaseReportGenerator):
    template_code = "permissions_audit"

    async def collect_data(self, db, es, parameters):
        from app.modules.reports.generators.collectors import PostgresCollector
        return await PostgresCollector(db).permissions_audit(parameters)


class ComplianceOverviewGenerator(BaseReportGenerator):
    template_code = "compliance_overview"

    async def collect_data(self, db, es, parameters):
        from app.modules.reports.generators.collectors import PostgresCollector, ElasticCollector
        pg = await PostgresCollector(db).compliance_pg_part(parameters)
        es_data = await ElasticCollector(es).compliance_es_part(parameters)
        rows = [
            ["Всего пользователей", pg["total_users"]],
            ["Активных пользователей", pg["active_users"]],
            ["Заблокированных", pg["blocked_users"]],
            ["Открытых инцидентов", pg["open_alerts"]],
            ["Всего ролей", pg["total_roles"]],
            ["Событий аудита", es_data["total_audit_events"]],
        ]
        return {
            "title": "Обзор соответствия политикам",
            "headers": ["Показатель", "Значение"],
            "rows": rows,
            "count": len(rows),
        }


# Registry: template_code → generator instance
GENERATORS: dict[str, BaseReportGenerator] = {
    g.template_code: g
    for g in [
        UsersReportGenerator(),
        RolesMatrixGenerator(),
        AccessRequestsReportGenerator(),
        AuditSummaryGenerator(),
        SecurityIncidentsGenerator(),
        InactiveUsersGenerator(),
        PermissionsAuditGenerator(),
        ComplianceOverviewGenerator(),
    ]
}
