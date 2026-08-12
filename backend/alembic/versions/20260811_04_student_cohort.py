"""add the graduating cohort to student profiles

Revision ID: 20260811_04
Revises: 20260809_03
Create Date: 2026-08-11
"""
from alembic import op
import sqlalchemy as sa


revision = "20260811_04"
down_revision = "20260809_03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("student_profiles")}
    if "cohort_year" not in columns:
        op.add_column("student_profiles", sa.Column("cohort_year", sa.Integer(), nullable=False, server_default="2026"))


def downgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("student_profiles")}
    if "cohort_year" in columns:
        with op.batch_alter_table("student_profiles") as batch:
            batch.drop_column("cohort_year")
