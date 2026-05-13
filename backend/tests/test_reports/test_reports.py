"""Тесты Reports модуля — templates, generation, schedules."""
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from httpx import AsyncClient


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ── Templates ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_templates(client: AsyncClient, admin_token: str):
    resp = await client.get("/api/reports/templates", headers=_headers(admin_token))
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    # Migration seeds 8 templates (may be 0 in fresh test DB)


@pytest.mark.asyncio
async def test_get_template_not_found(client: AsyncClient, admin_token: str):
    resp = await client.get("/api/reports/templates/nonexistent_code", headers=_headers(admin_token))
    assert resp.status_code == 404


# ── Reports (async generation) ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_report_template_not_found(client: AsyncClient, admin_token: str):
    resp = await client.post(
        "/api/reports/",
        json={"template_code": "nonexistent_xyz", "parameters": {}, "format": "csv"},
        headers=_headers(admin_token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_reports(client: AsyncClient, admin_token: str):
    resp = await client.get("/api/reports/", headers=_headers(admin_token))
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data


@pytest.mark.asyncio
async def test_get_report_not_found(client: AsyncClient, admin_token: str):
    resp = await client.get(f"/api/reports/{uuid4()}", headers=_headers(admin_token))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_download_not_ready(client: AsyncClient, admin_token: str, seed_user_ext: str, db_session):
    """Report in pending state — download should return 409."""
    from app.models.reports import Report, ReportStatus, ReportFormat
    from app.models.reports import ReportTemplate
    from sqlalchemy import select

    tmpl = (await db_session.execute(select(ReportTemplate).limit(1))).scalar_one_or_none()
    if not tmpl:
        from app.models.reports import ReportDataSource

        tmpl = ReportTemplate(
            code=f"pytest_template_{uuid4().hex[:8]}",
            name="Pytest Template",
            description="Template for tests",
            data_source=ReportDataSource.postgres,
            parameters_schema={},
            output_formats=["csv", "xlsx", "pdf"],
        )
        db_session.add(tmpl)
        await db_session.commit()

    resp = await client.post(
        "/api/reports/",
        json={"template_code": tmpl.code, "parameters": {}, "format": "csv"},
        headers=_headers(admin_token),
    )
    assert resp.status_code == 202
    report_id = resp.json()["id"]
    assert resp.json()["status"] == "pending"

    dl = await client.get(f"/api/reports/{report_id}/download", headers=_headers(admin_token))
    assert dl.status_code in (404, 409)  # Not ready or file missing


# ── Schedules ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_schedules(client: AsyncClient, admin_token: str):
    resp = await client.get("/api/reports/schedules/", headers=_headers(admin_token))
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_create_schedule_template_not_found(client: AsyncClient, admin_token: str):
    resp = await client.post(
        "/api/reports/schedules/",
        json={"template_code": "no_such_template", "format": "xlsx", "cron_expression": "@daily"},
        headers=_headers(admin_token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_schedule_not_found(client: AsyncClient, admin_token: str):
    resp = await client.patch(
        f"/api/reports/schedules/{uuid4()}",
        json={"is_enabled": False},
        headers=_headers(admin_token),
    )
    assert resp.status_code == 404


# ── Generator unit tests ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_csv_renderer():
    from app.modules.reports.generators.renderers import CsvRenderer
    data = {
        "title": "Тест",
        "headers": ["Имя", "Значение"],
        "rows": [["Иванов", "100"], ["Петров", "200"]],
        "count": 2,
    }
    result = CsvRenderer().render(data)
    assert isinstance(result, bytes)
    text = result.decode("utf-8-sig")
    assert "Тест" in text
    assert "Иванов" in text
    assert "Петров" in text


@pytest.mark.asyncio
async def test_xlsx_renderer():
    from app.modules.reports.generators.renderers import XlsxRenderer
    data = {
        "title": "XLSX тест",
        "headers": ["Колонка 1", "Колонка 2"],
        "rows": [["A", "B"], ["C", "D"]],
        "count": 2,
    }
    result = XlsxRenderer().render(data)
    assert isinstance(result, bytes)
    assert len(result) > 0


@pytest.mark.asyncio
async def test_pdf_renderer_fallback():
    from app.modules.reports.generators.renderers import PdfRenderer
    data = {
        "title": "PDF тест",
        "headers": ["Колонка 1"],
        "rows": [["Значение"]],
        "count": 1,
    }
    # Falls back gracefully if WeasyPrint not installed
    result = PdfRenderer().render(data)
    assert isinstance(result, bytes)
    assert len(result) > 0


@pytest.mark.asyncio
async def test_generator_registry():
    from app.modules.reports.generators.base import GENERATORS
    expected = [
        "users_report", "roles_matrix", "access_requests_report",
        "audit_summary", "security_incidents", "inactive_users",
        "permissions_audit", "compliance_overview",
    ]
    for code in expected:
        assert code in GENERATORS, f"Missing generator: {code}"


@pytest.mark.asyncio
async def test_schedule_should_run():
    from app.modules.reports.tasks import _should_run
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)

    # Never run before — should run
    assert _should_run("@daily", None, now) is True

    # Run 2 hours ago — hourly should run
    two_hours_ago = now - timedelta(hours=2)
    assert _should_run("@hourly", two_hours_ago, now) is True

    # Run 30 minutes ago — hourly should NOT run
    thirty_min_ago = now - timedelta(minutes=30)
    assert _should_run("@hourly", thirty_min_ago, now) is False

    # Run 2 days ago — daily should run
    two_days_ago = now - timedelta(days=2)
    assert _should_run("@daily", two_days_ago, now) is True
