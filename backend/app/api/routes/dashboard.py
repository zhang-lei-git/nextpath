from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import current_owner_id
from app.core.database import get_session
from app.domain.schemas import DashboardResponse
from app.services.student_service import StudentService

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("", response_model=DashboardResponse)
async def get_dashboard(
    owner_id: str = Depends(current_owner_id), session: AsyncSession = Depends(get_session)
) -> DashboardResponse:
    return await StudentService(session).dashboard(owner_id)
