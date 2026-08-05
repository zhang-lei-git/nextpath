from dataclasses import dataclass
from typing import Protocol

from app.domain.schemas import AdmissionReport, Forecast
from app.services.admission_data import (
    POLICY_SUMMARY, RANK_REFERENCE_SOURCE, RANK_REFERENCE_YEAR, estimate_city_rank, find_school_reference,
)
from app.services.published_reference_data import PublishedReferenceData
from app.services.position_engine import CalibrationPoint, PositionEngine


@dataclass(frozen=True)
class PredictionInput:
    total_score: float
    class_rank: int | None
    target_school: str | None
    junior_school: str | None = None
    trend_delta: float | None = None
    grade_rank: int | None = None
    grade_size: int | None = None
    assessment_stage: str | None = None


class PredictionEngine(Protocol):
    """A stable port for rule, statistical, or model-backed prediction engines."""

    def predict(self, input_data: PredictionInput) -> Forecast: ...


class BaselinePredictionEngine:
    """Transparent MVP baseline. Thresholds are configuration, not admission facts."""

    version = "baseline-2026.1"
    reference_year = 2026

    def __init__(
        self,
        reference_data: PublishedReferenceData | None = None,
        position_parameters: dict | None = None,
        model_version: str | None = None,
        calibration_points: tuple[CalibrationPoint, ...] = (),
    ) -> None:
        self.reference_data = reference_data
        self.position_parameters = position_parameters or {}
        self.calibration_points = calibration_points
        if model_version:
            self.version = model_version

    def predict(self, input_data: PredictionInput) -> Forecast:
        score = input_data.total_score
        position = self._position_engine().estimate(score, input_data.grade_rank, input_data.grade_size)
        city_rank = position.rank
        if city_rank is None:
            tier, rank = "当前分数暂无法映射全区位次", (0, 0)
        elif score >= 600:
            tier, rank = "省示范高中层", position.rank_range
        elif score >= 570:
            tier, rank = "省级标准化高中层", position.rank_range
        else:
            tier, rank = "普通高中与综合高中班层", position.rank_range

        target = self._find_school_reference(input_data.target_school)
        target_gap = max(0, target[1] - score) if target else None
        target_position = self._position_engine().estimate(target[1]) if target else None
        target_rank = target_position.rank if target_position else None
        target_rank_gap = max(0, city_rank - target_rank) if city_rank and target_rank else None

        return Forecast(
            tier=tier,
            estimated_rank_range=rank,
            target_gap=target_gap,
            confidence="low",
            basis=[
                f"按 {self._rank_reference_source()} 折算当前总分的全区参考位置。",
                self._position_basis(position.method, position.calibration_sample_count),
            ],
            model_version=self.version,
            reference_year=self._reference_year(),
            current_rank=city_rank,
            target_rank=target_rank,
            target_rank_gap=target_rank_gap,
        )

    def build_report(self, input_data: PredictionInput) -> AdmissionReport:
        forecast = self.predict(input_data)
        rank = forecast.current_rank
        target = self._find_school_reference(input_data.target_school)
        trend = input_data.trend_delta
        trend_summary = "成绩记录不足两次，暂不判断趋势。" if trend is None else (
            f"最近两次总分变化 {trend:+.1f} 分，已计入本次位置判断。"
        )
        target_summary = "尚未设定目标高中，可先看当前层次，再在档案中补充。" if not target else self._target_summary(
            target, forecast.current_rank, forecast.target_rank, forecast.target_rank_gap, input_data.total_score
        )
        return AdmissionReport(
            headline=f"当前更适合关注：{forecast.tier}",
            current_position=(f"按 {self._reference_year()} 年参考表，当前约全区第 {rank:,} 名。" if rank else "本次总分不在当前参考表覆盖范围内，无法可靠折算全区位次。"),
            trend_summary=trend_summary,
            target_summary=target_summary,
            school_context=self._school_context(input_data, forecast),
            policy_summary=self._policy_summary(),
            key_points=[forecast.basis[0], forecast.basis[1], "下次录入时补全年级排名和年级人数，判断会更贴近孩子所在初中的实际位置。"],
            data_sources=[self._rank_reference_source(), target[2] if target else "尚未选择目标学校", self._policy_source()],
        )

    def _estimate_city_rank(self, score: float) -> int | None:
        return self._position_engine().estimate(score).rank

    def _position_engine(self) -> PositionEngine:
        points = self.reference_data.rank_points if self.reference_data and self.reference_data.rank_points else ()
        if not points:
            from app.services.admission_data import RANK_POINTS
            points = RANK_POINTS
        return PositionEngine(points, self.position_parameters, self.calibration_points)

    @staticmethod
    def _position_basis(method: str, sample_count: int) -> str:
        if method == "rank_curve_with_school_mapping":
            return f"已将同校同阶段的 {sample_count} 条审核通过历史样本，与全区参考位置共同校准。"
        return "已参考历次成绩变化；所在初中的可用历史样本不足时，以全区参考位置为主。"

    def _school_context(self, input_data: PredictionInput, forecast: Forecast) -> str:
        if not input_data.junior_school:
            return "补充孩子所在初中后，判断会更贴近实际升学环境。"
        if input_data.grade_rank and input_data.grade_size and forecast.current_rank:
            return f"已记录初中：{input_data.junior_school}。本次年级第 {input_data.grade_rank:,}/{input_data.grade_size:,} 名已纳入孩子的成绩档案。"
        return f"已记录初中：{input_data.junior_school}。补全年级排名和年级人数后，可进一步贴近实际升学环境。"

    @staticmethod
    def _target_summary(
        target: tuple[str, float, str],
        current_rank: int | None,
        target_rank: int | None,
        target_rank_gap: int | None,
        score: float,
    ) -> str:
        if current_rank and target_rank:
            gap = f"需前移约 {target_rank_gap:,} 名" if target_rank_gap else "已处于参考边界内"
            return f"目标 {target[0]} 的参考录取位置约全区第 {target_rank:,} 名；孩子当前约第 {current_rank:,} 名，{gap}。{target[2]}。"
        return f"目标 {target[0]} 的公开参考线约 {target[1]:.0f} 分；当前参考差距 {max(0, target[1] - score):.0f} 分。{target[2]}。"

    def _find_school_reference(self, name: str | None) -> tuple[str, float, str] | None:
        if self.reference_data and self.reference_data.school_references and name:
            normalized = name.replace(" ", "")
            match = next(
                (
                    item for item in self.reference_data.school_references
                    if item.name.replace(" ", "") in normalized or normalized in item.name
                ),
                None,
            )
            if match:
                return match.name, match.score, match.source
        fallback = find_school_reference(name)
        return (fallback.name, fallback.estimated_line, fallback.source) if fallback else None

    def _rank_reference_source(self) -> str:
        return self.reference_data.rank_source if self.reference_data and self.reference_data.rank_source else RANK_REFERENCE_SOURCE

    def _reference_year(self) -> int:
        return self.reference_data.reference_year if self.reference_data else RANK_REFERENCE_YEAR

    def _policy_summary(self) -> str:
        return self.reference_data.policy_summary if self.reference_data and self.reference_data.policy_summary else POLICY_SUMMARY

    def _policy_source(self) -> str:
        return "已发布中招政策数据" if self.reference_data and self.reference_data.policy_summary else "2026 年西安市城六区中招政策摘要"
