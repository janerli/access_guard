from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel

from app.models.reports import ReportDataSource, ReportFormat, ReportStatus


class ReportTemplateOut(BaseModel):
    id: UUID
    code: str
    name: str
    description: str
    data_source: ReportDataSource
    parameters_schema: dict
    output_formats: list[str]

    model_config = {"from_attributes": True}


class ReportOut(BaseModel):
    id: UUID
    template_id: UUID
    requested_by: Optional[UUID]
    parameters: dict
    format: ReportFormat
    status: ReportStatus
    created_at: datetime
    completed_at: Optional[datetime]
    file_path: Optional[str]
    file_size: Optional[int]
    error_message: Optional[str]
    template: Optional[ReportTemplateOut] = None

    model_config = {"from_attributes": True}


class ReportCreate(BaseModel):
    template_code: str
    parameters: dict = {}
    format: ReportFormat = ReportFormat.xlsx


class ReportsListResponse(BaseModel):
    items: list[ReportOut]
    total: int
    page: int
    page_size: int


class ReportScheduleOut(BaseModel):
    id: UUID
    template_id: UUID
    parameters: dict
    format: ReportFormat
    cron_expression: str
    delivery_channel_id: Optional[UUID]
    is_enabled: bool
    last_run_at: Optional[datetime]
    template: Optional[ReportTemplateOut] = None

    model_config = {"from_attributes": True}


class ReportScheduleCreate(BaseModel):
    template_code: str
    parameters: dict = {}
    format: ReportFormat = ReportFormat.xlsx
    cron_expression: str
    delivery_channel_id: Optional[UUID] = None
    is_enabled: bool = True


class ReportScheduleUpdate(BaseModel):
    parameters: Optional[dict] = None
    format: Optional[ReportFormat] = None
    cron_expression: Optional[str] = None
    delivery_channel_id: Optional[UUID] = None
    is_enabled: Optional[bool] = None
