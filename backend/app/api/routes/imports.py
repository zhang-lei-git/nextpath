from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import current_owner_id
from app.core.database import get_session
from app.domain.schemas import ImportResponse
from app.services.student_service import StudentService

router = APIRouter(prefix="/score-imports", tags=["score imports"])


@router.post("", response_model=ImportResponse, status_code=201)
async def create_score_import(
    image: UploadFile = File(...),
    owner_id: str = Depends(current_owner_id),
    session: AsyncSession = Depends(get_session),
) -> ImportResponse:
    return await StudentService(session).create_score_import(owner_id, image)
