from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.domain.models import Exam, ScoreImport
from app.domain.schemas import (
    ActionItem, DashboardResponse, ExamCreate, ExamRead, ImportResponse, StudentProfileRead, StudentProfileUpdate,
)
from app.repositories.exam_repository import ExamRepository
from app.repositories.profile_repository import ProfileRepository
from app.services.prediction import BaselinePredictionEngine, PredictionEngine, PredictionInput
from app.services.published_reference_data import PublishedReferenceDataService
from app.services.analysis_model_service import AnalysisModelService
from app.services.position_engine import CalibrationPoint


class StudentService:
    def __init__(self, session: AsyncSession, predictor: PredictionEngine | None = None) -> None:
        self.session = session
        self.profiles = ProfileRepository(session)
        self.exams = ExamRepository(session)
        self.predictor = predictor

    async def dashboard(self, owner_id: str) -> DashboardResponse:
        profile = await self.profiles.get_or_create_demo(owner_id)
        exams = await self.exams.list(profile.id)
        latest = exams[0] if exams else None
        forecast = None
        actions: list[ActionItem] = []
        profile_complete = bool(profile.student_name and profile.junior_school and profile.grade)
        report = None
        if latest and profile_complete:
            trend_delta = (latest.total_score - exams[1].total_score) if len(exams) > 1 else None
            reference_data = await PublishedReferenceDataService(self.session).load(profile.city, 2026)
            analysis_models = AnalysisModelService(self.session)
            position_model = await analysis_models.active_position_model(profile.city)
            assessment_stage = analysis_models.assessment_stage(latest.name)
            samples = await analysis_models.calibration_samples(
                region=profile.city,
                junior_school=profile.junior_school,
                assessment_stage=assessment_stage,
                approved_only=True,
            ) if assessment_stage else []
            predictor = self.predictor or BaselinePredictionEngine(
                reference_data,
                position_parameters=position_model.parameters,
                model_version=position_model.version,
                calibration_points=tuple(
                    CalibrationPoint(item.grade_rank, item.grade_size, item.final_city_rank)
                    for item in samples
                ),
            )
            prediction_input = PredictionInput(
                latest.total_score,
                latest.class_rank,
                profile.target_school,
                profile.junior_school,
                trend_delta,
                latest.grade_rank,
                latest.grade_size,
                assessment_stage,
            )
            forecast = predictor.predict(prediction_input)
            report = predictor.build_report(prediction_input)
            await analysis_models.record_run(
                profile_id=profile.id,
                exam_id=latest.id,
                data_release_id=reference_data.release_id if reference_data else None,
                model_id=position_model.id,
                input_snapshot={
                    "total_score": latest.total_score,
                    "grade_rank": latest.grade_rank,
                    "grade_size": latest.grade_size,
                    "assessment_stage": assessment_stage,
                    "junior_school": profile.junior_school,
                    "target_school": profile.target_school,
                    "model_version": position_model.version,
                    "model_parameters": position_model.parameters,
                    "calibration_sample_ids": [item.id for item in samples],
                },
                result={"forecast": forecast.model_dump(), "report": report.model_dump()},
            )
            actions.append(ActionItem(
                title="补齐排名信息",
                detail="补录年级排名后，孩子在全区的大致位置会更清楚。",
                priority="high",
            ))
            actions.append(ActionItem(
                title="关注大知识点失分",
                detail="下一次录入可补充科目分数，先看趋势，不进入错题分析。",
                priority="medium",
            ))
        elif not profile_complete:
            actions.append(ActionItem(
                title="先完成孩子档案",
                detail="只需姓名、初中和年级三项，完成后就能看到面向中考的位置判断。",
                priority="high",
            ))
        else:
            actions.append(ActionItem(
                title="录入最近一次考试",
                detail="上传成绩截图或手动录入。先有一条准确成绩，才能看清孩子现在的位置。",
                priority="high",
            ))
        return DashboardResponse(
            student_name=profile.student_name,
            profile_complete=profile_complete,
            junior_school=profile.junior_school,
            grade=profile.grade,
            latest_exam=ExamRead.model_validate(latest) if latest else None,
            forecast=forecast,
            action_items=actions,
            trend=[ExamRead.model_validate(item) for item in reversed(exams[:6])],
            report=report,
        )

    async def get_profile(self, owner_id: str) -> StudentProfileRead:
        profile = await self.profiles.get_or_create_demo(owner_id)
        return StudentProfileRead.model_validate(profile)

    async def update_profile(self, owner_id: str, payload: StudentProfileUpdate) -> StudentProfileRead:
        profile = await self.profiles.get_or_create_demo(owner_id)
        profile = await self.profiles.update(profile, payload)
        await self.session.commit()
        return StudentProfileRead.model_validate(profile)

    async def create_exam(self, owner_id: str, payload: ExamCreate) -> ExamRead:
        profile = await self.profiles.get_or_create_demo(owner_id)
        exam = await self.exams.add(Exam(profile_id=profile.id, **payload.model_dump()))
        await self.session.commit()
        return ExamRead.model_validate(exam)

    async def create_score_import(self, owner_id: str, file: UploadFile) -> ImportResponse:
        if file.content_type not in {"image/jpeg", "image/png", "image/webp"}:
            raise HTTPException(status_code=415, detail="仅支持 JPG、PNG 或 WebP 成绩截图")
        content = await file.read(settings.max_upload_size + 1)
        if len(content) > settings.max_upload_size:
            raise HTTPException(status_code=413, detail="图片不能超过 10MB")
        profile = await self.profiles.get_or_create_demo(owner_id)
        suffix = Path(file.filename or "score.png").suffix.lower() or ".png"
        stored_name = f"{uuid4()}{suffix}"
        settings.upload_dir.mkdir(parents=True, exist_ok=True)
        (settings.upload_dir / stored_name).write_bytes(content)

        # MVP keeps recognition behind a service boundary. Returning a candidate mandates parent confirmation.
        candidate = ExamCreate(name="待确认成绩", exam_date=__import__("datetime").date.today(), total_score=0)
        score_import = ScoreImport(
            profile_id=profile.id,
            file_path=stored_name,
            status="awaiting_confirmation",
            extracted_payload=candidate.model_dump(mode="json"),
        )
        self.session.add(score_import)
        await self.session.commit()
        return ImportResponse(
            import_id=score_import.id,
            status=score_import.status,
            extraction=candidate,
            message="截图已收到。请核对并补全本次成绩，确认后再保存。",
        )
