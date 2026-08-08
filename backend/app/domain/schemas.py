from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class ExamCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    exam_date: date
    total_score: float = Field(ge=0, le=1000)
    total_full_mark: float | None = Field(default=None, gt=0, le=1000)
    physical_score: float | None = Field(default=60, ge=0, le=60)
    class_rank: int | None = Field(default=None, ge=1)
    grade_rank: int | None = Field(default=None, ge=1)
    grade_size: int | None = Field(default=None, ge=1)
    exam_scope: str | None = Field(default=None, max_length=120)
    participant_scope: str | None = Field(default=None, max_length=32)
    participant_count: int | None = Field(default=None, ge=1)
    paper_version: str | None = Field(default=None, max_length=80)
    scores: dict[str, float] = Field(default_factory=dict)

    @model_validator(mode="after")
    def grade_rank_is_within_grade_size(self) -> "ExamCreate":
        if self.physical_score is None:
            self.physical_score = 60
        if self.grade_rank and self.grade_size and self.grade_rank > self.grade_size:
            raise ValueError("年级排名不能大于年级人数")
        if self.participant_count and self.grade_size and self.participant_scope == "年级" and self.participant_count != self.grade_size:
            raise ValueError("参与范围为年级时，参考人数应与年级人数一致")
        return self


class ExamRead(ExamCreate):
    id: str

    model_config = {"from_attributes": True}


class ExamUpdate(ExamCreate):
    pass


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
    current_rank: int | None = None
    target_rank: int | None = None
    target_rank_gap: int | None = None
    position_note: str | None = None
    estimated_percentile_range: tuple[float, float] | None = None
    current_percentile: float | None = None
    target_percentile: float | None = None
    target_percentile_gap: float | None = None
    projected_total_range: tuple[float, float] | None = None
    historical_equivalent_score_range: tuple[float, float] | None = None
    score_bridge_method: str | None = None
    score_bridge_source: str | None = None
    position_method: str | None = None
    position_channels: dict[str, dict] = Field(default_factory=dict)
    position_conflict_pp: float | None = None
    current_snapshot: "ForecastScenario | None" = None
    reasonable_projection: "ForecastScenario | None" = None
    prediction_level: Literal["complete", "basic", "unavailable"] = "basic"
    target_comparison: "TargetComparison | None" = None
    school_tiers: dict[str, list[str]] = Field(default_factory=lambda: {"reach": [], "match": [], "safe": []})
    missing_inputs: list[str] = Field(default_factory=list)


class ForecastScenario(BaseModel):
    title: str
    total_range: tuple[float, float] | None = None
    total_full_mark: float | None = None
    tier: str
    estimated_rank_range: tuple[int, int] = (0, 0)
    estimated_percentile_range: tuple[float, float] | None = None
    current_percentile: float | None = None
    target_percentile_gap: float | None = None
    target_rank_gap: int | None = None
    summary: str
    confidence: Literal["low", "medium", "high"] = "low"
    range_usable: bool = False
    parent_reasons: list[str] = Field(default_factory=list)


class TargetComparison(BaseModel):
    school: str
    school_rank_range: tuple[int, int] | None = None
    current_gap_rank_range: tuple[int, int] | None = None
    projected_gap_rank_range: tuple[int, int] | None = None
    risk: Literal["已进入", "稳妥", "匹配", "边界冲刺", "仍有差距", "数据不足"]
    current_relation: str | None = None
    projected_relation: str | None = None


class DashboardResponse(BaseModel):
    student_name: str
    profile_complete: bool
    junior_school: str | None
    grade: str | None
    target_school: str | None
    latest_exam: ExamRead | None
    forecast: Forecast | None
    action_items: list[ActionItem]
    trend: list[ExamRead]
    report: "AdmissionReport | None" = None


class StudentProfileUpdate(BaseModel):
    student_name: str = Field(min_length=1, max_length=64)
    junior_school: str = Field(min_length=1, max_length=128)
    grade: str = Field(default="初三", pattern="^(初一|初二|初三)$")
    class_type_raw: str | None = Field(default=None, max_length=80)
    class_type_standard: Literal["创新", "重点", "平行", "未知"] = "未知"
    target_school: str | None = Field(default=None, max_length=128)


class StudentProfileRead(BaseModel):
    id: str
    student_name: str
    junior_school: str | None
    grade: str | None
    class_type_raw: str | None
    class_type_standard: str
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


class StudentReportRead(BaseModel):
    id: str
    exam_id: str
    title: str
    status: str
    report_type: Literal["exam", "monthly"] = "exam"
    period_key: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class StudentReportDetail(StudentReportRead):
    content: dict


class StudentReportAccess(BaseModel):
    url: str
    expires_in: int


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


class DataIngestionRead(BaseModel):
    id: str
    source_id: str | None
    evidence_id: str | None
    ingestion_type: str
    title: str
    original_filename: str | None
    file_path: str | None
    source_url: str | None
    extraction_text: str | None
    suggested_facts: list
    status: str
    error_message: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class CollectionJobCreate(BaseModel):
    source_id: str | None = None
    name: str = Field(min_length=1, max_length=160)
    target_url: str = Field(min_length=8, max_length=1024, pattern=r"^https?://")
    collection_type: str = Field(default="web_page", max_length=32)
    region: str | None = Field(default=None, max_length=80)
    data_type: str | None = Field(default=None, max_length=32)
    extraction_hint: str | None = Field(default=None, max_length=1000)
    interval_minutes: int = Field(default=1440, ge=15, le=10080)
    timeout_seconds: int = Field(default=30, ge=5, le=300)
    max_retries: int = Field(default=3, ge=0, le=10)
    rate_limit_per_minute: int = Field(default=10, ge=1, le=120)
    parser_key: str = Field(default="default", max_length=80)
    governance_rule_version: str | None = Field(default=None, max_length=48)
    owner: str | None = Field(default=None, max_length=64)
    priority: int = Field(default=50, ge=0, le=100)
    is_active: bool = True


class CollectionJobUpdate(BaseModel):
    source_id: str | None = None
    name: str | None = Field(default=None, min_length=1, max_length=160)
    target_url: str | None = Field(default=None, min_length=8, max_length=1024, pattern=r"^https?://")
    collection_type: str | None = Field(default=None, max_length=32)
    region: str | None = Field(default=None, max_length=80)
    data_type: str | None = Field(default=None, max_length=32)
    extraction_hint: str | None = Field(default=None, max_length=1000)
    interval_minutes: int | None = Field(default=None, ge=15, le=10080)
    timeout_seconds: int | None = Field(default=None, ge=5, le=300)
    max_retries: int | None = Field(default=None, ge=0, le=10)
    rate_limit_per_minute: int | None = Field(default=None, ge=1, le=120)
    parser_key: str | None = Field(default=None, max_length=80)
    governance_rule_version: str | None = Field(default=None, max_length=48)
    owner: str | None = Field(default=None, max_length=64)
    priority: int | None = Field(default=None, ge=0, le=100)
    is_active: bool | None = None


class CollectionJobRead(CollectionJobCreate):
    id: str
    last_run_at: datetime | None
    last_status: str | None
    last_message: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class SourceSnapshotRead(BaseModel):
    id: str
    run_id: str
    evidence_id: str | None
    source_url: str
    final_url: str | None
    response_status: int | None
    content_hash: str | None
    attachment_hash: str | None
    structure_hash: str | None
    storage_path: str | None
    change_type: str
    diff_summary: dict
    captured_at: datetime

    model_config = {"from_attributes": True}


class ProcessingStepRead(BaseModel):
    id: str
    run_id: str
    snapshot_id: str | None
    step_name: str
    status: str
    processor_version: str | None
    input_payload: dict
    output_payload: dict
    error_message: str | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class CollectionRunRead(BaseModel):
    id: str
    job_id: str
    trigger_type: str
    status: str
    idempotency_key: str
    attempt: int
    item_count: int
    changed_count: int
    error_message: str | None
    scheduled_at: datetime | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class CollectionRunDetail(CollectionRunRead):
    snapshots: list[SourceSnapshotRead] = Field(default_factory=list)
    steps: list[ProcessingStepRead] = Field(default_factory=list)


class CollectionReprocessRequest(BaseModel):
    parser_key: str | None = Field(default=None, max_length=80)
    governance_rule_version: str | None = Field(default=None, max_length=48)


class GovernanceRuleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    version: str = Field(min_length=1, max_length=48, pattern=r"^[A-Za-z0-9._-]+$")
    status: Literal["active", "inactive"] = "active"
    rules: dict = Field(default_factory=dict)


class GovernanceRuleRead(GovernanceRuleCreate):
    id: str
    created_by: str
    created_at: datetime

    model_config = {"from_attributes": True}


class OperationAlertRead(BaseModel):
    id: str
    alert_type: str
    severity: str
    source_id: str | None
    job_id: str | None
    run_id: str | None
    status: str
    title: str
    details: dict
    created_at: datetime
    resolved_at: datetime | None

    model_config = {"from_attributes": True}


class OperationAlertUpdate(BaseModel):
    status: Literal["open", "resolved"]


class DataGapCreate(BaseModel):
    region: str = Field(min_length=1, max_length=80)
    junior_school: str | None = Field(default=None, max_length=128)
    class_type_standard: str | None = Field(default=None, max_length=24)
    assessment_stage: str | None = Field(default=None, max_length=32)
    gap_type: str = Field(min_length=1, max_length=48)
    affected_users: int = Field(default=1, ge=1, le=1_000_000)
    details: dict = Field(default_factory=dict)


class DataGapRead(DataGapCreate):
    id: str
    priority_score: float
    status: Literal["open", "resolved"]
    created_at: datetime
    resolved_at: datetime | None

    model_config = {"from_attributes": True}


class DataGapUpdate(BaseModel):
    status: Literal["open", "resolved"]


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
    environment: Literal["production", "test"] = "production"
    data_purpose: Literal["forecast", "demo_or_backtest", "backtest_only"] = "forecast"
    usable_for_prediction: bool = True
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    notes: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def prediction_usage_matches_environment(self) -> "DataReleaseCreate":
        if self.usable_for_prediction and (self.environment != "production" or self.data_purpose != "forecast"):
            raise ValueError("只有 production/forecast 发布版本可以用于预测")
        if self.valid_from and self.valid_until and self.valid_until <= self.valid_from:
            raise ValueError("失效时间必须晚于生效时间")
        return self


class DataReleaseRead(BaseModel):
    id: str
    name: str
    region: str
    reference_year: int
    environment: str
    data_purpose: str
    usable_for_prediction: bool
    valid_from: datetime | None
    valid_until: datetime | None
    notes: str | None
    published_at: datetime
    fact_count: int = 0

    model_config = {"from_attributes": True}


class FactLineageRead(BaseModel):
    fact: DataFactRead
    evidence: list[EvidenceRead]
    snapshots: list[SourceSnapshotRead]
    steps: list[ProcessingStepRead]
    releases: list[DataReleaseRead]


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


class AnalysisModelUpdate(BaseModel):
    parameters: dict = Field(default_factory=dict)
    status: Literal["active", "inactive"] = "active"


class AnalysisModelRead(BaseModel):
    id: str
    name: str
    version: str
    analysis_type: str
    region: str
    status: str
    parameters: dict
    quality_metrics: dict
    created_at: datetime

    model_config = {"from_attributes": True}


class AnalysisValidationCreate(BaseModel):
    data_release_id: str | None = None
    validation_year: int = Field(ge=2020, le=2100)
    sample_size: int = Field(default=0, ge=0)
    median_absolute_rank_error: float | None = Field(default=None, ge=0)
    interval_coverage: float | None = Field(default=None, ge=0, le=1)
    notes: str | None = Field(default=None, max_length=2000)


class AnalysisValidationRead(AnalysisValidationCreate):
    id: str
    model_id: str
    created_at: datetime

    model_config = {"from_attributes": True}


CalibrationStatus = Literal["pending_review", "approved", "rejected"]


class PositionCalibrationSampleCreate(BaseModel):
    region: str = Field(default="西安", min_length=1, max_length=80)
    junior_school: str = Field(min_length=1, max_length=128)
    class_type_raw: str | None = Field(default=None, max_length=80)
    class_type_standard: Literal["创新", "重点", "平行", "未知"] = "未知"
    assessment_stage: str = Field(min_length=1, max_length=32)
    assessment_date: date | None = None
    cohort_year: int = Field(ge=2020, le=2100)
    mock_total_score: float | None = Field(default=None, ge=0, le=1000)
    mock_full_mark: float | None = Field(default=None, gt=0, le=1000)
    grade_rank: int = Field(ge=1)
    grade_size: int = Field(ge=1)
    final_total_score: float | None = Field(default=None, ge=0, le=1000)
    final_city_rank: int = Field(ge=1)
    final_candidate_count: int | None = Field(default=None, ge=1)
    evidence_ids: list[str] = Field(default_factory=list)
    source_note: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def rank_is_within_grade_size(self) -> "PositionCalibrationSampleCreate":
        if self.grade_rank > self.grade_size:
            raise ValueError("年级排名不能大于年级人数")
        return self


class PositionCalibrationSampleReview(BaseModel):
    decision: Literal["approved", "rejected"]
    note: str | None = Field(default=None, max_length=1000)


class PositionCalibrationSampleRead(PositionCalibrationSampleCreate):
    id: str
    status: CalibrationStatus
    review_note: str | None
    created_at: datetime
    reviewed_at: datetime | None

    model_config = {"from_attributes": True}
