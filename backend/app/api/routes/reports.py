from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import current_owner_id
from app.core.database import get_session
from app.domain.schemas import StudentReportRead
from app.services.report_service import StudentReportService
from app.services.student_service import StudentService


router = APIRouter(prefix="/reports", tags=["student reports"])


@router.get("", response_model=list[StudentReportRead])
async def list_reports(
    owner_id: str = Depends(current_owner_id),
    session: AsyncSession = Depends(get_session),
) -> list[StudentReportRead]:
    return await StudentService(session).reports(owner_id)


@router.get("/{report_id}/html", response_class=HTMLResponse)
async def report_html(
    report_id: str,
    owner_id: str = Depends(current_owner_id),
    session: AsyncSession = Depends(get_session),
) -> HTMLResponse:
    html_content = await StudentService(session).report_html(owner_id, report_id)
    return HTMLResponse(html_content)


@router.get("/published/{report_id}", response_class=HTMLResponse)
async def published_report_html(
    report_id: str,
    session: AsyncSession = Depends(get_session),
) -> HTMLResponse:
    report = await StudentReportService(session).get_public_html(report_id)
    return HTMLResponse(report.html_content)
