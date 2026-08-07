from dataclasses import dataclass


@dataclass(frozen=True)
class SchoolAdmissionObservation:
    school: str
    reference_year: int
    rank: int
    candidate_count: int
    plan: int | None = None
    previous_year_plan: int | None = None
    batch: str | None = None
    anomaly: bool = False


@dataclass(frozen=True)
class SchoolBoundary:
    school: str
    rank_range: tuple[int, int]
    percentile_range: tuple[float, float]
    confidence: str
    observation_count: int
    reasons: tuple[str, ...]


class SchoolBoundaryModel:
    version = "school-boundary-weighted-v1"

    def __init__(self, parameters: dict | None = None) -> None:
        self.parameters = parameters or {}

    def estimate(
        self,
        school: str,
        observations: tuple[SchoolAdmissionObservation, ...],
        target_candidate_count: int,
    ) -> SchoolBoundary | None:
        usable = sorted((item for item in observations if item.rank > 0 and item.candidate_count > 0), key=lambda item: item.reference_year, reverse=True)
        if not usable or target_candidate_count <= 0:
            return None
        decay = min(1.0, max(0.1, float(self.parameters.get("year_decay", 0.75))))
        weighted: list[tuple[float, float]] = []
        anomaly_count = 0
        for index, item in enumerate(usable):
            percentile = item.rank / item.candidate_count * 100
            weight = decay ** index
            if item.anomaly:
                weight *= float(self.parameters.get("anomaly_weight", 0.35))
                anomaly_count += 1
            weighted.append((percentile, weight))
        center = sum(value * weight for value, weight in weighted) / sum(weight for _, weight in weighted)
        latest = usable[0]
        plan_change = None
        if latest.plan and latest.previous_year_plan:
            plan_change = (latest.plan - latest.previous_year_plan) / latest.previous_year_plan
            center *= 1 + plan_change * float(self.parameters.get("plan_elasticity", 0.7))
        deviation = sum(abs(value - center) * weight for value, weight in weighted) / sum(weight for _, weight in weighted)
        half_width = max(float(self.parameters.get("minimum_boundary_width_pp", 0.8)), deviation)
        if len(usable) < int(self.parameters.get("preferred_observation_count", 3)):
            half_width += float(self.parameters.get("sparse_data_extra_width_pp", 1.5))
        if anomaly_count:
            half_width += float(self.parameters.get("anomaly_extra_width_pp", 0.8))
        low = max(0.01, center - half_width)
        high = min(100.0, center + half_width)
        rank_range = (max(1, round(low / 100 * target_candidate_count)), max(1, round(high / 100 * target_candidate_count)))
        reasons = [f"已参考近 {len(usable)} 年录取位置"]
        if plan_change is not None:
            reasons.append("已结合最新招生计划变化")
        if anomaly_count:
            reasons.append("异常年份已降低权重")
        confidence = "high" if len(usable) >= 3 and not anomaly_count else "medium" if len(usable) >= 2 else "low"
        return SchoolBoundary(
            school=school,
            rank_range=rank_range,
            percentile_range=(round(low, 2), round(high, 2)),
            confidence=confidence,
            observation_count=len(usable),
            reasons=tuple(reasons),
        )
