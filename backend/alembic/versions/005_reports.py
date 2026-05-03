"""reports module — report_templates, reports, report_schedules

Revision ID: 005
Revises: 004
Create Date: 2026-05-02
"""
from typing import Sequence, Union
from uuid import uuid4

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enum types
    op.execute("CREATE TYPE report_data_source AS ENUM ('postgres', 'elasticsearch', 'combined')")
    op.execute("CREATE TYPE report_format AS ENUM ('pdf', 'xlsx', 'csv')")
    op.execute("CREATE TYPE report_status AS ENUM ('pending', 'generating', 'ready', 'failed')")

    # report_templates
    op.create_table(
        "report_templates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(100), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("data_source", postgresql.ENUM(name="report_data_source", create_type=False), nullable=False),
        sa.Column("parameters_schema", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("output_formats", postgresql.ARRAY(sa.String(10)), nullable=False,
                  server_default=sa.text("ARRAY['pdf','xlsx','csv']")),
    )
    op.create_unique_constraint("uq_report_templates_code", "report_templates", ["code"])

    # reports
    op.create_table(
        "reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("template_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("report_templates.id"), nullable=False),
        sa.Column("requested_by", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users_ext.id", ondelete="SET NULL"), nullable=True),
        sa.Column("parameters", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("format", postgresql.ENUM(name="report_format", create_type=False), nullable=False),
        sa.Column("status", postgresql.ENUM(name="report_status", create_type=False), nullable=False, server_default=sa.text("'pending'::report_status")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("file_path", sa.String(500), nullable=True),
        sa.Column("file_size", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
    )
    op.create_index("ix_reports_status", "reports", ["status"])
    op.create_index("ix_reports_created_at", "reports", ["created_at"])

    # report_schedules
    op.create_table(
        "report_schedules",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("template_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("report_templates.id"), nullable=False),
        sa.Column("parameters", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("format", postgresql.ENUM(name="report_format", create_type=False),
                  nullable=False, server_default=sa.text("'xlsx'::report_format")),
        sa.Column("cron_expression", sa.String(100), nullable=False),
        sa.Column("delivery_channel_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Seed 8 templates
    op.execute(f"""
        INSERT INTO report_templates (id, code, name, description, data_source, parameters_schema, output_formats) VALUES
        (
            '{uuid4()}', 'users_report', 'Список пользователей',
            'Список сотрудников с фильтрацией по отделу, статусу и должности',
            'postgres',
            '{{"type":"object","properties":{{"department_id":{{"type":"string","title":"Отдел (ID)"}},"status":{{"type":"string","enum":["new","active","suspended","blocked","deleted"],"title":"Статус"}},"position_id":{{"type":"string","title":"Должность (ID)"}}}}}}',
            ARRAY['pdf','xlsx','csv']
        ),
        (
            '{uuid4()}', 'roles_matrix', 'Матрица ролей',
            'Распределение ролей пользователей по отделам',
            'postgres',
            '{{"type":"object","properties":{{"department_id":{{"type":"string","title":"Отдел (ID, необязательно)"}}}}}}',
            ARRAY['pdf','xlsx','csv']
        ),
        (
            '{uuid4()}', 'access_requests_report', 'Заявки на доступ',
            'Отчёт по заявкам на доступ за период',
            'postgres',
            '{{"type":"object","required":["date_from","date_to"],"properties":{{"date_from":{{"type":"string","format":"date","title":"Дата с"}},"date_to":{{"type":"string","format":"date","title":"Дата по"}},"status":{{"type":"string","title":"Статус заявки"}}}}}}',
            ARRAY['pdf','xlsx','csv']
        ),
        (
            '{uuid4()}', 'audit_summary', 'Сводка по аудиту',
            'Статистика событий аудита через агрегации Elasticsearch',
            'elasticsearch',
            '{{"type":"object","required":["date_from","date_to"],"properties":{{"date_from":{{"type":"string","format":"date","title":"Дата с"}},"date_to":{{"type":"string","format":"date","title":"Дата по"}}}}}}',
            ARRAY['pdf','xlsx','csv']
        ),
        (
            '{uuid4()}', 'security_incidents', 'Инциденты безопасности',
            'Отчёт об инцидентах: алерты из PostgreSQL с контекстом из Elasticsearch',
            'combined',
            '{{"type":"object","required":["date_from","date_to"],"properties":{{"date_from":{{"type":"string","format":"date","title":"Дата с"}},"date_to":{{"type":"string","format":"date","title":"Дата по"}},"severity":{{"type":"string","title":"Severity"}}}}}}',
            ARRAY['pdf','xlsx','csv']
        ),
        (
            '{uuid4()}', 'inactive_users', 'Неактивные пользователи',
            'Пользователи без активности более N дней',
            'elasticsearch',
            '{{"type":"object","properties":{{"inactive_days":{{"type":"integer","default": 90,"title":"Дней бездействия"}}}}}}',
            ARRAY['pdf','xlsx','csv']
        ),
        (
            '{uuid4()}', 'permissions_audit', 'Аудит привилегированных ролей',
            'Назначения привилегированных ролей за период',
            'postgres',
            '{{"type":"object","required":["date_from","date_to"],"properties":{{"date_from":{{"type":"string","format":"date","title":"Дата с"}},"date_to":{{"type":"string","format":"date","title":"Дата по"}}}}}}',
            ARRAY['pdf','xlsx','csv']
        ),
        (
            '{uuid4()}', 'compliance_overview', 'Обзор соответствия политикам',
            'Комплексный отчёт о состоянии системы: пользователи, роли, инциденты, аудит',
            'combined',
            '{{"type":"object","properties":{{"date_from":{{"type":"string","format":"date","title":"Дата с"}},"date_to":{{"type":"string","format":"date","title":"Дата по"}}}}}}',
            ARRAY['pdf','xlsx','csv']
        )
    """)


def downgrade() -> None:
    op.drop_table("report_schedules")
    op.drop_table("reports")
    op.drop_table("report_templates")
    op.execute("DROP TYPE IF EXISTS report_status")
    op.execute("DROP TYPE IF EXISTS report_format")
    op.execute("DROP TYPE IF EXISTS report_data_source")
