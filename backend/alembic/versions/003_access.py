"""access module — roles, permissions, user_roles, resources, access_requests

Revision ID: 003
Revises: 002
Create Date: 2026-05-02
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enum types
    op.execute("CREATE TYPE resource_type AS ENUM ('file_share', 'application', 'database', 'api')")
    op.execute("CREATE TYPE access_request_status AS ENUM ('pending', 'approved', 'rejected', 'withdrawn')")

    # roles
    op.create_table(
        "roles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(100), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("is_privileged", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_unique_constraint("uq_roles_code", "roles", ["code"])
    op.create_foreign_key("fk_roles_owner", "roles", "users_ext", ["owner_user_id"], ["id"])

    # permissions
    op.create_table(
        "permissions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(100), nullable=False),
        sa.Column("description", sa.String(500), nullable=False, server_default=sa.text("''")),
    )
    op.create_unique_constraint("uq_permissions_code", "permissions", ["code"])

    # role_permissions
    op.create_table(
        "role_permissions",
        sa.Column("role_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("permission_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True),
    )

    # resources
    op.create_table(
        "resources",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(100), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column(
            "type",
            postgresql.ENUM(name="resource_type", create_type=False),
            nullable=False,
        ),
        sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users_ext.id"), nullable=True),
    )
    op.create_unique_constraint("uq_resources_code", "resources", ["code"])

    # access_requests (before user_roles — FK from user_roles.request_id)
    op.create_table(
        "access_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users_ext.id"), nullable=False),
        sa.Column("role_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("roles.id"), nullable=False),
        sa.Column("justification", sa.Text(), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(name="access_request_status", create_type=False),
            nullable=False,
            server_default=sa.text("'pending'::access_request_status"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decided_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("decision_comment", sa.Text(), nullable=True),
    )
    op.create_index("ix_access_requests_user_id", "access_requests", ["user_id"])
    op.create_index("ix_access_requests_status", "access_requests", ["status"])

    # user_roles
    op.create_table(
        "user_roles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users_ext.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("roles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("granted_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("granted_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("request_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index("ix_user_roles_user_id", "user_roles", ["user_id"])
    op.create_index("ix_user_roles_role_id", "user_roles", ["role_id"])

    # Deferred FK: user_roles.request_id → access_requests.id
    op.create_foreign_key(
        "fk_user_role_request",
        "user_roles", "access_requests",
        ["request_id"], ["id"],
        use_alter=True,
    )

    # position_role_defaults
    op.create_table(
        "position_role_defaults",
        sa.Column("position_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("positions.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("role_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    )

    # processed_events (idempotency for Kafka consumers)
    op.create_table(
        "processed_events",
        sa.Column("event_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("consumer_group", sa.String(100), nullable=False),
    )

    # ── Seed data ─────────────────────────────────────────────────────────────

    # Seed roles
    op.execute("""
        INSERT INTO roles (id, code, name, description, is_privileged) VALUES
        (gen_random_uuid(), 'system_admin',     'Системный администратор',      'Полный доступ к системе',                       true),
        (gen_random_uuid(), 'security_officer', 'Офицер безопасности',          'Управление ИБ, аудит, согласование заявок',     true),
        (gen_random_uuid(), 'hr_operator',      'HR-оператор',                  'Управление учётными записями сотрудников',       false),
        (gen_random_uuid(), 'auditor',          'Аудитор',                      'Просмотр всей информации, формирование отчётов', false),
        (gen_random_uuid(), 'manager',          'Руководитель',                 'Управление командой, согласование заявок',       false),
        (gen_random_uuid(), 'employee',         'Сотрудник',                    'Стандартный доступ для сотрудников',             false),
        (gen_random_uuid(), 'guest',            'Гость',                        'Ограниченный гостевой доступ',                   false)
    """)

    # Seed permissions
    op.execute("""
        INSERT INTO permissions (id, code, description) VALUES
        (gen_random_uuid(), 'users.read',       'Просмотр учётных записей'),
        (gen_random_uuid(), 'users.write',      'Управление учётными записями'),
        (gen_random_uuid(), 'roles.read',       'Просмотр ролей и разрешений'),
        (gen_random_uuid(), 'roles.write',      'Управление ролями и разрешениями'),
        (gen_random_uuid(), 'access.view',      'Просмотр прав доступа'),
        (gen_random_uuid(), 'access.manage',    'Управление назначением доступа'),
        (gen_random_uuid(), 'access.request',   'Подача заявок на доступ'),
        (gen_random_uuid(), 'access.approve',   'Согласование заявок на доступ'),
        (gen_random_uuid(), 'resources.read',   'Просмотр информационных ресурсов'),
        (gen_random_uuid(), 'resources.write',  'Управление информационными ресурсами'),
        (gen_random_uuid(), 'monitor.view',     'Просмотр журналов и мониторинга'),
        (gen_random_uuid(), 'reports.view',     'Просмотр отчётов'),
        (gen_random_uuid(), 'reports.generate', 'Генерация отчётов'),
        (gen_random_uuid(), 'system.admin',     'Системное администрирование')
    """)

    # system_admin — all permissions
    op.execute("""
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id FROM roles r CROSS JOIN permissions p WHERE r.code = 'system_admin'
    """)

    # security_officer
    op.execute("""
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id FROM roles r JOIN permissions p ON p.code = ANY(ARRAY[
            'users.read','roles.read','roles.write','access.view','access.manage',
            'access.approve','resources.read','monitor.view','reports.view','reports.generate'
        ]) WHERE r.code = 'security_officer'
    """)

    # hr_operator
    op.execute("""
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id FROM roles r JOIN permissions p ON p.code = ANY(ARRAY[
            'users.read','users.write','access.view','access.request','reports.view'
        ]) WHERE r.code = 'hr_operator'
    """)

    # auditor
    op.execute("""
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id FROM roles r JOIN permissions p ON p.code = ANY(ARRAY[
            'users.read','roles.read','access.view','monitor.view','reports.view','reports.generate'
        ]) WHERE r.code = 'auditor'
    """)

    # manager
    op.execute("""
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id FROM roles r JOIN permissions p ON p.code = ANY(ARRAY[
            'users.read','access.view','access.request','access.approve','resources.read','reports.view'
        ]) WHERE r.code = 'manager'
    """)

    # employee
    op.execute("""
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id FROM roles r JOIN permissions p ON p.code = ANY(ARRAY[
            'access.request','resources.read'
        ]) WHERE r.code = 'employee'
    """)

    # guest
    op.execute("""
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id FROM roles r JOIN permissions p ON p.code = ANY(ARRAY[
            'resources.read'
        ]) WHERE r.code = 'guest'
    """)

    # position_role_defaults
    op.execute("""
        INSERT INTO position_role_defaults (position_id, role_id)
        SELECT pos.id, r.id FROM positions pos JOIN roles r ON r.code = 'employee'
        WHERE pos.code IN ('DEV-JUN','DEV-MID','DEV-SEN','OPS-ENG','FIN-ANAL')
    """)
    op.execute("""
        INSERT INTO position_role_defaults (position_id, role_id)
        SELECT pos.id, r.id FROM positions pos JOIN roles r ON r.code = 'hr_operator'
        WHERE pos.code = 'HR-SPEC'
    """)
    op.execute("""
        INSERT INTO position_role_defaults (position_id, role_id)
        SELECT pos.id, r.id FROM positions pos JOIN roles r ON r.code = 'security_officer'
        WHERE pos.code = 'SEC-ANALYST'
    """)
    op.execute("""
        INSERT INTO position_role_defaults (position_id, role_id)
        SELECT pos.id, r.id FROM positions pos JOIN roles r ON r.code = 'manager'
        WHERE pos.code = 'MANAGER'
    """)

    # Seed sample resources
    op.execute("""
        INSERT INTO resources (id, code, name, type) VALUES
        (gen_random_uuid(), 'FS-SHARED',    'Общий файловый ресурс',  'file_share'),
        (gen_random_uuid(), 'APP-CRM',      'CRM система',             'application'),
        (gen_random_uuid(), 'APP-ERP',      'ERP система',             'application'),
        (gen_random_uuid(), 'DB-MAIN',      'Основная база данных',    'database'),
        (gen_random_uuid(), 'API-INTERNAL', 'Внутренний API',          'api')
    """)


def downgrade() -> None:
    op.drop_constraint("fk_user_role_request", "user_roles", type_="foreignkey")
    op.drop_table("processed_events")
    op.drop_table("position_role_defaults")
    op.drop_table("user_roles")
    op.drop_table("access_requests")
    op.drop_table("resources")
    op.drop_table("role_permissions")
    op.drop_table("permissions")
    op.drop_table("roles")
    op.execute("DROP TYPE access_request_status")
    op.execute("DROP TYPE resource_type")
