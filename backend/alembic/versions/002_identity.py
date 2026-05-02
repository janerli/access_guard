"""identity module — positions, departments, users_ext, lifecycle_events

Revision ID: 002
Revises: 001
Create Date: 2026-05-02
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enum types
    op.execute("CREATE TYPE user_status AS ENUM ('new', 'active', 'suspended', 'blocked', 'deleted')")
    op.execute("CREATE TYPE lifecycle_event_type AS ENUM ('hire', 'transfer', 'leave_start', 'leave_end', 'terminate')")
    op.execute("CREATE TYPE lifecycle_event_source AS ENUM ('hr_system', 'manual', 'scheduled')")
    op.execute("CREATE TYPE lifecycle_event_status AS ENUM ('pending', 'processed', 'failed')")

    # positions
    op.create_table(
        "positions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(100), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("level", sa.Integer(), nullable=False, server_default=sa.text("1")),
    )
    op.create_unique_constraint("uq_positions_code", "positions", ["code"])

    # departments (no FK to users_ext yet — added with ALTER below)
    op.create_table(
        "departments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(100), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("parent_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("departments.id"), nullable=True),
        sa.Column("manager_user_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_unique_constraint("uq_departments_code", "departments", ["code"])
    op.create_index("ix_departments_parent_id", "departments", ["parent_id"])

    # users_ext
    op.create_table(
        "users_ext",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("ldap_dn", sa.String(512), nullable=True),
        sa.Column("employee_id", sa.String(100), nullable=False),
        sa.Column("username", sa.String(100), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("position_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("positions.id"), nullable=True),
        sa.Column("department_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("departments.id"), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM(name="user_status", create_type=False),
            nullable=False,
            server_default=sa.text("'active'::user_status"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_unique_constraint("uq_users_ext_ldap_dn", "users_ext", ["ldap_dn"])
    op.create_unique_constraint("uq_users_ext_employee_id", "users_ext", ["employee_id"])
    op.create_unique_constraint("uq_users_ext_username", "users_ext", ["username"])
    op.create_index("ix_users_ext_status", "users_ext", ["status"])
    op.create_index("ix_users_ext_department_id", "users_ext", ["department_id"])

    # Add deferred FK from departments.manager_user_id → users_ext.id
    op.create_foreign_key(
        "fk_department_manager",
        "departments", "users_ext",
        ["manager_user_id"], ["id"],
        use_alter=True,
    )

    # lifecycle_events
    op.create_table(
        "lifecycle_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users_ext.id"), nullable=True),
        sa.Column(
            "event_type",
            postgresql.ENUM(name="lifecycle_event_type", create_type=False),
            nullable=False,
        ),
        sa.Column(
            "source",
            postgresql.ENUM(name="lifecycle_event_source", create_type=False),
            nullable=False,
        ),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM(name="lifecycle_event_status", create_type=False),
            nullable=False,
            server_default=sa.text("'pending'::lifecycle_event_status"),
        ),
        sa.Column("kafka_offset", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_lifecycle_events_user_id", "lifecycle_events", ["user_id"])
    op.create_index("ix_lifecycle_events_status", "lifecycle_events", ["status"])
    op.create_index("ix_lifecycle_events_event_type", "lifecycle_events", ["event_type"])

    # Seed positions and departments from HR-mock data
    op.execute("""
        INSERT INTO positions (id, code, name, level) VALUES
        (gen_random_uuid(), 'DEV-JUN',     'Разработчик (Junior)',      1),
        (gen_random_uuid(), 'DEV-MID',     'Разработчик (Middle)',      2),
        (gen_random_uuid(), 'DEV-SEN',     'Разработчик (Senior)',      3),
        (gen_random_uuid(), 'OPS-ENG',     'Инженер эксплуатации',     2),
        (gen_random_uuid(), 'HR-SPEC',     'HR-специалист',             2),
        (gen_random_uuid(), 'FIN-ANAL',    'Финансовый аналитик',       2),
        (gen_random_uuid(), 'SEC-ANALYST', 'Аналитик ИБ',               2),
        (gen_random_uuid(), 'MANAGER',     'Руководитель отдела',       4)
    """)

    op.execute("""
        INSERT INTO departments (id, code, name) VALUES
        (gen_random_uuid(), 'IT-DEV',   'Отдел разработки'),
        (gen_random_uuid(), 'IT-OPS',   'Отдел эксплуатации'),
        (gen_random_uuid(), 'HR',       'Отдел кадров'),
        (gen_random_uuid(), 'FINANCE',  'Финансовый отдел'),
        (gen_random_uuid(), 'SECURITY', 'Отдел информационной безопасности')
    """)


def downgrade() -> None:
    op.drop_constraint("fk_department_manager", "departments", type_="foreignkey")
    op.drop_table("lifecycle_events")
    op.drop_table("users_ext")
    op.drop_table("departments")
    op.drop_table("positions")
    op.execute("DROP TYPE lifecycle_event_status")
    op.execute("DROP TYPE lifecycle_event_source")
    op.execute("DROP TYPE lifecycle_event_type")
    op.execute("DROP TYPE user_status")
