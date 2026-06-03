"""reports.requested_by FK: users_ext → admin_users

Revision ID: 007
Revises: 006
Create Date: 2026-06-03
"""
from typing import Sequence, Union

from alembic import op

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop the old FK that wrongly pointed to users_ext
    op.drop_constraint("reports_requested_by_fkey", "reports", type_="foreignkey")

    # Add correct FK → admin_users
    op.create_foreign_key(
        "fk_reports_requested_by_admin",
        "reports", "admin_users",
        ["requested_by"], ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_reports_requested_by_admin", "reports", type_="foreignkey")
    op.create_foreign_key(
        "reports_requested_by_fkey",
        "reports", "users_ext",
        ["requested_by"], ["id"],
        ondelete="SET NULL",
    )
