import hashlib
import json
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import AnalysisModelVersion, AnalysisRun, AnalysisValidationRun, PositionCalibrationSample
from app.domain.schemas import (
    AnalysisModelRead, AnalysisModelUpdate, AnalysisValidationCreate, AnalysisValidationRead,
    PositionCalibrationSampleCreate, PositionCalibrationSampleRead, PositionCalibrationSampleReview,
)
from app.repositories.analysis_repository import AnalysisRepository


DEFAULT_POSITION_PARAMETERS = {
    "engine_contract": "position-fusion-pe-default-60-score-linked-projection-v1",
    "rank_interval_ratio": 0.06,
    "minimum_rank_interval": 400,
    "grade_rank_weight": 0,
    "trend_weight": 0,
    "school_mapping_min_samples": 15,
    "school_mapping_weight": 0.35,
    "score_channel_base_uncertainty_pp": 8.0,
    "rank_channel_prior_uncertainty_pp": 12.0,
    "rank_channel_calibrated_uncertainty_pp": 5.0,
    "rank_channel_min_samples": 15,
    "fusion_conflict_threshold_pp": 8.0,
    "fusion_conflict_uncertainty_multiplier": 1.35,
    "fusion_correlation_inflation": 1.25,
    "difficulty_stage_uncertainty_pp": {"一模": 6.0, "二模": 5.0, "三模": 4.0, "月考": 8.0, "期中": 8.0, "期末": 7.0, "周测": 10.0},
    "school_difficulty_profiles": {},
    "difficulty_profile_min_samples": 20,
    "score_projection_trend_weight": 0.6,
    "score_projection_max_trend_points": 24.0,
    "score_projection_range_points": 10.0,
    "score_projection_volatility_weight": 0.5,
    "score_projection_max_volatility_points": 12.0,
    "rank_projection_trend_weight": 0.5,
    "rank_projection_max_shift_pp": 5.0,
    "score_projection_reference_days": 90,
    "score_projection_min_time_factor": 0.15,
    "target_exam_month": 6,
    "target_exam_day": 21,
}

DEFAULT_ANNUAL_DISTRIBUTION_PARAMETERS = {
    "engine_contract": "annual-distribution-target-curve-v1",
    "candidate_count_multiplier": 1.0,
    "target_score_shift": 0.0,
    "rank_interval_ratio": 0.08,
    "minimum_rank_interval": 600,
}


class AnalysisModelService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = AnalysisRepository(session)

    async def active_position_model(self, region: str) -> AnalysisModelVersion:
        model = await self.repository.active_position_model(region)
        if model:
            merged_parameters = {**DEFAULT_POSITION_PARAMETERS, **model.parameters}
            if merged_parameters == model.parameters:
                return model
            # An algorithm default is part of the model contract.  Migrate legacy
            # active configurations by creating a successor instead of silently
            # changing the meaning of old analysis runs.
            model.status = "inactive"
            successor = await self.repository.add_model(AnalysisModelVersion(
                name=model.name,
                version=await self._next_revision(model.version),
                analysis_type=model.analysis_type,
                region=model.region,
                status="active",
                parameters=merged_parameters,
                quality_metrics={**model.quality_metrics, "parent_version": model.version},
            ))
            await self.session.commit()
            return successor
        model = await self.repository.add_model(AnalysisModelVersion(
            name="一分一段位置模型",
            version=f"position-rank-curve-v1-{region}",
            region=region,
            parameters=DEFAULT_POSITION_PARAMETERS,
            quality_metrics={"method": "rank_curve_interpolation", "validation_status": "awaiting_history"},
        ))
        await self.session.commit()
        return model

    async def active_annual_distribution_model(self, region: str) -> AnalysisModelVersion:
        model = await self.repository.active_model(region, "annual_distribution")
        if model:
            merged = {**DEFAULT_ANNUAL_DISTRIBUTION_PARAMETERS, **model.parameters}
            if merged == model.parameters:
                return model
            model.status = "inactive"
            successor = await self.repository.add_model(AnalysisModelVersion(
                name=model.name,
                version=await self._next_revision(model.version),
                analysis_type="annual_distribution",
                region=region,
                status="active",
                parameters=merged,
                quality_metrics={**model.quality_metrics, "parent_version": model.version},
            ))
            await self.session.commit()
            return successor
        model = await self.repository.add_model(AnalysisModelVersion(
            name="目标年度分数位次曲线",
            version=f"annual-curve-v1-{region}",
            analysis_type="annual_distribution",
            region=region,
            parameters=DEFAULT_ANNUAL_DISTRIBUTION_PARAMETERS,
            quality_metrics={"method": "historical_percentile_scale", "validation_status": "awaiting_backtest"},
        ))
        await self.session.commit()
        return model

    async def list_models(self) -> list[AnalysisModelRead]:
        await self.active_position_model("西安")
        await self.active_annual_distribution_model("西安")
        return [AnalysisModelRead.model_validate(model) for model in await self.repository.list_models()]

    async def update_model(self, model_id: str, payload: AnalysisModelUpdate) -> AnalysisModelRead:
        model = await self.repository.model_by_id(model_id)
        if not model:
            raise HTTPException(status_code=404, detail="未找到分析模型")
        merged_parameters = {**model.parameters, **payload.parameters}
        if merged_parameters == model.parameters and payload.status == model.status:
            return AnalysisModelRead.model_validate(model)
        version = await self._next_revision(model.version)
        if model.status == "active":
            model.status = "inactive"
        successor = await self.repository.add_model(AnalysisModelVersion(
            name=model.name,
            version=version,
            analysis_type=model.analysis_type,
            region=model.region,
            status=payload.status,
            parameters=merged_parameters,
            quality_metrics={**model.quality_metrics, "parent_version": model.version},
        ))
        await self.session.commit()
        return AnalysisModelRead.model_validate(successor)

    async def _next_revision(self, version: str) -> str:
        base_version = version.rsplit(".r", 1)[0]
        existing_versions = {item.version for item in await self.repository.list_models()}
        revision = 2
        candidate = f"{base_version}.r{revision}"
        while candidate in existing_versions:
            revision += 1
            candidate = f"{base_version}.r{revision}"
        return candidate

    async def validations(self, model_id: str) -> list[AnalysisValidationRead]:
        if not await self.repository.model_by_id(model_id):
            raise HTTPException(status_code=404, detail="未找到分析模型")
        return [AnalysisValidationRead.model_validate(item) for item in await self.repository.list_validations(model_id)]

    async def add_validation(self, model_id: str, payload: AnalysisValidationCreate) -> AnalysisValidationRead:
        if not await self.repository.model_by_id(model_id):
            raise HTTPException(status_code=404, detail="未找到分析模型")
        record = await self.repository.add_validation(AnalysisValidationRun(model_id=model_id, **payload.model_dump()))
        await self.session.commit()
        return AnalysisValidationRead.model_validate(record)

    async def calibration_samples(
        self,
        *,
        region: str | None = None,
        junior_school: str | None = None,
        assessment_stage: str | None = None,
        approved_only: bool = False,
    ) -> list[PositionCalibrationSampleRead]:
        items = await self.repository.list_calibration_samples(
            region=region,
            junior_school=junior_school,
            assessment_stage=assessment_stage,
            approved_only=approved_only,
        )
        return [PositionCalibrationSampleRead.model_validate(item) for item in items]

    async def calibration_samples_for_prediction(
        self,
        *,
        region: str,
        junior_school: str | None,
        class_type_standard: str | None,
        assessment_stage: str | None,
        minimum_samples: int,
    ) -> tuple[list[PositionCalibrationSampleRead], str]:
        items = await self.calibration_samples(
            region=region, assessment_stage=assessment_stage, approved_only=True
        )
        levels = (
            ("same_school_class_stage", [item for item in items if item.junior_school == junior_school and item.class_type_standard == class_type_standard]),
            ("same_school_stage", [item for item in items if item.junior_school == junior_school]),
            ("region_stage", items),
        )
        for level, matches in levels:
            if len(matches) >= minimum_samples:
                return matches, level
        return (levels[0][1] or levels[1][1] or items), "insufficient_prior"

    async def add_calibration_sample(
        self, payload: PositionCalibrationSampleCreate
    ) -> PositionCalibrationSampleRead:
        record = await self.repository.add_calibration_sample(PositionCalibrationSample(**payload.model_dump()))
        await self.session.commit()
        return PositionCalibrationSampleRead.model_validate(record)

    async def review_calibration_sample(
        self, sample_id: str, payload: PositionCalibrationSampleReview
    ) -> PositionCalibrationSampleRead:
        sample = await self.repository.calibration_sample_by_id(sample_id)
        if not sample:
            raise HTTPException(status_code=404, detail="未找到校准样本")
        sample.status = payload.decision
        sample.review_note = payload.note
        sample.reviewed_at = datetime.now(timezone.utc)
        await self.session.commit()
        await self.session.refresh(sample)
        return PositionCalibrationSampleRead.model_validate(sample)

    @staticmethod
    def assessment_stage(exam_name: str) -> str | None:
        normalized = exam_name.replace(" ", "")
        for stage in ("一模", "二模", "三模", "期中", "期末", "月考", "周测"):
            if stage in normalized:
                return stage
        return None

    async def record_run(
        self,
        *,
        profile_id: str,
        exam_id: str,
        data_release_id: str | None,
        model_id: str,
        input_snapshot: dict,
        result: dict,
        exam_at: datetime | None = None,
        run_at: datetime | None = None,
        data_cutoff_at: datetime | None = None,
        status: str = "completed",
        model_versions: dict | None = None,
    ) -> AnalysisRun:
        fingerprint_source = {"profile": profile_id, "exam": exam_id, "release": data_release_id, "model": model_id, "input": input_snapshot}
        fingerprint = hashlib.sha256(json.dumps(fingerprint_source, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        existing = await self.repository.run_by_fingerprint(fingerprint)
        if existing:
            return existing
        run = await self.repository.add_run(AnalysisRun(
            fingerprint=fingerprint,
            profile_id=profile_id,
            exam_id=exam_id,
            data_release_id=data_release_id,
            model_id=model_id,
            exam_at=exam_at,
            run_at=run_at or datetime.now(timezone.utc),
            data_cutoff_at=data_cutoff_at,
            status=status,
            model_versions=model_versions or {},
            input_snapshot=input_snapshot,
            result=result,
        ))
        await self.session.commit()
        return run
