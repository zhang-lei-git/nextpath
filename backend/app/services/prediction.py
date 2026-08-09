from dataclasses import dataclass
from datetime import date
from math import sqrt
from typing import Protocol

from app.domain.schemas import AdmissionReport, Forecast, ForecastScenario, TargetComparison
from app.services.annual_distribution import AnnualDistributionModel, AnnualDistributionProjection
from app.services.published_reference_data import PublishedReferenceData
from app.services.position_engine import CalibrationPoint, PositionEngine
from app.services.position_fusion import PositionFusionEngine
from app.services.scoring_scheme import ScoreBridgeModel, ScoreBridgeResult, scoring_scheme
from app.services.school_boundary import SchoolAdmissionObservation, SchoolBoundary, SchoolBoundaryModel


PHYSICAL_EDUCATION_FULL_MARK = 60
DEFAULT_ACADEMIC_FULL_MARK = 580


@dataclass(frozen=True)
class PredictionInput:
    """A snapshot of information available on the day of a mock examination."""

    total_score: float
    class_rank: int | None
    target_school: str | None
    junior_school: str | None = None
    trend_delta: float | None = None
    grade_rank: int | None = None
    grade_size: int | None = None
    assessment_stage: str | None = None
    total_full_mark: float | None = None
    physical_score: float | None = None
    score_includes_pe: bool = False
    analysis_year: int | None = None
    analysis_date: date | None = None
    subject_scores: dict[str, float] | None = None
    score_history: tuple[tuple[float, float | None, int], ...] = ()
    rank_history: tuple[tuple[int, int], ...] = ()
    class_type_standard: str | None = None
    calibration_level: str | None = None


class PredictionEngine(Protocol):
    def predict(self, input_data: PredictionInput) -> Forecast: ...
    def build_report(self, input_data: PredictionInput) -> AdmissionReport: ...


class BaselinePredictionEngine:
    """Pre-exam forecast built only from past, published reference data.

    A mock examination is not an admission result.  The engine therefore starts with
    the student's local percentile when it is available, includes PE as a 60-point
    component unless the actual result has been entered, and maps both sides to historical
    admission percentiles.  It never reads a rank table from the analysis year.
    """

    version = "historical-preexam-2026.5"

    def __init__(
        self,
        reference_data: PublishedReferenceData | None = None,
        position_parameters: dict | None = None,
        model_version: str | None = None,
        annual_distribution_parameters: dict | None = None,
        annual_distribution_version: str | None = None,
        school_boundary_parameters: dict | None = None,
        school_boundary_version: str | None = None,
        calibration_points: tuple[CalibrationPoint, ...] = (),
    ) -> None:
        self.reference_data = reference_data
        self.position_parameters = position_parameters or {}
        self.calibration_points = calibration_points
        self.score_bridge = ScoreBridgeModel()
        self.position_fusion = PositionFusionEngine(self.position_parameters)
        self.annual_distribution = AnnualDistributionModel(
            annual_distribution_parameters, annual_distribution_version
        )
        self.school_boundary = SchoolBoundaryModel(school_boundary_parameters)
        self.school_boundary_version = school_boundary_version or self.school_boundary.version
        if model_version:
            self.version = model_version

    def predict(self, input_data: PredictionInput) -> Forecast:
        annual_curve = self._annual_curve(input_data)
        current_total = self._projected_total_range(input_data)
        current_bridge = self._score_bridge(input_data, current_total)
        current_score_percentile = self._score_percentile(current_bridge, current_total, annual_curve)
        current_score_channel = self.position_fusion.score_channel(
            current_score_percentile,
            junior_school=None,
            assessment_stage=None,
            apply_difficulty=False,
        )
        current_position = self.position_fusion.fuse(current_score_channel, None)

        projected_total = self._reasonable_total_range(input_data, current_total)
        bridge = self._score_bridge(input_data, projected_total)
        raw_score_percentile = self._score_percentile(bridge, projected_total, annual_curve)
        score_channel = self.position_fusion.score_channel(
            raw_score_percentile,
            junior_school=input_data.junior_school,
            assessment_stage=input_data.assessment_stage,
            apply_difficulty=False,
        )
        historical_base = self.reference_data.candidate_count if self.reference_data else None
        target_base = annual_curve.candidate_count if annual_curve else historical_base
        projected_grade_rank, projected_grade_size = self._projected_grade_position(input_data)
        rank_channel = self.position_fusion.rank_channel(
            grade_rank=projected_grade_rank,
            grade_size=projected_grade_size,
            candidate_count=target_base,
            calibration_points=self.calibration_points,
        )
        # Rank evidence may move the reasonable projection only through the
        # target-year curve, so the displayed score and rank always move together.
        fused_position = self.position_fusion.fuse(score_channel, None)
        if rank_channel:
            fused_position = self.position_fusion.fuse(score_channel, rank_channel)
            joint_total = annual_curve.score_range_for_percentiles(fused_position.percentile_range) \
                if annual_curve and fused_position.percentile_range else None
            if joint_total:
                projected_total = joint_total
                bridge = self._score_bridge(input_data, projected_total)
        percentile_range, method = fused_position.percentile_range, fused_position.method
        rank_range = self._project_rank_range(percentile_range, target_base)
        current_rank = round(sum(rank_range) / 2) if rank_range != (0, 0) else None
        current_percentile = fused_position.center
        target = self._find_school_reference(input_data.target_school)
        target_boundary = self._school_boundary(input_data.target_school, target_base)
        historical_target_rank = self._rank_for_score(target[1]) if target else None
        target_percentile = (
            round(sum(target_boundary.percentile_range) / 2, 2)
            if target_boundary
            else self._rank_percentile(historical_target_rank) if historical_target_rank else None
        )
        target_rank = (
            round(sum(target_boundary.rank_range) / 2)
            if target_boundary
            else round(target_percentile / 100 * target_base) if target_percentile is not None and target_base else None
        )
        target_percentile_gap = (
            round(max(0, current_percentile - target_percentile), 2)
            if current_percentile is not None and target_percentile is not None else None
        )
        target_rank_gap = (
            max(0, current_rank - target_rank)
            if current_rank is not None and target_rank is not None else None
        )
        current_snapshot = self._scenario(
            title="当前现状",
            total_range=current_total,
            total_full_mark=self._total_full_mark(input_data),
            position=current_position,
            candidate_count=target_base,
            target_percentile=target_percentile,
            target_rank=target_rank,
            summary="仅按最近一次成绩换算，不使用历史走势或考试难度调整。",
        )
        reasonable_projection = self._scenario(
            title="合理预测",
            total_range=projected_total,
            total_full_mark=self._total_full_mark(input_data),
            position=fused_position,
            candidate_count=target_base,
            target_percentile=target_percentile,
            target_rank=target_rank,
            summary=self._projection_summary(input_data),
        )

        prediction_level = self._prediction_level(input_data, annual_curve)
        current_snapshot.school_scope = self._school_scope(
            current_snapshot.current_percentile, current_snapshot.range_usable
        )
        reasonable_projection.school_scope = self._school_scope(
            reasonable_projection.current_percentile, reasonable_projection.range_usable
        )
        if prediction_level == "complete":
            if current_snapshot.range_usable:
                current_snapshot.school_tiers = self._school_tiers(
                    current_snapshot.estimated_rank_range, target_base
                )
            if reasonable_projection.range_usable:
                reasonable_projection.school_tiers = self._school_tiers(
                    reasonable_projection.estimated_rank_range, target_base
                )

        if current_percentile is None:
            tier = "先补全年级位置，再看升学范围"
            position_note = "本次模考成绩已计入体育分，但缺少可换算的历史数据。补全年级排名和年级人数后，系统会先估算校内位置。"
        else:
            tier = self._tier(current_percentile)
            position_note = self._position_note(percentile_range, method, input_data)

        basis = [
            self._historical_basis(),
            self._physical_basis(input_data, projected_total),
            self._position_basis(method),
        ]
        missing_inputs = self._missing_inputs(input_data, annual_curve)
        comparison_current_range = current_snapshot.estimated_rank_range if current_snapshot.range_usable else (0, 0)
        comparison_projected_range = reasonable_projection.estimated_rank_range if reasonable_projection.range_usable else (0, 0)
        target_comparison = self._target_comparison(
            target[0] if target else None,
            target_boundary.rank_range if target_boundary else (target_rank, target_rank) if target_rank else None,
            comparison_current_range,
            comparison_projected_range,
        )
        school_tiers = reasonable_projection.school_tiers
        return Forecast(
            tier=tier,
            estimated_rank_range=rank_range,
            target_gap=None,
            confidence=fused_position.confidence,
            basis=basis,
            model_version=self.version,
            reference_year=self._reference_year(),
            current_rank=current_rank,
            target_rank=target_rank,
            target_rank_gap=target_rank_gap,
            position_note=position_note,
            estimated_percentile_range=percentile_range,
            current_percentile=current_percentile,
            target_percentile=target_percentile,
            target_percentile_gap=target_percentile_gap,
            projected_total_range=projected_total,
            historical_equivalent_score_range=bridge.target_equivalent_range if bridge else None,
            score_bridge_method=bridge.method if bridge else None,
            score_bridge_source=bridge.source if bridge else None,
            position_method=method,
            position_channels={
                **({"score": score_channel.as_dict()} if score_channel else {}),
                **({"rank": rank_channel.as_dict()} if rank_channel else {}),
            },
            position_conflict_pp=fused_position.conflict_pp,
            current_snapshot=current_snapshot,
            reasonable_projection=reasonable_projection,
            prediction_level=prediction_level,
            target_comparison=target_comparison,
            school_tiers=school_tiers,
            missing_inputs=missing_inputs,
        )

    def build_report(self, input_data: PredictionInput) -> AdmissionReport:
        forecast = self.predict(input_data)
        trend_summary = "成绩记录不足两次，暂不分析趋势。" if input_data.trend_delta is None else (
            f"最近两次学科总分变化 {input_data.trend_delta:+.1f} 分；不同试卷先看年级位置，再看分数变化。"
        )
        target = self._find_school_reference(input_data.target_school)
        if forecast.target_comparison and forecast.target_comparison.school_rank_range:
            boundary = forecast.target_comparison.school_rank_range
            target_summary = (
                f"目标 {forecast.target_comparison.school} 的历史录取位置折算到本届约为第 {boundary[0]}–{boundary[1]} 名；"
                f"孩子的合理预测与目标关系为“{forecast.target_comparison.risk}”。"
            )
        elif target and forecast.current_percentile is not None and forecast.target_percentile is not None:
            gap = forecast.target_percentile_gap or 0
            target_summary = (
                f"目标 {target[0]} 在 {self._reference_year()} 年的历史录取位置约为前 {forecast.target_percentile:.1f}%；"
                f"孩子当前预估在前 {forecast.current_percentile:.1f}%，"
                + (f"还需前移约 {gap:.1f} 个百分点。" if gap else "已进入历史参考边界。")
                + f"{target[2]}。"
            )
        elif target:
            target_summary = f"已记录目标 {target[0]}。待补全年级位置后，才能把孩子的位置与该校历史录取位置进行比较。{target[2]}。"
        else:
            target_summary = "尚未设定目标高中。先持续记录年级位置，后续可直接比较目标学校的历史录取位置。"

        position = (
            f"按 {self._reference_year()} 年历史数据和本次可得信息，预估处于全区考生前 {forecast.current_percentile:.1f}% 左右"
            if forecast.current_percentile is not None else forecast.position_note or "当前数据不足，暂不输出区域位置。"
        )
        return AdmissionReport(
            headline=f"当前更适合关注：{forecast.tier}",
            current_position=position,
            trend_summary=trend_summary,
            target_summary=target_summary,
            school_context=self._school_context(input_data),
            policy_summary="中考前只使用已经发布的往年政策和数据；当年政策、计划和录取结果发布后再分阶段纳入分析。",
            key_points=basis_with_next_step(forecast.basis),
            data_sources=[
                self._rank_reference_source(),
                forecast.score_bridge_source or "年度计分方案待补充",
                target[2] if target else "尚未选择目标学校",
            ],
        )

    def _projected_total_range(self, input_data: PredictionInput) -> tuple[float, float]:
        academic_full_mark = self._academic_full_mark(input_data.total_full_mark, input_data.analysis_year)
        academic_score = min(self._academic_score(input_data), academic_full_mark)
        physical_score = input_data.physical_score if input_data.physical_score is not None else PHYSICAL_EDUCATION_FULL_MARK
        total = round(academic_score + physical_score, 1)
        return (total, total)

    def _reasonable_total_range(
        self, input_data: PredictionInput, current_total: tuple[float, float]
    ) -> tuple[float, float]:
        academic_full_mark = self._academic_full_mark(input_data.total_full_mark, input_data.analysis_year)
        physical_score = input_data.physical_score if input_data.physical_score is not None else PHYSICAL_EDUCATION_FULL_MARK
        rates = []
        for history_item in input_data.score_history:
            score, full_mark, year = history_item[:3]
            physical = history_item[3] if len(history_item) > 3 else None
            includes_pe = bool(history_item[4]) if len(history_item) > 4 else False
            history_academic = score - (physical if includes_pe and physical is not None else 0)
            history_full_mark = self._academic_full_mark(full_mark, year)
            if history_full_mark > 0:
                rates.append(min(1, max(0, history_academic / history_full_mark)))
        current_rate = min(1, max(0, self._academic_score(input_data) / academic_full_mark))
        if not rates or abs(rates[-1] - current_rate) > 0.0001:
            rates.append(current_rate)
        if len(rates) < 2:
            return current_total

        recent_rates = rates[-4:]
        deltas = [right - left for left, right in zip(recent_rates, recent_rates[1:])]
        average_delta = sum(deltas) / len(deltas)
        trend_points = average_delta * academic_full_mark * float(
            self.position_parameters.get("score_projection_trend_weight", 0.6)
        )
        time_factor = self._remaining_time_factor(input_data)
        max_adjustment = float(self.position_parameters.get("score_projection_max_trend_points", 24.0)) * time_factor
        trend_points = max(-max_adjustment, min(max_adjustment, trend_points))
        difficulty_points = self.position_fusion.score_projection_adjustment(
            input_data.junior_school, input_data.assessment_stage
        )
        center = min(academic_full_mark, max(0, self._academic_score(input_data) + trend_points + difficulty_points)) + physical_score
        average_rate = sum(recent_rates) / len(recent_rates)
        volatility = sqrt(sum((value - average_rate) ** 2 for value in recent_rates) / len(recent_rates))
        volatility_points = min(
            float(self.position_parameters.get("score_projection_max_volatility_points", 12.0)),
            volatility * academic_full_mark * float(
                self.position_parameters.get("score_projection_volatility_weight", 0.5)
            ),
        )
        half_width = (
            float(self.position_parameters.get("score_projection_range_points", 10.0)) + volatility_points
        ) * sqrt(time_factor)
        return (
            round(max(physical_score, center - half_width), 1),
            round(min(academic_full_mark + physical_score, center + half_width), 1),
        )

    def _remaining_time_factor(self, input_data: PredictionInput) -> float:
        if not input_data.analysis_date or not input_data.analysis_year:
            return 1.0
        month = int(self.position_parameters.get("target_exam_month", 6))
        day = int(self.position_parameters.get("target_exam_day", 21))
        exam_date = date(input_data.analysis_year, month, day)
        remaining_days = max(0, (exam_date - input_data.analysis_date).days)
        reference_days = max(1, int(self.position_parameters.get("score_projection_reference_days", 90)))
        minimum = min(1.0, max(0.0, float(self.position_parameters.get("score_projection_min_time_factor", 0.15))))
        return round(max(minimum, min(1.0, remaining_days / reference_days)), 4)

    def _projected_grade_position(self, input_data: PredictionInput) -> tuple[int | None, int | None]:
        if not input_data.grade_rank or not input_data.grade_size:
            return input_data.grade_rank, input_data.grade_size
        history = [rank / size * 100 for rank, size in input_data.rank_history if rank > 0 and size >= rank]
        current = input_data.grade_rank / input_data.grade_size * 100
        if not history or abs(history[-1] - current) > 0.0001:
            history.append(current)
        if len(history) < 2:
            return input_data.grade_rank, input_data.grade_size
        recent = history[-4:]
        trend = sum(right - left for left, right in zip(recent, recent[1:])) / (len(recent) - 1)
        shift = trend * float(self.position_parameters.get("rank_projection_trend_weight", 0.5))
        max_shift = float(self.position_parameters.get("rank_projection_max_shift_pp", 5.0)) * self._remaining_time_factor(input_data)
        shift = max(-max_shift, min(max_shift, shift))
        projected_percentile = min(100, max(0.1, current + shift))
        return max(1, round(projected_percentile / 100 * input_data.grade_size)), input_data.grade_size

    @staticmethod
    def _academic_full_mark(total_full_mark: float | None, analysis_year: int | None) -> float:
        scheme = scoring_scheme(analysis_year) if analysis_year else None
        scheme_academic = scheme.total_full_mark - scheme.counted_subjects.get("pe", 0) if scheme else DEFAULT_ACADEMIC_FULL_MARK
        if total_full_mark is None:
            return scheme_academic
        # 580/760 are accepted for old records created before the form switched
        # to the inclusive total-mark convention.
        return total_full_mark if total_full_mark <= scheme_academic else total_full_mark - PHYSICAL_EDUCATION_FULL_MARK

    @staticmethod
    def _academic_score(input_data: PredictionInput) -> float:
        if not input_data.score_includes_pe:
            return input_data.total_score
        physical_score = input_data.physical_score if input_data.physical_score is not None else PHYSICAL_EDUCATION_FULL_MARK
        return max(0, input_data.total_score - physical_score)

    @staticmethod
    def _total_full_mark(input_data: PredictionInput) -> float:
        scheme = scoring_scheme(input_data.analysis_year) if input_data.analysis_year else None
        if scheme:
            return scheme.total_full_mark
        if input_data.total_full_mark:
            return input_data.total_full_mark if input_data.total_full_mark > DEFAULT_ACADEMIC_FULL_MARK else input_data.total_full_mark + PHYSICAL_EDUCATION_FULL_MARK
        return DEFAULT_ACADEMIC_FULL_MARK + PHYSICAL_EDUCATION_FULL_MARK

    def _scenario(
        self,
        *,
        title: str,
        total_range: tuple[float, float],
        total_full_mark: float,
        position,
        candidate_count: int | None,
        target_percentile: float | None,
        target_rank: int | None,
        summary: str,
    ) -> ForecastScenario:
        percentile_range = position.percentile_range
        rank_range = self._project_rank_range(percentile_range, candidate_count)
        rank = round(sum(rank_range) / 2) if rank_range != (0, 0) else None
        target_percentile_gap = (
            round(max(0, position.center - target_percentile), 2)
            if position.center is not None and target_percentile is not None else None
        )
        target_rank_gap = max(0, rank - target_rank) if rank is not None and target_rank is not None else None
        return ForecastScenario(
            title=title,
            total_range=total_range,
            total_full_mark=total_full_mark,
            tier=self._tier(position.center) if position.center is not None else "暂缺位置参考",
            estimated_rank_range=rank_range,
            estimated_percentile_range=percentile_range,
            current_percentile=position.center,
            target_percentile_gap=target_percentile_gap,
            target_rank_gap=target_rank_gap,
            summary=summary,
            confidence=position.confidence,
            range_usable=self._range_usable(percentile_range, rank_range, candidate_count),
            parent_reasons=[summary],
        )

    def _projection_summary(self, input_data: PredictionInput) -> str:
        if len(input_data.score_history) < 2:
            return "成绩记录不足两次，暂以当前成绩作为合理预测。"
        if self.position_fusion.score_projection_adjustment(input_data.junior_school, input_data.assessment_stage):
            return "已结合历次成绩变化和已审核的同校考试难度档案。"
        return "已结合历次成绩变化；学校考试难度档案会在审核样本充足后自动纳入。"

    def _score_percentile(
        self,
        bridge: ScoreBridgeResult | None,
        target_total: tuple[float, float],
        annual_curve: AnnualDistributionProjection | None,
    ) -> tuple[float, float] | None:
        if annual_curve:
            ranks = [annual_curve.estimate(total, self.position_parameters).rank for total in target_total]
            ranks = [rank for rank in ranks if rank is not None]
            if ranks:
                values = [rank / annual_curve.candidate_count * 100 for rank in ranks]
                return (round(max(0.1, min(values)), 2), round(min(99.9, max(values)), 2))
        if not self.reference_data or not self.reference_data.rank_points or not bridge:
            return None
        ranks = [self._rank_for_score(total) for total in bridge.target_equivalent_range]
        ranks = [rank for rank in ranks if rank is not None]
        if not ranks:
            return None
        base = self.reference_data.candidate_count or self.reference_data.rank_points[-1][1]
        values = [rank / base * 100 for rank in ranks]
        lower, upper = min(values), max(values)
        return (round(max(0.1, lower), 2), round(min(99.9, upper), 2))

    def _annual_curve(self, input_data: PredictionInput) -> AnnualDistributionProjection | None:
        if not self.reference_data or not input_data.analysis_year:
            return None
        historical_full_mark = self.reference_data.rank_full_mark
        historical_candidates = self.reference_data.candidate_count
        target_scheme = scoring_scheme(input_data.analysis_year)
        if not historical_full_mark or not historical_candidates or not target_scheme:
            return None
        return self.annual_distribution.project(
            region="西安",
            target_year=input_data.analysis_year,
            reference_year=self.reference_data.reference_year,
            historical_points=self.reference_data.rank_points,
            historical_full_mark=historical_full_mark,
            historical_candidate_count=historical_candidates,
            target_full_mark=target_scheme.total_full_mark,
            source_release_id=self.reference_data.release_id,
        )

    @staticmethod
    def _missing_inputs(
        input_data: PredictionInput, annual_curve: AnnualDistributionProjection | None
    ) -> list[str]:
        missing = []
        if not input_data.junior_school:
            missing.append("所在初中")
        if not input_data.grade_rank or not input_data.grade_size:
            missing.append("年级排名")
        if not input_data.class_type_standard or input_data.class_type_standard == "未知":
            missing.append("班型")
        if not annual_curve:
            missing.append("目标年度位置参考")
        return missing

    @staticmethod
    def _prediction_level(
        input_data: PredictionInput, annual_curve: AnnualDistributionProjection | None
    ) -> str:
        if not input_data.analysis_year or input_data.total_full_mark is None:
            return "unavailable"
        if (
            annual_curve
            and input_data.junior_school
            and input_data.grade_rank
            and input_data.grade_size
            and input_data.class_type_standard
            and input_data.class_type_standard != "未知"
        ):
            return "complete"
        return "basic"

    @staticmethod
    def _target_comparison(
        school: str | None,
        school_rank_range: tuple[int, int] | None,
        current_range: tuple[int, int],
        projected_range: tuple[int, int],
    ) -> TargetComparison | None:
        if not school:
            return None
        if not school_rank_range:
            return TargetComparison(school=school, risk="数据不足")
        school_range = school_rank_range
        current_gap = (
            (current_range[0] - school_range[1], current_range[1] - school_range[0])
            if current_range != (0, 0) else None
        )
        projected_gap = (
            (projected_range[0] - school_range[1], projected_range[1] - school_range[0])
            if projected_range != (0, 0) else None
        )
        decision_gap = projected_gap or current_gap
        if not decision_gap:
            risk = "数据不足"
        elif decision_gap[1] <= 0:
            risk = "已进入"
        elif decision_gap[0] <= 0:
            risk = "边界冲刺"
        elif decision_gap[0] <= max(500, round(sum(school_range) / 2 * 0.08)):
            risk = "匹配"
        else:
            risk = "仍有差距"
        return TargetComparison(
            school=school,
            school_rank_range=school_range,
            current_gap_rank_range=current_gap,
            projected_gap_rank_range=projected_gap,
            risk=risk,
            current_relation=BaselinePredictionEngine._gap_relation(current_gap) if current_gap else None,
            projected_relation=BaselinePredictionEngine._gap_relation(projected_gap) if projected_gap else None,
        )

    @staticmethod
    def _gap_relation(gap: tuple[int, int]) -> str:
        if gap[1] <= 0:
            return "已进入目标边界"
        if gap[0] <= 0:
            return "与目标边界有交集"
        return f"还需前移约 {gap[0]:,}–{gap[1]:,} 名"

    def _score_bridge(
        self, input_data: PredictionInput, projected_total: tuple[float, float]
    ) -> ScoreBridgeResult | None:
        if not self.reference_data or not input_data.analysis_year:
            return None
        return self.score_bridge.bridge(
            projected_total,
            source_year=input_data.analysis_year,
            target_year=self.reference_data.reference_year,
            subject_scores=input_data.subject_scores,
            as_of_date=input_data.analysis_date,
        )

    def _rank_for_score(self, score: float) -> int | None:
        if not self.reference_data or not self.reference_data.rank_points:
            return None
        return PositionEngine(self.reference_data.rank_points, self.position_parameters, self.calibration_points).estimate(score).rank

    def _rank_percentile(self, rank: int | None) -> float | None:
        base = self.reference_data.candidate_count if self.reference_data else None
        return round(rank / base * 100, 2) if rank and base else None

    @staticmethod
    def _project_rank_range(percentile_range: tuple[float, float] | None, base: int | None) -> tuple[int, int]:
        if not percentile_range or not base:
            return (0, 0)
        return tuple(round(value / 100 * base) for value in percentile_range)

    @staticmethod
    def _tier(percentile: float) -> str:
        if percentile <= 5:
            return "优先关注头部高中"
        if percentile <= 15:
            return "优先关注示范高中"
        if percentile <= 35:
            return "优先关注匹配度较高的高中"
        return "先把目标范围稳住"

    @staticmethod
    def _school_scope(percentile: float | None, range_usable: bool) -> str:
        if percentile is None or not range_usable:
            return "学校范围仍需观察"
        if percentile <= 3:
            return "头部高中范围"
        if percentile <= 10:
            return "示范性高中范围"
        if percentile <= 25:
            return "优质高中范围"
        if percentile <= 45:
            return "普通高中范围"
        if percentile <= 65:
            return "以普通高中范围为主"
        return "先稳住普高选择"

    def _find_school_reference(self, name: str | None) -> tuple[str, float, str] | None:
        if not (self.reference_data and name):
            return None
        normalized = name.replace(" ", "")
        match = next((item for item in self.reference_data.school_references if item.name.replace(" ", "") in normalized or normalized in item.name), None)
        return (match.name, match.score, match.source) if match else None

    def _school_boundary(self, name: str | None, target_candidate_count: int | None) -> SchoolBoundary | None:
        if not self.reference_data or not name or not target_candidate_count:
            return None
        normalized = name.replace(" ", "")
        matches = [
            item for item in self.reference_data.school_references
            if item.name.replace(" ", "") in normalized or normalized in item.name.replace(" ", "")
        ]
        observations = tuple(
            SchoolAdmissionObservation(
                school=item.name,
                reference_year=item.reference_year,
                rank=item.rank,
                candidate_count=item.candidate_count,
                plan=item.plan,
                previous_year_plan=item.previous_year_plan,
                batch=item.batch,
                anomaly=item.anomaly,
            )
            for item in matches
            if item.rank and item.candidate_count
        )
        return self.school_boundary.estimate(
            matches[0].name if matches else name, observations, target_candidate_count
        )

    def _school_tiers(
        self, student_rank_range: tuple[int, int], target_candidate_count: int | None
    ) -> dict[str, list[str]]:
        candidates: dict[str, list[tuple[float, str]]] = {"reach": [], "match": [], "safe": []}
        if not self.reference_data or not target_candidate_count or student_rank_range == (0, 0):
            return {"reach": [], "match": [], "safe": []}
        student_center = sum(student_rank_range) / 2
        for name in sorted({item.name for item in self.reference_data.school_references}):
            boundary = self._school_boundary(name, target_candidate_count)
            if not boundary:
                continue
            if student_rank_range[0] > boundary.rank_range[1]:
                bucket = "reach"
                distance = student_rank_range[0] - boundary.rank_range[1]
            elif student_rank_range[1] < boundary.rank_range[0]:
                bucket = "safe"
                distance = boundary.rank_range[0] - student_rank_range[1]
            else:
                bucket = "match"
                distance = abs(student_center - sum(boundary.rank_range) / 2)
            candidates[bucket].append((distance, name))
        limit = max(1, int(self.position_parameters.get("school_tier_display_limit", 5)))
        return {
            bucket: [name for _, name in sorted(items, key=lambda item: (item[0], item[1]))[:limit]]
            for bucket, items in candidates.items()
        }

    def _range_usable(
        self,
        percentile_range: tuple[float, float] | None,
        rank_range: tuple[int, int],
        candidate_count: int | None,
    ) -> bool:
        if percentile_range is None or rank_range == (0, 0) or not candidate_count:
            return False
        percentile_width = max(0.0, percentile_range[1] - percentile_range[0])
        rank_width = max(0, rank_range[1] - rank_range[0])
        max_percentile_width = float(self.position_parameters.get("max_parent_rank_interval_pp", 18.0))
        max_rank_width = max(500, int(self.position_parameters.get("max_parent_rank_interval", 9000)))
        return percentile_width <= max_percentile_width and rank_width <= max_rank_width

    def _historical_basis(self) -> str:
        return f"只使用 {self._reference_year()} 年及更早的已发布参考数据（{self._rank_reference_source()}），不使用本年度一分一段表或录取结果。"

    @staticmethod
    def _physical_basis(input_data: PredictionInput, projected_total: tuple[float, float]) -> str:
        if input_data.physical_score is not None:
            return f"体育成绩已录入 {input_data.physical_score:g}/60，本次中考计分总分按 {projected_total[0]:g} 分计算。"
        return f"体育成绩尚未录入，本次中考计分总分暂按体育满分 60 分，按 {projected_total[0]:g} 分计算。"

    @staticmethod
    def _position_basis(method: str) -> str:
        if method == "dual_channel_fusion":
            return "本次同时参考了计分方案换算后的成绩位置和所在初中年级位置；两条信息相互校验后再给出范围。"
        if method == "dual_channel_conflict_review":
            return "成绩换算与年级位置给出的范围暂不一致，系统已保留更宽的分析范围；后续同类考试会持续校准。"
        if method == "rank_only":
            return "当前以所在初中的年级位置为主，并保留学校层次差异带来的不确定性。"
        if method == "score_only":
            return "年级排名暂缺，已按两年教育局公布的计分科目进行科目桥接，并保留试卷难度带来的不确定性。"
        return "缺少年级位置或可用历史曲线，暂不输出区域位次。"

    def _position_note(self, percentile_range: tuple[float, float] | None, method: str, input_data: PredictionInput) -> str:
        if not percentile_range:
            return "当前缺少年级位置和可用历史参考曲线，暂不换算全区位置。"
        if method in {"dual_channel_fusion", "dual_channel_conflict_review"}:
            return f"综合本次成绩和年级第 {input_data.grade_rank}/{input_data.grade_size} 名，预估全区前 {percentile_range[0]:.1f}%–{percentile_range[1]:.1f}%。"
        if method == "rank_only":
            return f"根据年级第 {input_data.grade_rank}/{input_data.grade_size} 名，预估全区前 {percentile_range[0]:.1f}%–{percentile_range[1]:.1f}%。"
        return f"按年度计分科目桥接后的往年曲线，预估全区前 {percentile_range[0]:.1f}%–{percentile_range[1]:.1f}%；补全年级位置后可相互校验。"

    def _school_context(self, input_data: PredictionInput) -> str:
        if not input_data.junior_school:
            return "补充所在初中后，可持续积累该校与全区位置的校准样本。"
        if input_data.grade_rank and input_data.grade_size:
            return f"已使用 {input_data.junior_school} 的年级第 {input_data.grade_rank}/{input_data.grade_size} 名作为本次分析的主要输入。"
        return f"已记录初中：{input_data.junior_school}。下次补全年级排名和年级人数，分析会更贴近孩子所在初中的实际位置。"

    def _reference_year(self) -> int:
        return self.reference_data.reference_year if self.reference_data else 0

    def _rank_reference_source(self) -> str:
        return self.reference_data.rank_source if self.reference_data and self.reference_data.rank_source else "尚未发布可用的历史一分一段参考数据"


def basis_with_next_step(basis: list[str]) -> list[str]:
    return basis + ["下次录入优先补全年级排名和年级人数；体育成绩公布后可直接补录，系统会保留本次分析，不会覆盖历史报告。"]
