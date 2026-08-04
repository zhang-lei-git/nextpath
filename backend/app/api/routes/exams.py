from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import current_owner_id
from app.core.database import get_session
from app.domain.schemas import ExamCreate, ExamRead
from app.services.student_service import StudentService

router = APIRouter(prefix="/exams", tags=["exams"])


@router.post("", response_model=ExamRead, status_code=201)
async def create_exam(
    payload: ExamCreate,
    owner_id: str = Depends(current_owner_id),
    session: AsyncSession = Depends(get_session),
) -> ExamRead:
    return await StudentService(session).create_exam(owner_id, payload)
