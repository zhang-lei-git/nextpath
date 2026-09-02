from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import current_owner_id
from app.core.database import get_session
from app.domain.schemas import ExamCreate, ExamRead, ExamUpdate, TrendResponse
from app.services.student_service import StudentService

router = APIRouter(prefix="/exams", tags=["exams"])


@router.get("", response_model=list[ExamRead])
async def list_exams(
    owner_id: str = Depends(current_owner_id),
    session: AsyncSession = Depends(get_session),
) -> list[ExamRead]:
    return await StudentService(session).list_exams(owner_id)


@router.post("", response_model=ExamRead, status_code=201)
async def create_exam(
    payload: ExamCreate,
    owner_id: str = Depends(current_owner_id),
    session: AsyncSession = Depends(get_session),
) -> ExamRead:
    return await StudentService(session).create_exam(owner_id, payload)


@router.get("/trend", response_model=TrendResponse)
async def exam_trend(
    owner_id: str = Depends(current_owner_id),
    session: AsyncSession = Depends(get_session),
) -> TrendResponse:
    return await StudentService(session).trend_data(owner_id)


@router.get("/{exam_id}", response_model=ExamRead)
async def get_exam(
    exam_id: str,
    owner_id: str = Depends(current_owner_id),
    session: AsyncSession = Depends(get_session),
) -> ExamRead:
    return await StudentService(session).get_exam(owner_id, exam_id)


@router.put("/{exam_id}", response_model=ExamRead)
async def update_exam(
    exam_id: str,
    payload: ExamUpdate,
    owner_id: str = Depends(current_owner_id),
    session: AsyncSession = Depends(get_session),
) -> ExamRead:
    return await StudentService(session).update_exam(owner_id, exam_id, payload)
