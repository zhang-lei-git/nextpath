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
