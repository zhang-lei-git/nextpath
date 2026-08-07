"""add monthly report identity

Revision ID: 20260808_02
Revises: 20260807_01
Create Date: 2026-08-08
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260808_02"
down_revision: Union[str, None] = "20260807_01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _columns() -> set[str]:
    return {item["name"] for item in sa.inspect(op.get_bind()).get_columns("student_reports")}


def upgrade() -> None:
    columns = _columns()
    if "report_type" not in columns:
        op.add_column("student_reports", sa.Column("report_type", sa.String(24), nullable=False, server_default="exam"))
    if "period_key" not in columns:
        op.add_column("student_reports", sa.Column("period_key", sa.String(16), nullable=True))
    indexes = {item["name"] for item in sa.inspect(op.get_bind()).get_indexes("student_reports")}
    if "ix_student_reports_report_type" not in indexes:
        op.create_index("ix_student_reports_report_type", "student_reports", ["report_type"])
    if "ix_student_reports_period_key" not in indexes:
        op.create_index("ix_student_reports_period_key", "student_reports", ["period_key"])
    unique_constraints = {item["name"] for item in sa.inspect(op.get_bind()).get_unique_constraints("student_reports")}
    if "uq_student_report_period" not in unique_constraints:
        with op.batch_alter_table("student_reports") as batch:
            batch.create_unique_constraint("uq_student_report_period", ["profile_id", "report_type", "period_key"])


def downgrade() -> None:
    with op.batch_alter_table("student_reports") as batch:
        batch.drop_constraint("uq_student_report_period", type_="unique")
        batch.drop_index("ix_student_reports_period_key")
        batch.drop_index("ix_student_reports_report_type")
        batch.drop_column("period_key")
        batch.drop_column("report_type")
