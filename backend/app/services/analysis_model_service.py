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
    "rank_interval_ratio": 0.06,
    "minimum_rank_interval": 400,
    "grade_rank_weight": 0,
    "trend_weight": 0,
    "school_mapping_min_samples": 15,
    "school_mapping_weight": 0.35,
}


class AnalysisModelService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = AnalysisRepository(session)

    async def active_position_model(self, region: str) -> AnalysisModelVersion:
        model = await self.repository.active_position_model(region)
        if model:
            return model
        model = await self.repository.add_model(AnalysisModelVersion(
            name="一分一段位置模型",
            version=f"position-rank-curve-v1-{region}",
            region=region,
            parameters=DEFAULT_POSITION_PARAMETERS,
            quality_metrics={"method": "rank_curve_interpolation", "validation_status": "awaiting_history"},
        ))
        await self.session.commit()
        return model

    async def list_models(self) -> list[AnalysisModelRead]:
        await self.active_position_model("西安")
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
            input_snapshot=input_snapshot,
            result=result,
        ))
        await self.session.commit()
        return run
