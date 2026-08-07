"""adopt migrations and add the data foundation

Revision ID: 20260807_01
Revises:
Create Date: 2026-08-07
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from app.domain.models import Base


revision: str = "20260807_01"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _columns(table_name: str) -> set[str]:
    return {item["name"] for item in sa.inspect(op.get_bind()).get_columns(table_name)}


def _add_column(table_name: str, column: sa.Column) -> None:
    if column.name not in _columns(table_name):
        op.add_column(table_name, column)


def _indexes(table_name: str) -> set[str]:
    return {item["name"] for item in sa.inspect(op.get_bind()).get_indexes(table_name)}


def _add_index(name: str, table_name: str, columns: list[str]) -> None:
    if name not in _indexes(table_name):
        op.create_index(name, table_name, columns)


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)

    _add_column("student_profiles", sa.Column("grade", sa.String(16), nullable=False, server_default="初三"))
    _add_column("student_profiles", sa.Column("class_type_raw", sa.String(80), nullable=True))
    _add_column("student_profiles", sa.Column("class_type_standard", sa.String(24), nullable=False, server_default="未知"))

    _add_column("exams", sa.Column("grade_size", sa.Integer(), nullable=True))
    _add_column("exams", sa.Column("total_full_mark", sa.Float(), nullable=True))
    _add_column("exams", sa.Column("physical_score", sa.Float(), nullable=True))
    _add_column("exams", sa.Column("exam_scope", sa.String(120), nullable=True))
    _add_column("exams", sa.Column("participant_scope", sa.String(32), nullable=True))
    _add_column("exams", sa.Column("participant_count", sa.Integer(), nullable=True))
    _add_column("exams", sa.Column("paper_version", sa.String(80), nullable=True))

    for column in (
        sa.Column("collection_type", sa.String(32), nullable=False, server_default="web_page"),
        sa.Column("region", sa.String(80), nullable=True),
        sa.Column("data_type", sa.String(32), nullable=True),
        sa.Column("timeout_seconds", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("max_retries", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("rate_limit_per_minute", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("parser_key", sa.String(80), nullable=False, server_default="default"),
        sa.Column("governance_rule_version", sa.String(48), nullable=True),
        sa.Column("owner", sa.String(64), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="50"),
    ):
        _add_column("collection_jobs", column)

    for column in (
        sa.Column("environment", sa.String(24), nullable=False, server_default="test"),
        sa.Column("data_purpose", sa.String(32), nullable=False, server_default="demo_or_backtest"),
        sa.Column("usable_for_prediction", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
    ):
        _add_column("data_releases", column)
    bind.execute(sa.text(
        "UPDATE data_releases SET environment='test', data_purpose='demo_or_backtest', usable_for_prediction=0"
    ))

    for column in (
        sa.Column("exam_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("data_cutoff_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(24), nullable=False, server_default="completed"),
        sa.Column("model_versions", sa.JSON(), nullable=False, server_default="{}"),
    ):
        _add_column("analysis_runs", column)
    bind.execute(sa.text("UPDATE analysis_runs SET run_at=created_at WHERE run_at IS NULL"))

    for column in (
        sa.Column("class_type_raw", sa.String(80), nullable=True),
        sa.Column("class_type_standard", sa.String(24), nullable=False, server_default="未知"),
        sa.Column("assessment_date", sa.Date(), nullable=True),
        sa.Column("mock_total_score", sa.Float(), nullable=True),
        sa.Column("mock_full_mark", sa.Float(), nullable=True),
        sa.Column("final_total_score", sa.Float(), nullable=True),
        sa.Column("final_candidate_count", sa.Integer(), nullable=True),
    ):
        _add_column("position_calibration_samples", column)

    for name, table_name, columns in (
        ("ix_collection_jobs_collection_type", "collection_jobs", ["collection_type"]),
        ("ix_collection_jobs_region", "collection_jobs", ["region"]),
        ("ix_collection_jobs_data_type", "collection_jobs", ["data_type"]),
        ("ix_collection_jobs_priority", "collection_jobs", ["priority"]),
        ("ix_data_releases_environment", "data_releases", ["environment"]),
        ("ix_data_releases_data_purpose", "data_releases", ["data_purpose"]),
        ("ix_data_releases_usable_for_prediction", "data_releases", ["usable_for_prediction"]),
        ("ix_analysis_runs_data_cutoff_at", "analysis_runs", ["data_cutoff_at"]),
        ("ix_analysis_runs_status", "analysis_runs", ["status"]),
        ("ix_position_calibration_samples_class_type_standard", "position_calibration_samples", ["class_type_standard"]),
    ):
        _add_index(name, table_name, columns)


def _drop_column(table_name: str, column_name: str) -> None:
    if column_name in _columns(table_name):
        with op.batch_alter_table(table_name) as batch:
            batch.drop_column(column_name)


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    tables = set(inspector.get_table_names())
    for index_name, table_name in (
        ("ix_position_calibration_samples_class_type_standard", "position_calibration_samples"),
        ("ix_analysis_runs_status", "analysis_runs"),
        ("ix_analysis_runs_data_cutoff_at", "analysis_runs"),
        ("ix_data_releases_usable_for_prediction", "data_releases"),
        ("ix_data_releases_data_purpose", "data_releases"),
        ("ix_data_releases_environment", "data_releases"),
        ("ix_collection_jobs_priority", "collection_jobs"),
        ("ix_collection_jobs_data_type", "collection_jobs"),
        ("ix_collection_jobs_region", "collection_jobs"),
        ("ix_collection_jobs_collection_type", "collection_jobs"),
    ):
        if table_name in tables and index_name in _indexes(table_name):
            op.drop_index(index_name, table_name=table_name)

    for table_name in (
        "operation_alerts",
        "outcome_samples",
        "consent_records",
        "data_gaps",
        "processing_steps",
        "source_snapshots",
        "collection_runs",
        "governance_rule_versions",
    ):
        if table_name in tables:
            op.drop_table(table_name)

    for table_name, columns in (
        ("position_calibration_samples", ["class_type_raw", "class_type_standard", "assessment_date", "mock_total_score", "mock_full_mark", "final_total_score", "final_candidate_count"]),
        ("analysis_runs", ["exam_at", "run_at", "data_cutoff_at", "status", "model_versions"]),
        ("data_releases", ["environment", "data_purpose", "usable_for_prediction", "valid_from", "valid_until"]),
        ("collection_jobs", ["collection_type", "region", "data_type", "timeout_seconds", "max_retries", "rate_limit_per_minute", "parser_key", "governance_rule_version", "owner", "priority"]),
        ("exams", ["exam_scope", "participant_scope", "participant_count", "paper_version"]),
        ("student_profiles", ["class_type_raw", "class_type_standard"]),
    ):
        for column_name in columns:
            _drop_column(table_name, column_name)
