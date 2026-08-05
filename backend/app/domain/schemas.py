from datetime import date, datetime
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


SourceType = Literal["official", "school_official", "media", "expert", "parent", "manual"]
Reliability = Literal["official", "verified", "observation"]
FactType = Literal["school", "admission", "policy"]
FactStatus = Literal["pending_review", "approved", "rejected"]


class DataSourceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    source_type: SourceType
    reliability: Reliability = "observation"
    homepage_url: str | None = Field(default=None, max_length=512)


class DataSourceRead(DataSourceCreate):
    id: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class EvidenceCreate(BaseModel):
    source_id: str | None = None
    title: str = Field(min_length=1, max_length=240)
    url: str | None = Field(default=None, max_length=1024)
    file_path: str | None = Field(default=None, max_length=512)
    excerpt: str | None = Field(default=None, max_length=4000)


class EvidenceRead(EvidenceCreate):
    id: str
    captured_at: datetime
    source_name: str | None = None
    source_type: SourceType | None = None

    model_config = {"from_attributes": True}


class DataFactCreate(BaseModel):
    fact_type: FactType
    entity_name: str = Field(min_length=1, max_length=160)
    field: str = Field(min_length=1, max_length=80)
    region: str = Field(min_length=1, max_length=80)
    reference_year: int = Field(ge=2020, le=2100)
    scope: dict = Field(default_factory=dict)
    value: dict = Field(default_factory=dict)
    evidence_ids: list[str] = Field(default_factory=list)
    confidence: Reliability = "observation"


class DataFactReview(BaseModel):
    decision: Literal["approved", "rejected"]
    note: str | None = Field(default=None, max_length=2000)


class DataFactRead(DataFactCreate):
    id: str
    status: FactStatus
    review_note: str | None
    created_at: datetime
    reviewed_at: datetime | None

    model_config = {"from_attributes": True}


class DataReleaseCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    region: str = Field(min_length=1, max_length=80)
    reference_year: int = Field(ge=2020, le=2100)
    fact_ids: list[str] = Field(min_length=1)
    notes: str | None = Field(default=None, max_length=2000)


class DataReleaseRead(BaseModel):
    id: str
    name: str
    region: str
    reference_year: int
    notes: str | None
    published_at: datetime
    fact_count: int = 0

    model_config = {"from_attributes": True}


class ConsumerFact(BaseModel):
    id: str
    fact_type: FactType
    entity_name: str
    field: str
    region: str
    reference_year: int
    scope: dict
    value: dict
    confidence: Reliability
    evidence: list[EvidenceRead]


class ConsumerDataResponse(BaseModel):
    release: DataReleaseRead | None
    facts: list[ConsumerFact]
