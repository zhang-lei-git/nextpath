from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import current_data_admin
from app.core.database import get_session
from app.domain.schemas import AnalysisModelRead, AnalysisModelUpdate, AnalysisValidationCreate, AnalysisValidationRead
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
