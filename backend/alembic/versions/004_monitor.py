"""monitor module — audit_log, outbox_events, alert_rules, alerts, notification_channels

Revision ID: 004
Revises: 003
Create Date: 2026-05-02
"""
from typing import Sequence, Union
from uuid import uuid4

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Enum types ─────────────────────────────────────────────────────────────
    op.execute("CREATE TYPE audit_target_type AS ENUM ('user', 'role', 'resource', 'system')")
    op.execute("""
        CREATE TYPE audit_operation AS ENUM (
            'create', 'read', 'update', 'delete',
            'login_success', 'login_failure', 'permission_check',
            'role_assign', 'role_revoke', 'password_reset',
            'suspend', 'restore', 'block',
            'request_submit', 'request_approve', 'request_reject', 'request_withdraw'
        )
    """)
    op.execute("CREATE TYPE audit_module AS ENUM ('identity', 'access', 'monitor', 'reports', 'auth')")
    op.execute("CREATE TYPE audit_result AS ENUM ('success', 'failure', 'denied')")
    op.execute("CREATE TYPE outbox_status AS ENUM ('pending', 'published', 'failed')")
    op.execute("CREATE TYPE alert_condition_type AS ENUM ('threshold', 'pattern', 'anomaly')")
    op.execute("CREATE TYPE alert_severity AS ENUM ('info', 'low', 'medium', 'high', 'critical')")
    op.execute("CREATE TYPE alert_data_source AS ENUM ('postgres', 'elasticsearch')")
    op.execute("CREATE TYPE alert_status AS ENUM ('new', 'acknowledged', 'resolved', 'false_positive')")
    op.execute("CREATE TYPE notification_channel_type AS ENUM ('email', 'webhook', 'log', 'kafka')")

    # ── audit_log ──────────────────────────────────────────────────────────────
    op.create_table(
        "audit_log",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users_ext.id", ondelete="SET NULL"), nullable=True),
        sa.Column("actor_username", sa.String(255), nullable=False, server_default=sa.text("''")),
        sa.Column("target_type", sa.Enum("user", "role", "resource", "system", name="audit_target_type", create_type=False), nullable=False),
        sa.Column("target_id", sa.String(255), nullable=False, server_default=sa.text("''")),
        sa.Column("operation", sa.Enum(
            "create", "read", "update", "delete",
            "login_success", "login_failure", "permission_check",
            "role_assign", "role_revoke", "password_reset",
            "suspend", "restore", "block",
            "request_submit", "request_approve", "request_reject", "request_withdraw",
            name="audit_operation", create_type=False
        ), nullable=False),
        sa.Column("module", sa.Enum("identity", "access", "monitor", "reports", "auth", name="audit_module", create_type=False), nullable=False),
        sa.Column("result", sa.Enum("success", "failure", "denied", name="audit_result", create_type=False), nullable=False),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.String(500), nullable=True),
        sa.Column("details", postgresql.JSONB(), nullable=True),
        sa.Column("correlation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("published_to_kafka", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.create_unique_constraint("uq_audit_log_event_id", "audit_log", ["event_id"])
    op.create_index("ix_audit_log_timestamp", "audit_log", ["timestamp"])
    op.create_index("ix_audit_log_actor_id", "audit_log", ["actor_id"])
    op.create_index("ix_audit_log_operation", "audit_log", ["operation"])
    op.create_index("ix_audit_log_module", "audit_log", ["module"])

    # Append-only trigger — запрещает UPDATE/DELETE для записей старше 1 минуты
    op.execute("""
        CREATE OR REPLACE FUNCTION prevent_audit_modification()
        RETURNS trigger AS $$
        BEGIN
            IF OLD.timestamp < now() - INTERVAL '1 minute' THEN
                RAISE EXCEPTION 'audit_log records cannot be modified or deleted';
            END IF;
            RETURN NULL;
        END;
        $$ LANGUAGE plpgsql;
    """)
    op.execute("""
        CREATE TRIGGER audit_log_immutable
        BEFORE UPDATE OR DELETE ON audit_log
        FOR EACH ROW EXECUTE FUNCTION prevent_audit_modification();
    """)

    # ── outbox_events ──────────────────────────────────────────────────────────
    op.create_table(
        "outbox_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("audit_log_id", sa.BigInteger(), sa.ForeignKey("audit_log.id", ondelete="CASCADE"), nullable=False),
        sa.Column("topic", sa.String(100), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.Enum("pending", "published", "failed", name="outbox_status", create_type=False), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default=sa.text("0")),
    )
    op.create_index("ix_outbox_status", "outbox_events", ["status"])

    # ── alert_rules ────────────────────────────────────────────────────────────
    op.create_table(
        "alert_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(100), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("condition_type", sa.Enum("threshold", "pattern", "anomaly", name="alert_condition_type", create_type=False), nullable=False),
        sa.Column("condition_config", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("severity", sa.Enum("info", "low", "medium", "high", "critical", name="alert_severity", create_type=False), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("cooldown_seconds", sa.Integer(), nullable=False, server_default=sa.text("300")),
        sa.Column("data_source", sa.Enum("postgres", "elasticsearch", name="alert_data_source", create_type=False), nullable=False),
    )
    op.create_unique_constraint("uq_alert_rules_code", "alert_rules", ["code"])

    # ── alerts ─────────────────────────────────────────────────────────────────
    op.create_table(
        "alerts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("rule_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("alert_rules.id"), nullable=False),
        sa.Column("triggered_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("subject_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users_ext.id", ondelete="SET NULL"), nullable=True),
        sa.Column("severity", sa.Enum("info", "low", "medium", "high", "critical", name="alert_severity", create_type=False), nullable=False),
        sa.Column("status", sa.Enum("new", "acknowledged", "resolved", "false_positive", name="alert_status", create_type=False), nullable=False, server_default=sa.text("'new'")),
        sa.Column("correlation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("details", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("acknowledged_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("resolution_comment", sa.Text(), nullable=True),
    )
    op.create_index("ix_alerts_triggered_at", "alerts", ["triggered_at"])
    op.create_index("ix_alerts_status", "alerts", ["status"])

    # ── notification_channels ─────────────────────────────────────────────────
    op.create_table(
        "notification_channels",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(100), nullable=False),
        sa.Column("type", sa.Enum("email", "webhook", "log", "kafka", name="notification_channel_type", create_type=False), nullable=False),
        sa.Column("config", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.create_unique_constraint("uq_notification_channels_code", "notification_channels", ["code"])

    # ── Seed: 10 alert rules ───────────────────────────────────────────────────
    op.execute(f"""
        INSERT INTO alert_rules (id, code, name, description, condition_type, condition_config, severity, is_enabled, cooldown_seconds, data_source) VALUES
        ('{uuid4()}', 'multiple_failed_logins',       'Множественные неудачные входы',        '5+ неудачных попыток входа за 15 минут',                   'threshold', '{{"threshold": 5, "window_minutes": 15}}', 'high',     true, 300,  'postgres'),
        ('{uuid4()}', 'privileged_role_assigned',     'Назначение привилегированной роли',     'Назначение роли с флагом is_privileged',                    'pattern',   '{{}}',                                      'high',     true, 60,   'postgres'),
        ('{uuid4()}', 'audit_log_tampering_attempt',  'Попытка изменить журнал аудита',        'Попытка UPDATE/DELETE в таблице audit_log',                 'pattern',   '{{}}',                                      'critical', true, 0,    'postgres'),
        ('{uuid4()}', 'admin_password_reset',         'Сброс пароля администратора',           'Сброс пароля пользователя с привилегированной ролью',       'pattern',   '{{}}',                                      'high',     true, 300,  'postgres'),
        ('{uuid4()}', 'login_outside_hours',          'Вход в нерабочее время',                'Успешный вход с 22:00 до 06:00',                            'threshold', '{{"start_hour": 22, "end_hour": 6}}',        'medium',   true, 600,  'elasticsearch'),
        ('{uuid4()}', 'mass_permission_failures',     'Массовые отказы в доступе',             '10+ отказов в доступе за 5 минут от одного пользователя',   'threshold', '{{"threshold": 10, "window_minutes": 5}}',  'medium',   true, 300,  'elasticsearch'),
        ('{uuid4()}', 'bulk_user_changes',            'Массовые изменения учётных записей',    '20+ операций за 10 минут от одного администратора',         'threshold', '{{"threshold": 20, "window_minutes": 10}}', 'medium',   true, 600,  'elasticsearch'),
        ('{uuid4()}', 'inactive_user_login',          'Вход под неактивной учётной записью',   'Вход под записью без активности более 90 дней',             'anomaly',   '{{"inactive_days": 90}}',                   'high',     true, 3600, 'elasticsearch'),
        ('{uuid4()}', 'unusual_geo_login',            'Нетипичная геолокация входа',           'Вход с IP из необычной страны',                             'anomaly',   '{{"history_days": 30}}',                    'high',     true, 3600, 'elasticsearch'),
        ('{uuid4()}', 'data_exfiltration_pattern',    'Признаки массовой выгрузки данных',     'Массовое чтение документов одним пользователем за период',  'threshold', '{{"threshold": 100, "window_minutes": 30}}','high',     true, 1800, 'elasticsearch')
    """)

    # ── Seed: notification channels ───────────────────────────────────────────
    op.execute(f"""
        INSERT INTO notification_channels (id, code, type, config, is_enabled) VALUES
        ('{uuid4()}', 'email_default',   'email',   '{{"to": "security@accessguard.local"}}',  true),
        ('{uuid4()}', 'log_default',     'log',     '{{"path": "/var/log/accessguard/alerts.log"}}', true),
        ('{uuid4()}', 'kafka_alerts',    'kafka',   '{{"topic": "monitor.alerts"}}',            true),
        ('{uuid4()}', 'webhook_default', 'webhook', '{{"url": "http://localhost:9999/alerts"}}', false)
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS audit_log_immutable ON audit_log")
    op.execute("DROP FUNCTION IF EXISTS prevent_audit_modification()")
    op.drop_table("notification_channels")
    op.drop_table("alerts")
    op.drop_table("alert_rules")
    op.drop_table("outbox_events")
    op.drop_table("audit_log")
    op.execute("DROP TYPE IF EXISTS notification_channel_type")
    op.execute("DROP TYPE IF EXISTS alert_status")
    op.execute("DROP TYPE IF EXISTS alert_data_source")
    op.execute("DROP TYPE IF EXISTS alert_severity")
    op.execute("DROP TYPE IF EXISTS alert_condition_type")
    op.execute("DROP TYPE IF EXISTS outbox_status")
    op.execute("DROP TYPE IF EXISTS audit_result")
    op.execute("DROP TYPE IF EXISTS audit_module")
    op.execute("DROP TYPE IF EXISTS audit_operation")
    op.execute("DROP TYPE IF EXISTS audit_target_type")
