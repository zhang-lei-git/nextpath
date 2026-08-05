import hashlib
import json

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import AnalysisModelVersion, AnalysisRun, AnalysisValidationRun
from app.domain.schemas import AnalysisModelRead, AnalysisModelUpdate, AnalysisValidationCreate, AnalysisValidationRead
from app.repositories.analysis_repository import AnalysisRepository


DEFAULT_POSITION_PARAMETERS = {
    "rank_interval_ratio": 0.06,
    "minimum_rank_interval": 400,
    "grade_rank_weight": 0,
    "trend_weight": 0,
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
        model.parameters = {**model.parameters, **payload.parameters}
        model.status = payload.status
        await self.session.commit()
        await self.session.refresh(model)
        return AnalysisModelRead.model_validate(model)

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

    async def record_run(
        self,
        *,
        profile_id: str,
        exam_id: str,
        data_release_id: str | None,
        model_id: str,
        input_snapshot: dict,
        result: dict,
    ) -> None:
        fingerprint_source = {"profile": profile_id, "exam": exam_id, "release": data_release_id, "model": model_id, "input": input_snapshot}
        fingerprint = hashlib.sha256(json.dumps(fingerprint_source, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        if await self.repository.run_by_fingerprint(fingerprint):
            return
        await self.repository.add_run(AnalysisRun(
            fingerprint=fingerprint,
            profile_id=profile_id,
            exam_id=exam_id,
            data_release_id=data_release_id,
            model_id=model_id,
            input_snapshot=input_snapshot,
            result=result,
        ))
        await self.session.commit()
