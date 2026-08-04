from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


class ExamCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    exam_date: date
    total_score: float = Field(ge=0, le=1000)
    class_rank: int | None = Field(default=None, ge=1)
    grade_rank: int | None = Field(default=None, ge=1)
    scores: dict[str, float] = Field(default_factory=dict)


class ExamRead(ExamCreate):
    id: str

    model_config = {"from_attributes": True}


class ActionItem(BaseModel):
    title: str
    detail: str
    priority: Literal["high", "medium", "low"]


class Forecast(BaseModel):
    tier: str
    estimated_rank_range: tuple[int, int]
    target_gap: float | None
    confidence: Literal["low", "medium", "high"]
    basis: list[str]
    model_version: str
    reference_year: int


class DashboardResponse(BaseModel):
    student_name: str
    profile_complete: bool
    junior_school: str | None
    grade: str | None
    latest_exam: ExamRead | None
    forecast: Forecast | None
    action_items: list[ActionItem]
    trend: list[ExamRead]
    report: "AdmissionReport | None" = None


class StudentProfileUpdate(BaseModel):
    student_name: str = Field(min_length=1, max_length=64)
    junior_school: str = Field(min_length=1, max_length=128)
    grade: str = Field(default="初三", pattern="^(初一|初二|初三)$")
    target_school: str | None = Field(default=None, max_length=128)


class StudentProfileRead(BaseModel):
    id: str
    student_name: str
    junior_school: str | None
    grade: str | None
    target_school: str | None

    model_config = {"from_attributes": True}


class AdmissionReport(BaseModel):
    headline: str
    current_position: str
    trend_summary: str
    target_summary: str
    school_context: str
    policy_summary: str
    key_points: list[str]
    data_sources: list[str]


class ImportResponse(BaseModel):
    import_id: str
    status: str
    extraction: ExamCreate
    message: str
