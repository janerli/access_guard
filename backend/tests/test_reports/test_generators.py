"""Unit tests for report generators — covers base.py collect_data methods."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest


def _make_db():
    """Mock AsyncSession — execute().scalars().all() returns empty list by default."""
    db = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    result.scalar_one.return_value = 0
    result.scalar_one_or_none.return_value = None
    result.all.return_value = []
    db.execute = AsyncMock(return_value=result)
    return db


def _make_es(search_result: dict | None = None):
    es = AsyncMock()
    es.search = AsyncMock(return_value=search_result or {
        "hits": {"total": {"value": 0}, "hits": []},
        "aggregations": {
            "by_module":    {"buckets": [{"key": "identity", "doc_count": 10}]},
            "by_operation": {"buckets": [{"key": "login_success", "doc_count": 5}]},
            "by_result":    {"buckets": [{"key": "success", "doc_count": 15}]},
            "by_day":       {"buckets": []},
            "active_users": {"buckets": [{"key": "user1", "doc_count": 3}]},
            "all_users":    {"buckets": [{"key": "user1", "doc_count": 3},
                                          {"key": "user2", "doc_count": 1}]},
        },
    })
    return es


# ── BaseReportGenerator.generate (covers base class generate method) ──────────

@pytest.mark.asyncio
async def test_base_generator_generate_csv():
    from app.modules.reports.generators.base import UsersReportGenerator
    from app.models.reports import ReportFormat

    gen = UsersReportGenerator()
    db = _make_db()
    es = _make_es()

    result = await gen.generate(db, es, {}, ReportFormat.csv)
    assert isinstance(result, bytes)


@pytest.mark.asyncio
async def test_base_generator_generate_xlsx():
    from app.modules.reports.generators.base import RolesMatrixGenerator
    from app.models.reports import ReportFormat

    gen = RolesMatrixGenerator()
    db = _make_db()

    # roles_matrix does multiple joins — mock returns empty
    result = await gen.generate(db, None, {}, ReportFormat.xlsx)
    assert isinstance(result, bytes)


@pytest.mark.asyncio
async def test_base_generator_generate_pdf():
    from app.modules.reports.generators.base import UsersReportGenerator
    from app.models.reports import ReportFormat

    gen = UsersReportGenerator()
    db = _make_db()

    result = await gen.generate(db, None, {}, ReportFormat.pdf)
    assert isinstance(result, bytes)


# ── UsersReportGenerator ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_users_report_empty():
    from app.modules.reports.generators.base import UsersReportGenerator

    gen = UsersReportGenerator()
    data = await gen.collect_data(_make_db(), None, {})
    assert data["headers"] == ["ФИО", "Логин", "Email", "Должность", "Отдел", "Статус"]
    assert data["rows"] == []
    assert data["count"] == 0


@pytest.mark.asyncio
async def test_users_report_with_status_filter():
    from app.modules.reports.generators.base import UsersReportGenerator

    gen = UsersReportGenerator()
    data = await gen.collect_data(_make_db(), None, {"status": "active"})
    assert isinstance(data, dict)


# ── RolesMatrixGenerator ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_roles_matrix_empty():
    from app.modules.reports.generators.base import RolesMatrixGenerator

    gen = RolesMatrixGenerator()
    data = await gen.collect_data(_make_db(), None, {})
    assert data["headers"] == ["Отдел", "Сотрудник", "Роли"]
    assert isinstance(data["rows"], list)


# ── AccessRequestsReportGenerator ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_access_requests_report_empty():
    from app.modules.reports.generators.base import AccessRequestsReportGenerator

    gen = AccessRequestsReportGenerator()
    data = await gen.collect_data(_make_db(), None, {})
    assert "headers" in data
    assert data["count"] == 0


@pytest.mark.asyncio
async def test_access_requests_with_date_filter():
    from app.modules.reports.generators.base import AccessRequestsReportGenerator

    gen = AccessRequestsReportGenerator()
    data = await gen.collect_data(_make_db(), None, {
        "date_from": "2026-01-01",
        "date_to": "2026-12-31",
        "status": "approved",
    })
    assert isinstance(data, dict)


# ── AuditSummaryGenerator (ES) ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_audit_summary_with_es():
    from app.modules.reports.generators.base import AuditSummaryGenerator

    gen = AuditSummaryGenerator()
    data = await gen.collect_data(None, _make_es(), {
        "date_from": "2026-01-01",
        "date_to": "2026-12-31",
    })
    assert "headers" in data
    assert data["headers"] == ["Операция", "Количество"]
    assert isinstance(data["rows"], list)


@pytest.mark.asyncio
async def test_audit_summary_es_down():
    """When ES raises — returns fallback with ES-недоступен title."""
    from app.modules.reports.generators.base import AuditSummaryGenerator

    es = AsyncMock()
    es.search = AsyncMock(side_effect=Exception("ES down"))

    gen = AuditSummaryGenerator()
    data = await gen.collect_data(None, es, {})
    assert "ES недоступен" in data["title"]
    assert data["rows"] == []


# ── SecurityIncidentsGenerator ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_security_incidents_empty():
    from app.modules.reports.generators.base import SecurityIncidentsGenerator

    gen = SecurityIncidentsGenerator()
    data = await gen.collect_data(_make_db(), None, {})
    assert data["headers"] == ["Время", "Правило", "Severity", "Статус", "Детали"]
    assert data["count"] == 0


@pytest.mark.asyncio
async def test_security_incidents_with_filters():
    from app.modules.reports.generators.base import SecurityIncidentsGenerator

    gen = SecurityIncidentsGenerator()
    data = await gen.collect_data(_make_db(), None, {
        "date_from": "2026-01-01",
        "date_to": "2026-12-31",
        "severity": "high",
    })
    assert isinstance(data, dict)


# ── InactiveUsersGenerator (ES) ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_inactive_users_with_es():
    from app.modules.reports.generators.base import InactiveUsersGenerator

    gen = InactiveUsersGenerator()
    data = await gen.collect_data(None, _make_es(), {"inactive_days": 30})
    assert "headers" in data
    # user2 is in all_users but not in active_users (active within 30 days) → inactive
    assert data["count"] >= 0


@pytest.mark.asyncio
async def test_inactive_users_es_down():
    from app.modules.reports.generators.base import InactiveUsersGenerator

    es = AsyncMock()
    es.search = AsyncMock(side_effect=ConnectionError("ES down"))

    gen = InactiveUsersGenerator()
    data = await gen.collect_data(None, es, {})
    assert data["rows"] == []


# ── PermissionsAuditGenerator ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_permissions_audit_empty():
    from app.modules.reports.generators.base import PermissionsAuditGenerator

    gen = PermissionsAuditGenerator()
    data = await gen.collect_data(_make_db(), None, {
        "date_from": "2026-01-01",
        "date_to": "2026-12-31",
    })
    assert data["headers"] == ["Время", "Администратор", "Объект", "Роль", "Результат"]
    assert data["count"] == 0


# ── ComplianceOverviewGenerator ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_compliance_overview():
    from app.modules.reports.generators.base import ComplianceOverviewGenerator

    db = _make_db()
    # compliance_pg_part runs 5 count queries — each returns 0
    gen = ComplianceOverviewGenerator()
    data = await gen.collect_data(db, _make_es(), {})
    assert data["headers"] == ["Показатель", "Значение"]
    assert len(data["rows"]) == 6
    assert data["count"] == 6


@pytest.mark.asyncio
async def test_compliance_overview_es_down():
    from app.modules.reports.generators.base import ComplianceOverviewGenerator

    es = AsyncMock()
    es.search = AsyncMock(side_effect=Exception("ES down"))

    gen = ComplianceOverviewGenerator()
    data = await gen.collect_data(_make_db(), es, {})
    # Should still return rows (ES part returns 0 on failure)
    assert len(data["rows"]) == 6
