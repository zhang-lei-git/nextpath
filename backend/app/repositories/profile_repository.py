from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import StudentProfile
from app.domain.schemas import StudentProfileUpdate


class ProfileRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_or_create_demo(self, owner_id: str) -> StudentProfile:
        profile = await self.session.scalar(
            select(StudentProfile).where(StudentProfile.owner_id == owner_id)
        )
        if profile:
            return profile
        profile = StudentProfile(
            owner_id=owner_id,
            student_name="",
            city="西安",
            junior_school="示例初中",
            target_school="目标高中",
        )
        self.session.add(profile)
        await self.session.flush()
        return profile

    async def update(self, profile: StudentProfile, payload: StudentProfileUpdate) -> StudentProfile:
        profile.student_name = payload.student_name
        profile.junior_school = payload.junior_school
        profile.grade = payload.grade
        profile.target_school = payload.target_school
        await self.session.flush()
        await self.session.refresh(profile)
        return profile
