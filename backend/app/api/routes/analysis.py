from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import current_data_admin
from app.core.database import get_session
from app.domain.schemas import (
    AnalysisModelRead, AnalysisModelUpdate, AnalysisValidationCreate, AnalysisValidationRead,
    PositionCalibrationSampleCreate, PositionCalibrationSampleRead, PositionCalibrationSampleReview,
)
from app.services.analysis_model_service import AnalysisModelService

router = APIRouter(prefix="/analysis", tags=["analysis models"])


@router.get("/models", response_model=list[AnalysisModelRead])
async def list_models(_: str = Depends(current_data_admin), session: AsyncSession = Depends(get_session)) -> list[AnalysisModelRead]:
    return await AnalysisModelService(session).list_models()


@router.put("/models/{model_id}", response_model=AnalysisModelRead)
async def update_model(
    model_id: str,
    payload: AnalysisModelUpdate,
    _: str = Depends(current_data_admin),
    session: AsyncSession = Depends(get_session),
) -> AnalysisModelRead:
    return await AnalysisModelService(session).update_model(model_id, payload)


@router.get("/models/{model_id}/validations", response_model=list[AnalysisValidationRead])
async def list_validations(
    model_id: str,
    _: str = Depends(current_data_admin),
    session: AsyncSession = Depends(get_session),
) -> list[AnalysisValidationRead]:
    return await AnalysisModelService(session).validations(model_id)


@router.post("/models/{model_id}/validations", response_model=AnalysisValidationRead, status_code=201)
async def add_validation(
    model_id: str,
    payload: AnalysisValidationCreate,
    _: str = Depends(current_data_admin),
    session: AsyncSession = Depends(get_session),
) -> AnalysisValidationRead:
    return await AnalysisModelService(session).add_validation(model_id, payload)


@router.get("/calibration-samples", response_model=list[PositionCalibrationSampleRead])
async def list_calibration_samples(
    region: str | None = None,
    junior_school: str | None = None,
    assessment_stage: str | None = None,
    approved_only: bool = False,
    _: str = Depends(current_data_admin),
    session: AsyncSession = Depends(get_session),
) -> list[PositionCalibrationSampleRead]:
    return await AnalysisModelService(session).calibration_samples(
        region=region,
        junior_school=junior_school,
        assessment_stage=assessment_stage,
        approved_only=approved_only,
    )


@router.post("/calibration-samples", response_model=PositionCalibrationSampleRead, status_code=201)
async def add_calibration_sample(
    payload: PositionCalibrationSampleCreate,
    _: str = Depends(current_data_admin),
    session: AsyncSession = Depends(get_session),
) -> PositionCalibrationSampleRead:
    return await AnalysisModelService(session).add_calibration_sample(payload)


@router.post("/calibration-samples/{sample_id}/review", response_model=PositionCalibrationSampleRead)
async def review_calibration_sample(
    sample_id: str,
    payload: PositionCalibrationSampleReview,
    _: str = Depends(current_data_admin),
    session: AsyncSession = Depends(get_session),
) -> PositionCalibrationSampleRead:
    return await AnalysisModelService(session).review_calibration_sample(sample_id, payload)
