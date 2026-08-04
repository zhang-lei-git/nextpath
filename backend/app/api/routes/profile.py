from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import current_owner_id
from app.core.database import get_session
from app.domain.schemas import StudentProfileRead, StudentProfileUpdate
from app.services.student_service import StudentService

router = APIRouter(prefix="/profile", tags=["profile"])


@router.get("", response_model=StudentProfileRead)
async def get_profile(
    owner_id: str = Depends(current_owner_id), session: AsyncSession = Depends(get_session)
) -> StudentProfileRead:
    return await StudentService(session).get_profile(owner_id)


@router.put("", response_model=StudentProfileRead)
async def update_profile(
    payload: StudentProfileUpdate,
    owner_id: str = Depends(current_owner_id),
    session: AsyncSession = Depends(get_session),
) -> StudentProfileRead:
    return await StudentService(session).update_profile(owner_id, payload)
