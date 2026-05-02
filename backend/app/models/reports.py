import enum
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ReportDataSource(str, enum.Enum):
    postgres = "postgres"
    elasticsearch = "elasticsearch"
    combined = "combined"


class ReportFormat(str, enum.Enum):
    pdf = "pdf"
    xlsx = "xlsx"
    csv = "csv"


class ReportStatus(str, enum.Enum):
    pending = "pending"
    generating = "generating"
    ready = "ready"
    failed = "failed"


class ReportTemplate(Base):
    __tablename__ = "report_templates"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    data_source: Mapped[ReportDataSource] = mapped_column(
        Enum(ReportDataSource, name="report_data_source"), nullable=False
    )
    parameters_schema: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    output_formats: Mapped[list[str]] = mapped_column(ARRAY(String(10)), nullable=False, default=list)

    reports: Mapped[list["Report"]] = relationship("Report", back_populates="template")
    schedules: Mapped[list["ReportSchedule"]] = relationship("ReportSchedule", back_populates="template")


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    template_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("report_templates.id"), nullable=False
    )
    requested_by: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users_ext.id", ondelete="SET NULL"), nullable=True
    )
    parameters: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    format: Mapped[ReportFormat] = mapped_column(
        Enum(ReportFormat, name="report_format"), nullable=False
    )
    status: Mapped[ReportStatus] = mapped_column(
        Enum(ReportStatus, name="report_status"), nullable=False, default=ReportStatus.pending
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    file_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    template: Mapped["ReportTemplate"] = relationship("ReportTemplate", back_populates="reports")


class ReportSchedule(Base):
    __tablename__ = "report_schedules"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    template_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("report_templates.id"), nullable=False
    )
    parameters: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    format: Mapped[ReportFormat] = mapped_column(
        Enum(ReportFormat, name="report_format"), nullable=False, default=ReportFormat.xlsx
    )
    cron_expression: Mapped[str] = mapped_column(String(100), nullable=False)
    delivery_channel_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    template: Mapped["ReportTemplate"] = relationship("ReportTemplate", back_populates="schedules")
