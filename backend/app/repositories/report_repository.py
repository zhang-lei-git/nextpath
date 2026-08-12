from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import StudentReport


class ReportRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, report: StudentReport) -> StudentReport:
        self.session.add(report)
        await self.session.flush()
        await self.session.refresh(report)
        return report

    async def monthly_for_period(self, profile_id: str, period_key: str) -> StudentReport | None:
        return await self.session.scalar(
            select(StudentReport).where(
                StudentReport.profile_id == profile_id,
                StudentReport.report_type == "monthly",
                StudentReport.period_key == period_key,
            ).limit(1)
        )

    async def latest_exam_report(self, profile_id: str, exam_id: str) -> StudentReport | None:
        return await self.session.scalar(
            select(StudentReport).where(
                StudentReport.profile_id == profile_id,
                StudentReport.exam_id == exam_id,
                StudentReport.report_type == "exam",
            ).order_by(desc(StudentReport.created_at)).limit(1)
        )

    async def list_for_profile(self, profile_id: str) -> list[StudentReport]:
        return list(await self.session.scalars(
            select(StudentReport)
            .where(StudentReport.profile_id == profile_id)
            .order_by(desc(StudentReport.created_at))
        ))

    async def get_for_profile(self, profile_id: str, report_id: str) -> StudentReport | None:
        return await self.session.scalar(
            select(StudentReport)
            .where(StudentReport.profile_id == profile_id, StudentReport.id == report_id)
            .limit(1)
        )

    async def get(self, report_id: str) -> StudentReport | None:
        return await self.session.get(StudentReport, report_id)
