from dataclasses import dataclass
from typing import Protocol

from app.domain.schemas import AdmissionReport, Forecast
from app.services.admission_data import (
    POLICY_SUMMARY, RANK_REFERENCE_SOURCE, RANK_REFERENCE_YEAR, estimate_city_rank, find_school_reference,
)


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

    def predict(self, input_data: PredictionInput) -> Forecast:
        score = input_data.total_score
        city_rank = estimate_city_rank(score)
        if city_rank is None:
            tier, rank = "当前分数暂无法映射全区位次", (0, 0)
        elif score >= 600:
            tier, rank = "省示范高中层", (max(1, city_rank - 500), city_rank + 500)
        elif score >= 570:
            tier, rank = "省级标准化高中层", (max(1, city_rank - 800), city_rank + 800)
        else:
            tier, rank = "普通高中与综合高中班层", (max(1, city_rank - 1200), city_rank + 1200)

        target = find_school_reference(input_data.target_school)
        target_gap = max(0, target.estimated_line - score) if target else None

        return Forecast(
            tier=tier,
            estimated_rank_range=rank,
            target_gap=target_gap,
            confidence="low",
            basis=[
                f"按 {RANK_REFERENCE_SOURCE} 折算当前总分的全区参考位置。",
                "已纳入历次成绩变化；初中到全区的历史映射数据尚未接入，因此不输出录取承诺。",
            ],
            model_version=self.version,
            reference_year=RANK_REFERENCE_YEAR,
        )

    def build_report(self, input_data: PredictionInput) -> AdmissionReport:
        forecast = self.predict(input_data)
        rank = estimate_city_rank(input_data.total_score)
        target = find_school_reference(input_data.target_school)
        trend = input_data.trend_delta
        trend_summary = "成绩记录不足两次，暂不判断趋势。" if trend is None else (
            f"最近两次总分变化 {trend:+.1f} 分，已计入本次位置判断。"
        )
        target_summary = "尚未设定目标高中，可先看当前层次，再在档案中补充。" if not target else (
            f"目标 {target.name} 的公开参考线约 {target.estimated_line:.0f} 分；当前参考差距 {max(0, target.estimated_line - input_data.total_score):.0f} 分。{target.source}。"
        )
        return AdmissionReport(
            headline=f"当前更适合关注：{forecast.tier}",
            current_position=(f"按 {RANK_REFERENCE_YEAR} 年参考表，当前约全区第 {rank:,} 名。" if rank else "本次总分不在当前参考表覆盖范围内，无法可靠折算全区位次。"),
            trend_summary=trend_summary,
            target_summary=target_summary,
            school_context=(f"已记录初中：{input_data.junior_school}。当前尚无该校历史成绩到全区位次的映射样本，报告未虚构校内换算。" if input_data.junior_school else "尚未填写初中，无法纳入学校维度。"),
            policy_summary=POLICY_SUMMARY,
            key_points=[forecast.basis[0], forecast.basis[1], "下一步优先补录下一次考试的年级排名，使个人趋势与学校映射逐步收敛。"],
            data_sources=[RANK_REFERENCE_SOURCE, target.source if target else "尚未选择目标学校", "2026 年西安市城六区中招政策摘要"],
        )
