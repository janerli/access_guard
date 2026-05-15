import os
from typing import Annotated, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.deps import get_current_admin, require_roles
from app.database import get_db
from app.models.admin import AdminRole
from app.models.reports import Report, ReportFormat, ReportSchedule, ReportStatus, ReportTemplate
from app.modules.reports.schemas import (
    ReportCreate,
    ReportOut,
    ReportsListResponse,
    ReportScheduleCreate,
    ReportScheduleOut,
    ReportScheduleUpdate,
    ReportTemplateOut,
)

router = APIRouter()

_CAN_READ = (AdminRole.system_admin, AdminRole.security_officer, AdminRole.hr_operator, AdminRole.auditor)
_CAN_MANAGE = (AdminRole.system_admin, AdminRole.security_officer)


# ── Templates ─────────────────────────────────────────────────────────────────

@router.get("/templates", response_model=list[ReportTemplateOut], dependencies=[require_roles(*_CAN_READ)])
async def list_templates(db: Annotated[AsyncSession, Depends(get_db)]):
    rows = (await db.execute(select(ReportTemplate).order_by(ReportTemplate.name))).scalars().all()
    return list(rows)


@router.get("/templates/{code}", response_model=ReportTemplateOut, dependencies=[require_roles(*_CAN_READ)])
async def get_template(code: str, db: Annotated[AsyncSession, Depends(get_db)]):
    row = (await db.execute(select(ReportTemplate).where(ReportTemplate.code == code))).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Шаблон не найден")
    return row


# ── Reports ───────────────────────────────────────────────────────────────────

@router.post("/", response_model=ReportOut, status_code=202, dependencies=[require_roles(*_CAN_READ)])
async def create_report(
    body: ReportCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_admin=Depends(get_current_admin),
):
    template = (await db.execute(
        select(ReportTemplate).where(ReportTemplate.code == body.template_code)
    )).scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="Шаблон не найден")
    if body.format.value not in template.output_formats:
        raise HTTPException(status_code=400, detail=f"Формат {body.format.value} не поддерживается этим шаблоном")

    report = Report(
        template_id=template.id,
        parameters=body.parameters,
        format=body.format,
        status=ReportStatus.pending,
    )
    db.add(report)
    await db.commit()  # commit before dispatch so Celery task can find the record

    from app.modules.reports.tasks import generate_report
    generate_report.delay(str(report.id))

    await db.refresh(report, ["template"])
    return report


@router.get("/", response_model=ReportsListResponse, dependencies=[require_roles(*_CAN_READ)])
async def list_reports(
    db: Annotated[AsyncSession, Depends(get_db)],
    template_code: Optional[str] = None,
    status: Optional[ReportStatus] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    q = select(Report).options(selectinload(Report.template))
    if template_code:
        tmpl = (await db.execute(
            select(ReportTemplate).where(ReportTemplate.code == template_code)
        )).scalar_one_or_none()
        if tmpl:
            q = q.where(Report.template_id == tmpl.id)
    if status:
        q = q.where(Report.status == status)
    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar_one()
    items = (await db.execute(
        q.order_by(desc(Report.created_at)).offset((page - 1) * page_size).limit(page_size)
    )).scalars().all()
    return ReportsListResponse(items=list(items), total=total, page=page, page_size=page_size)


@router.get("/{report_id}", response_model=ReportOut, dependencies=[require_roles(*_CAN_READ)])
async def get_report(report_id: UUID, db: Annotated[AsyncSession, Depends(get_db)]):
    row = (await db.execute(
        select(Report).options(selectinload(Report.template)).where(Report.id == report_id)
    )).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Отчёт не найден")
    return row


@router.get("/{report_id}/download", dependencies=[require_roles(*_CAN_READ)])
async def download_report(report_id: UUID, db: Annotated[AsyncSession, Depends(get_db)]):
    row = (await db.execute(select(Report).where(Report.id == report_id))).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Отчёт не найден")
    if row.status != ReportStatus.ready:
        raise HTTPException(status_code=409, detail=f"Отчёт не готов (статус: {row.status.value})")
    if not row.file_path or not os.path.exists(row.file_path):
        raise HTTPException(status_code=404, detail="Файл отчёта не найден")

    ext = row.format.value
    media_types = {"pdf": "application/pdf", "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "csv": "text/csv"}
    return FileResponse(
        row.file_path,
        media_type=media_types.get(ext, "application/octet-stream"),
        filename=f"report_{report_id}.{ext}",
    )


# ── Schedules ─────────────────────────────────────────────────────────────────

@router.get("/schedules/", response_model=list[ReportScheduleOut], dependencies=[require_roles(*_CAN_READ)])
async def list_schedules(db: Annotated[AsyncSession, Depends(get_db)]):
    rows = (await db.execute(
        select(ReportSchedule).options(selectinload(ReportSchedule.template))
    )).scalars().all()
    return list(rows)


@router.post("/schedules/", response_model=ReportScheduleOut, status_code=201, dependencies=[require_roles(*_CAN_MANAGE)])
async def create_schedule(body: ReportScheduleCreate, db: Annotated[AsyncSession, Depends(get_db)]):
    template = (await db.execute(
        select(ReportTemplate).where(ReportTemplate.code == body.template_code)
    )).scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="Шаблон не найден")
    schedule = ReportSchedule(
        template_id=template.id,
        parameters=body.parameters,
        format=body.format,
        cron_expression=body.cron_expression,
        delivery_channel_id=body.delivery_channel_id,
        is_enabled=body.is_enabled,
    )
    db.add(schedule)
    await db.flush()
    await db.refresh(schedule, ["template"])
    return schedule


@router.patch("/schedules/{schedule_id}", response_model=ReportScheduleOut, dependencies=[require_roles(*_CAN_MANAGE)])
async def update_schedule(
    schedule_id: UUID,
    body: ReportScheduleUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    row = (await db.execute(select(ReportSchedule).where(ReportSchedule.id == schedule_id))).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Расписание не найдено")
    if body.parameters is not None:
        row.parameters = body.parameters
    if body.format is not None:
        row.format = body.format
    if body.cron_expression is not None:
        row.cron_expression = body.cron_expression
    if body.delivery_channel_id is not None:
        row.delivery_channel_id = body.delivery_channel_id
    if body.is_enabled is not None:
        row.is_enabled = body.is_enabled
    await db.flush()
    return row


@router.delete("/schedules/{schedule_id}", status_code=204, dependencies=[require_roles(*_CAN_MANAGE)])
async def delete_schedule(schedule_id: UUID, db: Annotated[AsyncSession, Depends(get_db)]):
    row = (await db.execute(select(ReportSchedule).where(ReportSchedule.id == schedule_id))).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Расписание не найдено")
    await db.delete(row)


@router.post("/schedules/{schedule_id}/run", response_model=ReportOut, status_code=202, dependencies=[require_roles(*_CAN_MANAGE)])
async def run_schedule_now(schedule_id: UUID, db: Annotated[AsyncSession, Depends(get_db)]):
    schedule = (await db.execute(
        select(ReportSchedule).where(ReportSchedule.id == schedule_id)
    )).scalar_one_or_none()
    if not schedule:
        raise HTTPException(status_code=404, detail="Расписание не найдено")
    report = Report(
        template_id=schedule.template_id,
        parameters=schedule.parameters,
        format=schedule.format,
        status=ReportStatus.pending,
    )
    db.add(report)
    await db.flush()
    await db.commit()  # commit before dispatch so worker can find the row
    from app.modules.reports.tasks import generate_report
    generate_report.delay(str(report.id))
    await db.refresh(report, ["template"])
    return report


# ── WebSocket ─────────────────────────────────────────────────────────────────

@router.websocket("/ws/reports")
async def ws_reports(websocket: WebSocket):
    """Stream report status updates to connected clients."""
    import asyncio
    from app.database import AsyncSessionLocal

    await websocket.accept()
    try:
        while True:
            async with AsyncSessionLocal() as db:
                rows = (await db.execute(
                    select(Report)
                    .where(Report.status.in_([ReportStatus.pending, ReportStatus.generating]))
                    .order_by(desc(Report.created_at))
                    .limit(20)
                )).scalars().all()
                statuses = [
                    {"report_id": str(r.id), "status": r.status.value}
                    for r in rows
                ]
            await websocket.send_json({"reports": statuses})
            await asyncio.sleep(3)
    except WebSocketDisconnect:
        pass
