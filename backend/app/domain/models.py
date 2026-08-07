from datetime import date, datetime
from uuid import uuid4

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class StudentProfile(Base):
    __tablename__ = "student_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    owner_id: Mapped[str] = mapped_column(String(64), index=True, unique=True)
    student_name: Mapped[str] = mapped_column(String(64))
    grade: Mapped[str] = mapped_column(String(16), default="初三")
    city: Mapped[str] = mapped_column(String(64), default="西安")
    junior_school: Mapped[str | None] = mapped_column(String(128), nullable=True)
    class_type_raw: Mapped[str | None] = mapped_column(String(80), nullable=True)
    class_type_standard: Mapped[str] = mapped_column(String(24), default="未知")
    target_school: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Exam(Base):
    __tablename__ = "exams"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    profile_id: Mapped[str] = mapped_column(ForeignKey("student_profiles.id"), index=True)
    name: Mapped[str] = mapped_column(String(80))
    exam_date: Mapped[date] = mapped_column(Date)
    total_score: Mapped[float] = mapped_column(Float)
    total_full_mark: Mapped[float | None] = mapped_column(Float, nullable=True)
    physical_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    class_rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    grade_rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    grade_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    exam_scope: Mapped[str | None] = mapped_column(String(120), nullable=True)
    participant_scope: Mapped[str | None] = mapped_column(String(32), nullable=True)
    participant_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    paper_version: Mapped[str | None] = mapped_column(String(80), nullable=True)
    scores: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ScoreImport(Base):
    __tablename__ = "score_imports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    profile_id: Mapped[str] = mapped_column(ForeignKey("student_profiles.id"), index=True)
    file_path: Mapped[str] = mapped_column(String(256))
    status: Mapped[str] = mapped_column(String(24), default="pending")
    extracted_payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class StudentReport(Base):
    __tablename__ = "student_reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    profile_id: Mapped[str] = mapped_column(ForeignKey("student_profiles.id"), index=True)
    exam_id: Mapped[str] = mapped_column(ForeignKey("exams.id"), index=True)
    analysis_run_id: Mapped[str | None] = mapped_column(ForeignKey("analysis_runs.id"), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(160))
    status: Mapped[str] = mapped_column(String(24), default="published", index=True)
    report_json: Mapped[dict] = mapped_column(JSON, default=dict)
    html_content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DataSource(Base):
    __tablename__ = "data_sources"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(160))
    source_type: Mapped[str] = mapped_column(String(32))
    reliability: Mapped[str] = mapped_column(String(24), default="observation")
    homepage_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DataEvidence(Base):
    __tablename__ = "data_evidence"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    source_id: Mapped[str | None] = mapped_column(ForeignKey("data_sources.id"), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(240))
    url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    file_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    excerpt: Mapped[str | None] = mapped_column(String(4000), nullable=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_by: Mapped[str] = mapped_column(String(64))


class DataIngestion(Base):
    __tablename__ = "data_ingestions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    source_id: Mapped[str | None] = mapped_column(ForeignKey("data_sources.id"), nullable=True, index=True)
    evidence_id: Mapped[str | None] = mapped_column(ForeignKey("data_evidence.id"), nullable=True, index=True)
    ingestion_type: Mapped[str] = mapped_column(String(32), index=True)
    title: Mapped[str] = mapped_column(String(240))
    original_filename: Mapped[str | None] = mapped_column(String(256), nullable=True)
    file_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    extraction_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    suggested_facts: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(24), default="captured", index=True)
    error_message: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    created_by: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CollectionJob(Base):
    __tablename__ = "collection_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    source_id: Mapped[str | None] = mapped_column(ForeignKey("data_sources.id"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(160))
    target_url: Mapped[str] = mapped_column(String(1024))
    collection_type: Mapped[str] = mapped_column(String(32), default="web_page", index=True)
    region: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    data_type: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    extraction_hint: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    interval_minutes: Mapped[int] = mapped_column(Integer, default=1440)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=30)
    max_retries: Mapped[int] = mapped_column(Integer, default=3)
    rate_limit_per_minute: Mapped[int] = mapped_column(Integer, default=10)
    parser_key: Mapped[str] = mapped_column(String(80), default="default")
    governance_rule_version: Mapped[str | None] = mapped_column(String(48), nullable=True)
    owner: Mapped[str | None] = mapped_column(String(64), nullable=True)
    priority: Mapped[int] = mapped_column(Integer, default=50, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_status: Mapped[str | None] = mapped_column(String(24), nullable=True)
    last_message: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DataFact(Base):
    __tablename__ = "data_facts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    fact_type: Mapped[str] = mapped_column(String(24), index=True)
    entity_name: Mapped[str] = mapped_column(String(160), index=True)
    field: Mapped[str] = mapped_column(String(80), index=True)
    region: Mapped[str] = mapped_column(String(80), index=True)
    reference_year: Mapped[int] = mapped_column(Integer, index=True)
    scope: Mapped[dict] = mapped_column(JSON, default=dict)
    value: Mapped[dict] = mapped_column(JSON, default=dict)
    evidence_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    confidence: Mapped[str] = mapped_column(String(24), default="observation")
    status: Mapped[str] = mapped_column(String(24), default="pending_review", index=True)
    review_note: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    created_by: Mapped[str] = mapped_column(String(64))
    reviewed_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DataRelease(Base):
    __tablename__ = "data_releases"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(160))
    region: Mapped[str] = mapped_column(String(80), index=True)
    reference_year: Mapped[int] = mapped_column(Integer, index=True)
    environment: Mapped[str] = mapped_column(String(24), default="production", index=True)
    data_purpose: Mapped[str] = mapped_column(String(32), default="forecast", index=True)
    usable_for_prediction: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    valid_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    published_by: Mapped[str] = mapped_column(String(64))
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DataReleaseItem(Base):
    __tablename__ = "data_release_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    release_id: Mapped[str] = mapped_column(ForeignKey("data_releases.id"), index=True)
    fact_id: Mapped[str] = mapped_column(ForeignKey("data_facts.id"), index=True)


class AnalysisModelVersion(Base):
    __tablename__ = "analysis_model_versions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(80), index=True)
    version: Mapped[str] = mapped_column(String(48), unique=True, index=True)
    analysis_type: Mapped[str] = mapped_column(String(32), default="position", index=True)
    region: Mapped[str] = mapped_column(String(80), default="西安", index=True)
    status: Mapped[str] = mapped_column(String(24), default="active", index=True)
    parameters: Mapped[dict] = mapped_column(JSON, default=dict)
    quality_metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AnalysisValidationRun(Base):
    __tablename__ = "analysis_validation_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    model_id: Mapped[str] = mapped_column(ForeignKey("analysis_model_versions.id"), index=True)
    data_release_id: Mapped[str | None] = mapped_column(ForeignKey("data_releases.id"), nullable=True, index=True)
    validation_year: Mapped[int] = mapped_column(Integer)
    sample_size: Mapped[int] = mapped_column(Integer, default=0)
    median_absolute_rank_error: Mapped[float | None] = mapped_column(Float, nullable=True)
    interval_coverage: Mapped[float | None] = mapped_column(Float, nullable=True)
    notes: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AnalysisRun(Base):
    __tablename__ = "analysis_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    fingerprint: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    profile_id: Mapped[str] = mapped_column(ForeignKey("student_profiles.id"), index=True)
    exam_id: Mapped[str] = mapped_column(ForeignKey("exams.id"), index=True)
    data_release_id: Mapped[str | None] = mapped_column(ForeignKey("data_releases.id"), nullable=True, index=True)
    model_id: Mapped[str] = mapped_column(ForeignKey("analysis_model_versions.id"), index=True)
    exam_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    data_cutoff_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(24), default="completed", index=True)
    model_versions: Mapped[dict] = mapped_column(JSON, default=dict)
    input_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PositionCalibrationSample(Base):
    """An anonymized historical mapping from a junior-school rank to city rank."""

    __tablename__ = "position_calibration_samples"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    region: Mapped[str] = mapped_column(String(80), index=True)
    junior_school: Mapped[str] = mapped_column(String(128), index=True)
    class_type_raw: Mapped[str | None] = mapped_column(String(80), nullable=True)
    class_type_standard: Mapped[str] = mapped_column(String(24), default="未知", index=True)
    assessment_stage: Mapped[str] = mapped_column(String(32), index=True)
    assessment_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    cohort_year: Mapped[int] = mapped_column(Integer, index=True)
    mock_total_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    mock_full_mark: Mapped[float | None] = mapped_column(Float, nullable=True)
    grade_rank: Mapped[int] = mapped_column(Integer)
    grade_size: Mapped[int] = mapped_column(Integer)
    final_total_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    final_city_rank: Mapped[int] = mapped_column(Integer)
    final_candidate_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    evidence_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    source_note: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    status: Mapped[str] = mapped_column(String(24), default="pending_review", index=True)
    review_note: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CollectionRun(Base):
    __tablename__ = "collection_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    job_id: Mapped[str] = mapped_column(ForeignKey("collection_jobs.id"), index=True)
    trigger_type: Mapped[str] = mapped_column(String(24), default="scheduled", index=True)
    status: Mapped[str] = mapped_column(String(24), default="scheduled", index=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    attempt: Mapped[int] = mapped_column(Integer, default=1)
    item_count: Mapped[int] = mapped_column(Integer, default=0)
    changed_count: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SourceSnapshot(Base):
    __tablename__ = "source_snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    run_id: Mapped[str] = mapped_column(ForeignKey("collection_runs.id"), index=True)
    evidence_id: Mapped[str | None] = mapped_column(ForeignKey("data_evidence.id"), nullable=True, index=True)
    source_url: Mapped[str] = mapped_column(String(1024))
    final_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    response_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    attachment_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    structure_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    storage_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    change_type: Mapped[str] = mapped_column(String(24), default="new", index=True)
    diff_summary: Mapped[dict] = mapped_column(JSON, default=dict)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ProcessingStep(Base):
    __tablename__ = "processing_steps"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    run_id: Mapped[str] = mapped_column(ForeignKey("collection_runs.id"), index=True)
    snapshot_id: Mapped[str | None] = mapped_column(ForeignKey("source_snapshots.id"), nullable=True, index=True)
    step_name: Mapped[str] = mapped_column(String(40), index=True)
    status: Mapped[str] = mapped_column(String(24), index=True)
    processor_version: Mapped[str | None] = mapped_column(String(80), nullable=True)
    input_payload: Mapped[dict] = mapped_column(JSON, default=dict)
    output_payload: Mapped[dict] = mapped_column(JSON, default=dict)
    error_message: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class GovernanceRuleVersion(Base):
    __tablename__ = "governance_rule_versions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(120), index=True)
    version: Mapped[str] = mapped_column(String(48), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(24), default="active", index=True)
    rules: Mapped[dict] = mapped_column(JSON, default=dict)
    created_by: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DataGap(Base):
    __tablename__ = "data_gaps"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    region: Mapped[str] = mapped_column(String(80), index=True)
    junior_school: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    class_type_standard: Mapped[str | None] = mapped_column(String(24), nullable=True, index=True)
    assessment_stage: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    gap_type: Mapped[str] = mapped_column(String(48), index=True)
    affected_users: Mapped[int] = mapped_column(Integer, default=1)
    priority_score: Mapped[float] = mapped_column(Float, default=0)
    status: Mapped[str] = mapped_column(String(24), default="open", index=True)
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class OutcomeSample(Base):
    __tablename__ = "outcome_samples"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    anonymous_student_id: Mapped[str] = mapped_column(String(64), index=True)
    consent_id: Mapped[str | None] = mapped_column(ForeignKey("consent_records.id"), nullable=True, index=True)
    region: Mapped[str] = mapped_column(String(80), index=True)
    junior_school: Mapped[str] = mapped_column(String(128), index=True)
    class_type_standard: Mapped[str] = mapped_column(String(24), default="未知", index=True)
    cohort_year: Mapped[int] = mapped_column(Integer, index=True)
    assessment_stage: Mapped[str] = mapped_column(String(32), index=True)
    assessment_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    mock_total_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    mock_full_mark: Mapped[float | None] = mapped_column(Float, nullable=True)
    grade_rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    grade_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    final_total_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    final_city_rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    final_candidate_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(24), default="pending_review", index=True)
    evidence_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ConsentRecord(Base):
    __tablename__ = "consent_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    owner_id: Mapped[str] = mapped_column(String(64), index=True)
    profile_id: Mapped[str | None] = mapped_column(ForeignKey("student_profiles.id"), nullable=True, index=True)
    purpose: Mapped[str] = mapped_column(String(32), index=True)
    status: Mapped[str] = mapped_column(String(24), default="granted", index=True)
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    retain_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class OperationAlert(Base):
    __tablename__ = "operation_alerts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    alert_type: Mapped[str] = mapped_column(String(40), index=True)
    severity: Mapped[str] = mapped_column(String(16), default="medium", index=True)
    source_id: Mapped[str | None] = mapped_column(ForeignKey("data_sources.id"), nullable=True, index=True)
    job_id: Mapped[str | None] = mapped_column(ForeignKey("collection_jobs.id"), nullable=True, index=True)
    run_id: Mapped[str | None] = mapped_column(ForeignKey("collection_runs.id"), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(24), default="open", index=True)
    title: Mapped[str] = mapped_column(String(240))
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
