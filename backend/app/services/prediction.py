from dataclasses import dataclass
from datetime import date
from typing import Protocol

from app.domain.schemas import AdmissionReport, Forecast
from app.services.published_reference_data import PublishedReferenceData
from app.services.position_engine import CalibrationPoint, PositionEngine
from app.services.scoring_scheme import ScoreBridgeModel, ScoreBridgeResult, scoring_scheme


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
    physical_estimate: float | None = None
    analysis_year: int | None = None
    analysis_date: date | None = None
    subject_scores: dict[str, float] | None = None


class PredictionEngine(Protocol):
    def predict(self, input_data: PredictionInput) -> Forecast: ...
    def build_report(self, input_data: PredictionInput) -> AdmissionReport: ...


class BaselinePredictionEngine:
    """Pre-exam forecast built only from past, published reference data.

    A mock examination is not an admission result.  The engine therefore starts with
    the student's local percentile when it is available, treats PE as an uncertain
    60-point component before its result is known, and maps both sides to historical
    admission percentiles.  It never reads a rank table from the analysis year.
    """

    version = "historical-preexam-2026.2"

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
        self.score_bridge = ScoreBridgeModel()
        if model_version:
            self.version = model_version

    def predict(self, input_data: PredictionInput) -> Forecast:
        projected_total = self._projected_total_range(input_data)
        bridge = self._score_bridge(input_data, projected_total)
        percentile_range, method = self._estimate_percentile(input_data, bridge)
        historical_base = self.reference_data.candidate_count if self.reference_data else None
        rank_range = self._project_rank_range(percentile_range, historical_base)
        current_rank = round(sum(rank_range) / 2) if rank_range != (0, 0) else None
        current_percentile = round(sum(percentile_range) / 2, 2) if percentile_range else None
        target = self._find_school_reference(input_data.target_school)
        target_rank = self._rank_for_score(target[1]) if target else None
        target_percentile = self._rank_percentile(target_rank) if target_rank else None
        target_percentile_gap = (
            round(max(0, current_percentile - target_percentile), 2)
            if current_percentile is not None and target_percentile is not None else None
        )
        target_rank_gap = (
            max(0, current_rank - target_rank)
            if current_rank is not None and target_rank is not None else None
        )

        if current_percentile is None:
            tier = "先补全年级位置，再看升学范围"
            position_note = "本次是未含体育的模考成绩，且缺少可换算的历史数据。补全年级排名和年级人数后，系统会先按校内位置估算。"
        else:
            tier = self._tier(current_percentile)
            position_note = self._position_note(percentile_range, method, input_data)

        basis = [
            self._historical_basis(),
            self._physical_basis(input_data, projected_total),
            self._position_basis(method),
        ]
        return Forecast(
            tier=tier,
            estimated_rank_range=rank_range,
            target_gap=None,
            confidence="medium" if method == "school_percentile" and target_percentile is not None else "low",
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
        )

    def build_report(self, input_data: PredictionInput) -> AdmissionReport:
        forecast = self.predict(input_data)
        trend_summary = "成绩记录不足两次，暂不判断趋势。" if input_data.trend_delta is None else (
            f"最近两次学科总分变化 {input_data.trend_delta:+.1f} 分；不同试卷先看年级位置，再看分数变化。"
        )
        target = self._find_school_reference(input_data.target_school)
        if target and forecast.current_percentile is not None and forecast.target_percentile is not None:
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
            policy_summary="中考前只使用已经发布的往年政策和数据；当年政策、计划和录取结果发布后再分阶段纳入判断。",
            key_points=basis_with_next_step(forecast.basis),
            data_sources=[
                self._rank_reference_source(),
                forecast.score_bridge_source or "年度计分方案待补充",
                target[2] if target else "尚未选择目标学校",
            ],
        )

    def _projected_total_range(self, input_data: PredictionInput) -> tuple[float, float]:
        scheme = scoring_scheme(input_data.analysis_year) if input_data.analysis_year else None
        scheme_academic_full_mark = scheme.total_full_mark - scheme.counted_subjects.get("pe", 0) if scheme else None
        academic_full_mark = input_data.total_full_mark or scheme_academic_full_mark or DEFAULT_ACADEMIC_FULL_MARK
        academic_score = min(input_data.total_score, academic_full_mark)
        if input_data.physical_score is not None:
            low = high = input_data.physical_score
        elif input_data.physical_estimate is not None:
            low, high = max(0, input_data.physical_estimate - 3), min(60, input_data.physical_estimate + 3)
        else:
            low, high = 0, PHYSICAL_EDUCATION_FULL_MARK
        return (round(academic_score + low, 1), round(academic_score + high, 1))

    def _estimate_percentile(
        self, input_data: PredictionInput, bridge: ScoreBridgeResult | None
    ) -> tuple[tuple[float, float] | None, str]:
        if input_data.grade_rank and input_data.grade_size:
            center = input_data.grade_rank / input_data.grade_size * 100
            spread = max(0.6, min(4.0, center * 0.16))
            return (round(max(0.1, center - spread), 2), round(min(99.9, center + spread), 2)), "school_percentile"
        if not self.reference_data or not self.reference_data.rank_points or not bridge:
            return None, "insufficient_data"
        ranks = [self._rank_for_score(total) for total in bridge.target_equivalent_range]
        ranks = [rank for rank in ranks if rank is not None]
        if not ranks:
            return None, "insufficient_data"
        base = self.reference_data.candidate_count or self.reference_data.rank_points[-1][1]
        values = [rank / base * 100 for rank in ranks]
        lower, upper = min(values), max(values)
        uncertainty = float(self.position_parameters.get("score_bridge_uncertainty_pp", 8.0))
        return (round(max(0.1, lower - uncertainty), 2), round(min(99.9, upper + uncertainty), 2)), "score_scheme_bridge"

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

    def _find_school_reference(self, name: str | None) -> tuple[str, float, str] | None:
        if not (self.reference_data and name):
            return None
        normalized = name.replace(" ", "")
        match = next((item for item in self.reference_data.school_references if item.name.replace(" ", "") in normalized or normalized in item.name), None)
        return (match.name, match.score, match.source) if match else None

    def _historical_basis(self) -> str:
        return f"只使用 {self._reference_year()} 年及更早的已发布参考数据（{self._rank_reference_source()}），不使用本年度一分一段表或录取结果。"

    @staticmethod
    def _physical_basis(input_data: PredictionInput, projected_total: tuple[float, float]) -> str:
        if input_data.physical_score is not None:
            return f"体育成绩已确认为 {input_data.physical_score:g}/60，合计预测口径为 {projected_total[0]:g} 分。"
        if input_data.physical_estimate is not None:
            return f"体育暂按 {input_data.physical_estimate:g}/60 的家长预估，并保留上下 3 分区间。"
        return "体育尚未考试或未录入，预估位置保留体育 0–60 分的不确定性，不把模考学科分当作中考总分。"

    @staticmethod
    def _position_basis(method: str) -> str:
        if method == "school_percentile":
            return "以孩子在所在初中的年级位置为主，再映射到往年全区位置；这比直接比较不同年份总分更可靠。"
        if method == "score_scheme_bridge":
            return "年级排名暂缺，已按两年教育局公布的计分科目进行科目桥接，并扩大误差区间；补全年级排名后会自动替换。"
        return "缺少年级位置或可用历史曲线，暂不输出区域位次。"

    def _position_note(self, percentile_range: tuple[float, float] | None, method: str, input_data: PredictionInput) -> str:
        if not percentile_range:
            return "当前缺少年级位置和可用历史参考曲线，暂不换算全区位置。"
        if method == "school_percentile":
            return f"根据年级第 {input_data.grade_rank}/{input_data.grade_size} 名，预估全区前 {percentile_range[0]:.1f}%–{percentile_range[1]:.1f}%。"
        return f"按年度计分科目桥接后的往年曲线，预估全区前 {percentile_range[0]:.1f}%–{percentile_range[1]:.1f}%；请补全年级位置。"

    def _school_context(self, input_data: PredictionInput) -> str:
        if not input_data.junior_school:
            return "补充所在初中后，可持续积累该校与全区位置的校准样本。"
        if input_data.grade_rank and input_data.grade_size:
            return f"已使用 {input_data.junior_school} 的年级第 {input_data.grade_rank}/{input_data.grade_size} 名作为本次判断的主要输入。"
        return f"已记录初中：{input_data.junior_school}。下次补全年级排名和年级人数，判断会更贴近孩子所在初中的实际位置。"

    def _reference_year(self) -> int:
        return self.reference_data.reference_year if self.reference_data else 0

    def _rank_reference_source(self) -> str:
        return self.reference_data.rank_source if self.reference_data and self.reference_data.rank_source else "尚未发布可用的历史一分一段参考数据"


def basis_with_next_step(basis: list[str]) -> list[str]:
    return basis + ["下次录入优先补全年级排名、年级人数和体育实际成绩；系统会保留本次判断，不会覆盖历史报告。"]
