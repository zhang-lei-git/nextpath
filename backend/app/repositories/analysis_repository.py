from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import AnalysisModelVersion, AnalysisRun, AnalysisValidationRun, PositionCalibrationSample


class AnalysisRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def active_position_model(self, region: str) -> AnalysisModelVersion | None:
        return await self.session.scalar(
            select(AnalysisModelVersion)
            .where(
                AnalysisModelVersion.analysis_type == "position",
                AnalysisModelVersion.region == region,
                AnalysisModelVersion.status == "active",
            )
            .order_by(desc(AnalysisModelVersion.created_at))
            .limit(1)
        )

    async def model_by_id(self, model_id: str) -> AnalysisModelVersion | None:
        return await self.session.get(AnalysisModelVersion, model_id)

    async def list_models(self) -> list[AnalysisModelVersion]:
        return list(await self.session.scalars(select(AnalysisModelVersion).order_by(desc(AnalysisModelVersion.created_at))))

    async def add_model(self, model: AnalysisModelVersion) -> AnalysisModelVersion:
        self.session.add(model)
        await self.session.flush()
        await self.session.refresh(model)
        return model

    async def add_validation(self, validation: AnalysisValidationRun) -> AnalysisValidationRun:
        self.session.add(validation)
        await self.session.flush()
        await self.session.refresh(validation)
        return validation

    async def list_validations(self, model_id: str) -> list[AnalysisValidationRun]:
        return list(await self.session.scalars(
            select(AnalysisValidationRun)
            .where(AnalysisValidationRun.model_id == model_id)
            .order_by(desc(AnalysisValidationRun.created_at))
        ))

    async def run_by_fingerprint(self, fingerprint: str) -> AnalysisRun | None:
        return await self.session.scalar(select(AnalysisRun).where(AnalysisRun.fingerprint == fingerprint).limit(1))

    async def add_run(self, run: AnalysisRun) -> AnalysisRun:
        self.session.add(run)
        await self.session.flush()
        await self.session.refresh(run)
        return run

    async def add_calibration_sample(self, sample: PositionCalibrationSample) -> PositionCalibrationSample:
        self.session.add(sample)
        await self.session.flush()
        await self.session.refresh(sample)
        return sample

    async def calibration_sample_by_id(self, sample_id: str) -> PositionCalibrationSample | None:
        return await self.session.get(PositionCalibrationSample, sample_id)

    async def list_calibration_samples(
        self,
        *,
        region: str | None = None,
        junior_school: str | None = None,
        assessment_stage: str | None = None,
        approved_only: bool = False,
    ) -> list[PositionCalibrationSample]:
        query = select(PositionCalibrationSample)
        if region:
            query = query.where(PositionCalibrationSample.region == region)
        if junior_school:
            query = query.where(PositionCalibrationSample.junior_school == junior_school)
        if assessment_stage:
            query = query.where(PositionCalibrationSample.assessment_stage == assessment_stage)
        if approved_only:
            query = query.where(PositionCalibrationSample.status == "approved")
        query = query.order_by(desc(PositionCalibrationSample.cohort_year), desc(PositionCalibrationSample.created_at))
        return list(await self.session.scalars(query))
