import hashlib
from datetime import datetime, time, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.domain.models import Exam, ScoreImport
from app.domain.schemas import (
    ActionItem, DashboardResponse, DataGapCreate, ExamCreate, ExamRead, ImportResponse, StudentProfileRead, StudentProfileUpdate, StudentReportDetail,
)
from app.repositories.exam_repository import ExamRepository
from app.repositories.profile_repository import ProfileRepository
from app.services.prediction import BaselinePredictionEngine, PredictionEngine, PredictionInput
from app.services.published_reference_data import PublishedReferenceDataService
from app.services.analysis_model_service import AnalysisModelService
from app.services.data_service import DataService
from app.services.position_engine import CalibrationPoint
from app.services.report_service import ReportContext, StudentReportService


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
            forecast, report = await self._analyze_exam(profile, latest, exams, publish_report=False)
            if not latest.grade_rank or not latest.grade_size:
                actions.append(ActionItem(
                    title="补齐排名信息",
                    detail="补录年级排名和年级人数后，孩子在全区的大致位置会更清楚。",
                    priority="high",
                ))
            subject_scores = [
                value for key, value in latest.scores.items()
                if key != "pe" and isinstance(value, (int, float))
            ]
            if len(subject_scores) < 3:
                actions.append(ActionItem(
                    title="补充各科成绩",
                    detail="补充各科成绩后，可以看清主要差距来自哪些学科。",
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
            target_school=profile.target_school,
            latest_exam=ExamRead.model_validate(latest) if latest else None,
            forecast=forecast,
            action_items=actions,
            trend=[ExamRead.model_validate(item) for item in reversed(exams[:6])],
            report=report,
        )

    async def _analyze_exam(
        self,
        profile,
        exam: Exam,
        exams: list[Exam],
        *,
        publish_report: bool,
    ):
            run_at = datetime.now(timezone.utc)
            trend_delta = self._trend_delta(exam, exams)
            reference_data = await PublishedReferenceDataService(self.session).load_historical_bundle(
                profile.city, exam.exam_date.year, as_of=run_at
            )
            analysis_models = AnalysisModelService(self.session)
            position_model = await analysis_models.active_position_model(profile.city)
            annual_distribution_model = await analysis_models.active_annual_distribution_model(profile.city)
            school_boundary_model = await analysis_models.active_school_boundary_model(profile.city)
            assessment_stage = analysis_models.assessment_stage(exam.name)
            samples, calibration_level = await analysis_models.calibration_samples_for_prediction(
                region=profile.city,
                junior_school=profile.junior_school,
                class_type_standard=profile.class_type_standard,
                assessment_stage=assessment_stage,
                minimum_samples=int(position_model.parameters.get("rank_channel_min_samples", 15)),
            ) if assessment_stage else ([], "insufficient_prior")
            predictor = self.predictor or BaselinePredictionEngine(
                reference_data,
                position_parameters=position_model.parameters,
                model_version=position_model.version,
                annual_distribution_parameters=annual_distribution_model.parameters,
                annual_distribution_version=annual_distribution_model.version,
                school_boundary_parameters=school_boundary_model.parameters,
                school_boundary_version=school_boundary_model.version,
                calibration_points=tuple(
                    CalibrationPoint(item.grade_rank, item.grade_size, item.final_city_rank, item.final_candidate_count)
                    for item in samples
                ),
            )
            prediction_input = PredictionInput(
                total_score=exam.total_score,
                class_rank=exam.class_rank,
                target_school=profile.target_school,
                junior_school=profile.junior_school,
                trend_delta=trend_delta,
                grade_rank=exam.grade_rank,
                grade_size=exam.grade_size,
                assessment_stage=assessment_stage,
                total_full_mark=exam.total_full_mark,
                physical_score=exam.physical_score if exam.physical_score is not None else exam.scores.get("pe"),
                analysis_year=exam.exam_date.year,
                analysis_date=exam.exam_date,
                subject_scores=exam.scores,
                score_history=tuple(
                    (item.total_score, item.total_full_mark, item.exam_date.year)
                    for item in sorted(exams, key=lambda item: item.exam_date)
                    if item.exam_date <= exam.exam_date
                ),
                rank_history=tuple(
                    (item.grade_rank, item.grade_size)
                    for item in sorted(exams, key=lambda item: item.exam_date)
                    if item.exam_date <= exam.exam_date and item.grade_rank and item.grade_size
                ),
                class_type_standard=profile.class_type_standard,
                calibration_level=calibration_level,
            )
            forecast = predictor.predict(prediction_input)
            report = predictor.build_report(prediction_input)
            await self._record_analysis_gaps(
                profile=profile,
                exam=exam,
                assessment_stage=assessment_stage,
                reference_data=reference_data,
                forecast=forecast,
            )
            analysis_run = await analysis_models.record_run(
                profile_id=profile.id,
                exam_id=exam.id,
                data_release_id=reference_data.release_id if reference_data else None,
                model_id=position_model.id,
                exam_at=datetime.combine(exam.exam_date, time.min, tzinfo=timezone.utc),
                run_at=run_at,
                data_cutoff_at=run_at,
                status="completed",
                model_versions={
                    "student_forecast": position_model.version,
                    "annual_distribution": annual_distribution_model.version,
                    "school_boundary": school_boundary_model.version,
                },
                input_snapshot={
                    "total_score": exam.total_score,
                    "total_full_mark": exam.total_full_mark,
                    "physical_score": exam.physical_score,
                    "grade_rank": exam.grade_rank,
                    "grade_size": exam.grade_size,
                    "assessment_stage": assessment_stage,
                    "exam_scope": exam.exam_scope,
                    "participant_scope": exam.participant_scope,
                    "participant_count": exam.participant_count,
                    "paper_version": exam.paper_version,
                    "junior_school": profile.junior_school,
                    "class_type_raw": profile.class_type_raw,
                    "class_type_standard": profile.class_type_standard,
                    "target_school": profile.target_school,
                    "model_version": position_model.version,
                    "model_parameters": position_model.parameters,
                    "annual_distribution_version": annual_distribution_model.version,
                    "annual_distribution_parameters": annual_distribution_model.parameters,
                    "school_boundary_version": school_boundary_model.version,
                    "school_boundary_parameters": school_boundary_model.parameters,
                    "calibration_sample_ids": [item.id for item in samples],
                    "calibration_level": calibration_level,
                },
                result={
                    "forecast": forecast.model_dump(),
                    "report": report.model_dump(),
                    "internal_diagnostics": {
                        "position_channels": forecast.position_channels,
                        "position_conflict_pp": forecast.position_conflict_pp,
                        "consistency_check": "passed" if all(
                            scenario is None
                            or scenario.estimated_rank_range == (0, 0)
                            or scenario.total_range is not None
                            for scenario in (forecast.current_snapshot, forecast.reasonable_projection)
                        ) else "failed",
                    },
                },
            )
            if publish_report:
                await StudentReportService(self.session).publish(ReportContext(
                    profile=profile,
                    exam=exam,
                    exams=exams,
                    forecast=forecast,
                    admission_report=report,
                    reference_data=reference_data,
                    analysis_run_id=analysis_run.id,
                ))
            return forecast, report

    async def _record_analysis_gaps(
        self,
        *,
        profile,
        exam: Exam,
        assessment_stage: str | None,
        reference_data,
        forecast,
    ) -> None:
        occurrence_key = hashlib.sha256(profile.id.encode()).hexdigest()[:16]
        common = {
            "region": profile.city,
            "junior_school": profile.junior_school,
            "class_type_standard": profile.class_type_standard,
            "assessment_stage": assessment_stage,
            "affected_users": 1,
        }
        gaps: list[tuple[str, dict]] = []
        if not reference_data or not reference_data.rank_points:
            gaps.append(("annual_distribution", {
                "reference_year": exam.exam_date.year,
                "reason": "缺少截止本次分析时可用的历史分数位次曲线",
            }))
        if exam.grade_rank and exam.grade_size and "rank" not in forecast.position_channels:
            gaps.append(("junior_school_mapping", {
                "reference_year": exam.exam_date.year,
                "reason": "已有年级排名，但缺少同校同阶段纵向映射样本",
                "uncertainty_pp": 8,
            }))
        if profile.class_type_standard == "未知":
            gaps.append(("class_type_mapping", {
                "reference_year": exam.exam_date.year,
                "reason": "学生班型尚未标准化",
            }))
        if profile.target_school and forecast.target_percentile is None:
            gaps.append(("school_boundary", {
                "reference_year": exam.exam_date.year,
                "target_school": profile.target_school,
                "reason": "缺少目标高中可用的录取位置边界",
            }))
        service = DataService(self.session)
        for gap_type, details in gaps:
            await service.create_or_increment_gap(DataGapCreate(
                **common,
                gap_type=gap_type,
                details={**details, "occurrence_key": occurrence_key},
            ), commit=False)
        if gaps:
            await self.session.commit()

    @staticmethod
    def _trend_delta(exam: Exam, exams: list[Exam]) -> float | None:
        earlier = [item for item in exams if item.id != exam.id and item.exam_date <= exam.exam_date]
        previous = sorted(earlier, key=lambda item: item.exam_date, reverse=True)
        return exam.total_score - previous[0].total_score if previous else None

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
        if profile.student_name and profile.junior_school and profile.grade:
            exams = await self.exams.list(profile.id)
            await self._analyze_exam(profile, exam, exams, publish_report=True)
        return ExamRead.model_validate(exam)

    async def update_exam(self, owner_id: str, exam_id: str, payload: ExamCreate) -> ExamRead:
        profile = await self.profiles.get_or_create_demo(owner_id)
        exam = await self.exams.get(profile.id, exam_id)
        if not exam:
            raise HTTPException(status_code=404, detail="未找到这次成绩")
        exam = await self.exams.update(exam, payload.model_dump())
        await self.session.commit()
        if profile.student_name and profile.junior_school and profile.grade:
            exams = await self.exams.list(profile.id)
            await self._analyze_exam(profile, exam, exams, publish_report=True)
        return ExamRead.model_validate(exam)

    async def list_exams(self, owner_id: str) -> list[ExamRead]:
        profile = await self.profiles.get_or_create_demo(owner_id)
        return [ExamRead.model_validate(item) for item in await self.exams.list(profile.id)]

    async def get_exam(self, owner_id: str, exam_id: str) -> ExamRead:
        profile = await self.profiles.get_or_create_demo(owner_id)
        exam = await self.exams.get(profile.id, exam_id)
        if not exam:
            raise HTTPException(status_code=404, detail="未找到这次成绩")
        return ExamRead.model_validate(exam)

    async def reports(self, owner_id: str):
        profile = await self.profiles.get_or_create_demo(owner_id)
        return await StudentReportService(self.session).list_for_profile(profile.id)

    async def report_html(self, owner_id: str, report_id: str) -> str:
        profile = await self.profiles.get_or_create_demo(owner_id)
        report = await StudentReportService(self.session).get_for_profile(profile.id, report_id)
        return report.html_content

    async def report_detail(self, owner_id: str, report_id: str) -> StudentReportDetail:
        profile = await self.profiles.get_or_create_demo(owner_id)
        return await StudentReportService(self.session).detail_for_profile(profile.id, report_id)

    async def report_access_url(self, owner_id: str, report_id: str) -> str:
        profile = await self.profiles.get_or_create_demo(owner_id)
        service = StudentReportService(self.session)
        await service.get_for_profile(profile.id, report_id)
        return service.create_access_url(report_id)

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
