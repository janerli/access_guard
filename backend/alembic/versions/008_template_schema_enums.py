"""Add enum values to report template parameter schemas

Revision ID: 008
Revises: 007
Create Date: 2026-06-04
"""
from typing import Sequence, Union
from alembic import op

revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # access_requests_report: добавить enum для поля status
    op.execute("""
        UPDATE report_templates
        SET parameters_schema = jsonb_set(
            parameters_schema,
            '{properties,status}',
            '{"type":"string","title":"Статус заявки","enum":["pending","approved","rejected","cancelled"]}'::jsonb
        )
        WHERE code = 'access_requests_report'
    """)

    # security_incidents: добавить enum для поля severity
    op.execute("""
        UPDATE report_templates
        SET parameters_schema = jsonb_set(
            parameters_schema,
            '{properties,severity}',
            '{"type":"string","title":"Серьёзность","enum":["low","medium","high","critical"]}'::jsonb
        )
        WHERE code = 'security_incidents'
    """)


def downgrade() -> None:
    op.execute("""
        UPDATE report_templates
        SET parameters_schema = jsonb_set(
            parameters_schema,
            '{properties,status}',
            '{"type":"string","title":"Статус заявки"}'::jsonb
        )
        WHERE code = 'access_requests_report'
    """)
    op.execute("""
        UPDATE report_templates
        SET parameters_schema = jsonb_set(
            parameters_schema,
            '{properties,severity}',
            '{"type":"string","title":"Severity"}'::jsonb
        )
        WHERE code = 'security_incidents'
    """)
