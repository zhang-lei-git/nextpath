"""mark non-standard examinations

Revision ID: 20260812_05
Revises: 20260811_04
"""
from alembic import op
import sqlalchemy as sa

revision = "20260812_05"
down_revision = "20260811_04"
branch_labels = None
depends_on = None

def upgrade() -> None:
    columns = {row["name"] for row in sa.inspect(op.get_bind()).get_columns("exams")}
    if "comparison_mode" not in columns:
        op.add_column("exams", sa.Column("comparison_mode", sa.String(24), nullable=False, server_default="standard"))

def downgrade() -> None:
    columns = {row["name"] for row in sa.inspect(op.get_bind()).get_columns("exams")}
    if "comparison_mode" in columns:
        with op.batch_alter_table("exams") as batch:
            batch.drop_column("comparison_mode")
