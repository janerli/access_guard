"""indexes and constraints — actor_username index, correlation_id index,
users_ext email unique, FK for decided_by and granted_by

Revision ID: 006
Revises: 005
Create Date: 2026-06-02
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── audit_log: индексы для правил выявления и поиска ──────────────────────
    # check_multiple_failed_logins делает WHERE actor_username = X — без индекса full scan
    op.create_index("ix_audit_log_actor_username", "audit_log", ["actor_username"])
    # поиск связанных событий по correlation_id
    op.create_index("ix_audit_log_correlation_id", "audit_log", ["correlation_id"])

    # ── users_ext: уникальность email ────────────────────────────────────────
    # Два сотрудника с одним email невозможно — добавляем ограничение.
    # На свежей БД это всегда проходит (seed генерирует уникальные email).
    op.create_unique_constraint("uq_users_ext_email", "users_ext", ["email"])

    # ── access_requests.decided_by → admin_users ─────────────────────────────
    op.create_foreign_key(
        "fk_access_requests_decided_by",
        "access_requests", "admin_users",
        ["decided_by"], ["id"],
        ondelete="SET NULL",
        use_alter=True,
    )

    # ── user_roles.granted_by → admin_users ──────────────────────────────────
    op.create_foreign_key(
        "fk_user_roles_granted_by",
        "user_roles", "admin_users",
        ["granted_by"], ["id"],
        ondelete="SET NULL",
        use_alter=True,
    )


def downgrade() -> None:
    op.drop_constraint("fk_user_roles_granted_by", "user_roles", type_="foreignkey")
    op.drop_constraint("fk_access_requests_decided_by", "access_requests", type_="foreignkey")
    op.drop_constraint("uq_users_ext_email", "users_ext", type_="unique")
    op.drop_index("ix_audit_log_correlation_id", table_name="audit_log")
    op.drop_index("ix_audit_log_actor_username", table_name="audit_log")
