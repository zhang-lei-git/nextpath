from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import current_owner_id
from app.core.database import get_session
from app.domain.schemas import AdmissionScoringSchemeRead, StudentProfileRead, StudentProfileUpdate
from app.services.scoring_scheme import scoring_scheme_for_cohort
from app.services.student_service import StudentService

router = APIRouter(prefix="/profile", tags=["profile"])


@router.get("", response_model=StudentProfileRead)
async def get_profile(
    owner_id: str = Depends(current_owner_id), session: AsyncSession = Depends(get_session)
) -> StudentProfileRead:
    return await StudentService(session).get_profile(owner_id)


@router.get("/scoring-scheme", response_model=AdmissionScoringSchemeRead)
async def get_scoring_scheme(
    owner_id: str = Depends(current_owner_id), session: AsyncSession = Depends(get_session)
) -> AdmissionScoringSchemeRead:
    profile = await StudentService(session).get_profile(owner_id)
    scheme = scoring_scheme_for_cohort("西安", profile.cohort_year)
    if scheme is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="暂未配置该届别的中考计分方案")
    return AdmissionScoringSchemeRead(
        city="西安", cohort_year=profile.cohort_year, total_full_mark=scheme.total_full_mark,
        counted_subjects=scheme.counted_subjects, source_title=scheme.source_title, source_url=scheme.source_url,
    )


@router.put("", response_model=StudentProfileRead)
async def update_profile(
    payload: StudentProfileUpdate,
    owner_id: str = Depends(current_owner_id),
    session: AsyncSession = Depends(get_session),
) -> StudentProfileRead:
    return await StudentService(session).update_profile(owner_id, payload)
