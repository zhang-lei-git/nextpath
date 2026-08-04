from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import Exam


class ExamRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list(self, profile_id: str) -> list[Exam]:
        result = await self.session.scalars(
            select(Exam)
            .where(Exam.profile_id == profile_id)
            .order_by(desc(Exam.exam_date), desc(Exam.created_at))
        )
        return list(result)

    async def add(self, exam: Exam) -> Exam:
        self.session.add(exam)
        await self.session.flush()
        await self.session.refresh(exam)
        return exam
