from dataclasses import dataclass
from typing import Protocol

from app.domain.schemas import AdmissionReport, Forecast
from app.services.admission_data import (
    POLICY_SUMMARY, RANK_REFERENCE_SOURCE, RANK_REFERENCE_YEAR, estimate_city_rank, find_school_reference,
)
from app.services.published_reference_data import PublishedReferenceData


@dataclass(frozen=True)
class PredictionInput:
    total_score: float
    class_rank: int | None
    target_school: str | None
    junior_school: str | None = None
    trend_delta: float | None = None


class PredictionEngine(Protocol):
    """A stable port for rule, statistical, or model-backed prediction engines."""

    def predict(self, input_data: PredictionInput) -> Forecast: ...


class BaselinePredictionEngine:
    """Transparent MVP baseline. Thresholds are configuration, not admission facts."""

    version = "baseline-2026.1"
    reference_year = 2026

    def __init__(self, reference_data: PublishedReferenceData | None = None) -> None:
        self.reference_data = reference_data

    def predict(self, input_data: PredictionInput) -> Forecast:
        score = input_data.total_score
        city_rank = self._estimate_city_rank(score)
        if city_rank is None:
            tier, rank = "当前分数暂无法映射全区位次", (0, 0)
        elif score >= 600:
            tier, rank = "省示范高中层", (max(1, city_rank - 500), city_rank + 500)
        elif score >= 570:
            tier, rank = "省级标准化高中层", (max(1, city_rank - 800), city_rank + 800)
        else:
            tier, rank = "普通高中与综合高中班层", (max(1, city_rank - 1200), city_rank + 1200)

        target = self._find_school_reference(input_data.target_school)
        target_gap = max(0, target[1] - score) if target else None

        return Forecast(
            tier=tier,
            estimated_rank_range=rank,
            target_gap=target_gap,
            confidence="low",
            basis=[
                f"按 {self._rank_reference_source()} 折算当前总分的全区参考位置。",
                "已参考历次成绩变化；所在初中的历史成绩样本还在积累中，本次以全区参考位置为主。",
            ],
            model_version=self.version,
            reference_year=self._reference_year(),
        )

    def build_report(self, input_data: PredictionInput) -> AdmissionReport:
        forecast = self.predict(input_data)
        rank = self._estimate_city_rank(input_data.total_score)
        target = self._find_school_reference(input_data.target_school)
        trend = input_data.trend_delta
        trend_summary = "成绩记录不足两次，暂不判断趋势。" if trend is None else (
            f"最近两次总分变化 {trend:+.1f} 分，已计入本次位置判断。"
        )
        target_summary = "尚未设定目标高中，可先看当前层次，再在档案中补充。" if not target else (
            f"目标 {target[0]} 的公开参考线约 {target[1]:.0f} 分；当前参考差距 {max(0, target[1] - input_data.total_score):.0f} 分。{target[2]}。"
        )
        return AdmissionReport(
            headline=f"当前更适合关注：{forecast.tier}",
            current_position=(f"按 {self._reference_year()} 年参考表，当前约全区第 {rank:,} 名。" if rank else "本次总分不在当前参考表覆盖范围内，无法可靠折算全区位次。"),
            trend_summary=trend_summary,
            target_summary=target_summary,
            school_context=(f"已记录初中：{input_data.junior_school}。该校的历史成绩样本还在积累中，本次以全区参考位置为主。" if input_data.junior_school else "补充孩子所在初中后，判断会更贴近实际升学环境。"),
            policy_summary=self._policy_summary(),
            key_points=[forecast.basis[0], forecast.basis[1], "下一步优先补录下一次考试的年级排名，使个人趋势与学校映射逐步收敛。"],
            data_sources=[self._rank_reference_source(), target[2] if target else "尚未选择目标学校", self._policy_source()],
        )

    def _estimate_city_rank(self, score: float) -> int | None:
        points = self.reference_data.rank_points if self.reference_data and self.reference_data.rank_points else None
        if not points:
            return estimate_city_rank(score)
        if score < points[-1][0] or score > points[0][0]:
            return None
        for high, low in zip(points, points[1:]):
            high_score, high_rank = high
            low_score, low_rank = low
            if low_score <= score <= high_score:
                ratio = (high_score - score) / (high_score - low_score)
                return round(high_rank + (low_rank - high_rank) * ratio)
        return points[-1][1]

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
