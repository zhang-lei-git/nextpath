"""Add explicit admission region to student profiles."""
from alembic import op
import sqlalchemy as sa

revision = "20261025_07"
down_revision = "20260812_05"
branch_labels = None
depends_on = None

def upgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("student_profiles")}
    if "admission_region" not in columns:
        op.add_column("student_profiles", sa.Column("admission_region", sa.String(64), nullable=False, server_default="西安城六区"))

def downgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("student_profiles")}
    if "admission_region" in columns:
        with op.batch_alter_table("student_profiles") as batch:
            batch.drop_column("admission_region")
