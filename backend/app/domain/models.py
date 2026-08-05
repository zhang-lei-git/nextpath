from datetime import date, datetime
from uuid import uuid4

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, JSON, String, func
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
    target_school: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Exam(Base):
    __tablename__ = "exams"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    profile_id: Mapped[str] = mapped_column(ForeignKey("student_profiles.id"), index=True)
    name: Mapped[str] = mapped_column(String(80))
    exam_date: Mapped[date] = mapped_column(Date)
    total_score: Mapped[float] = mapped_column(Float)
    class_rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    grade_rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
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
    input_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
