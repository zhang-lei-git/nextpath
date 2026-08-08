"""store exam totals with physical education included

Revision ID: 20260809_03
Revises: 20260808_02
Create Date: 2026-08-09
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260809_03"
down_revision: Union[str, None] = "20260808_02"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    columns = {item["name"] for item in sa.inspect(op.get_bind()).get_columns("exams")}
    if "score_includes_pe" not in columns:
        op.add_column("exams", sa.Column("score_includes_pe", sa.Boolean(), nullable=False, server_default=sa.true()))
        op.execute("UPDATE exams SET total_score = total_score + COALESCE(physical_score, 60), score_includes_pe = 1")


def downgrade() -> None:
    columns = {item["name"] for item in sa.inspect(op.get_bind()).get_columns("exams")}
    if "score_includes_pe" in columns:
        op.execute("UPDATE exams SET total_score = total_score - COALESCE(physical_score, 60) WHERE score_includes_pe = 1")
        with op.batch_alter_table("exams") as batch:
            batch.drop_column("score_includes_pe")
