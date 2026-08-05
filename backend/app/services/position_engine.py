from dataclasses import dataclass


@dataclass(frozen=True)
class PositionEstimate:
    rank: int | None
    rank_range: tuple[int, int]
    method: str = "rank_curve"
    calibration_sample_count: int = 0


@dataclass(frozen=True)
class CalibrationPoint:
    grade_rank: int
    grade_size: int
    final_city_rank: int


class PositionEngine:
    """Maps an observed score to an admissions position on a published rank curve."""

    def __init__(
        self,
        rank_points: tuple[tuple[float, int], ...],
        parameters: dict | None = None,
        calibration_points: tuple[CalibrationPoint, ...] = (),
    ) -> None:
        self.rank_points = tuple(sorted(rank_points, reverse=True))
        self.parameters = parameters or {}
        self.calibration_points = tuple(
            sorted(calibration_points, key=lambda item: item.grade_rank / item.grade_size)
        )

    def estimate(self, score: float, grade_rank: int | None = None, grade_size: int | None = None) -> PositionEstimate:
        base_rank = self._interpolate(score)
        if base_rank is None:
            return PositionEstimate(rank=None, rank_range=(0, 0))
        calibrated_rank = self._school_rank(grade_rank, grade_size)
        minimum_sample_size = int(self.parameters.get("school_mapping_min_samples", 15))
        if calibrated_rank is not None and len(self.calibration_points) >= minimum_sample_size:
            weight = min(1, max(0, float(self.parameters.get("school_mapping_weight", 0.35))))
            rank = round(base_rank * (1 - weight) + calibrated_rank * weight)
            method = "rank_curve_with_school_mapping"
        else:
            rank = base_rank
            method = "rank_curve"
        ratio = float(self.parameters.get("rank_interval_ratio", 0.06))
        minimum = int(self.parameters.get("minimum_rank_interval", 400))
        width = max(minimum, round(rank * ratio))
        return PositionEstimate(
            rank=rank,
            rank_range=(max(1, rank - width), rank + width),
            method=method,
            calibration_sample_count=len(self.calibration_points),
        )

    def _school_rank(self, grade_rank: int | None, grade_size: int | None) -> int | None:
        if not grade_rank or not grade_size or grade_rank > grade_size or len(self.calibration_points) < 2:
            return None
        percentile = grade_rank / grade_size
        points = [(item.grade_rank / item.grade_size, item.final_city_rank) for item in self.calibration_points]
        if percentile < points[0][0] or percentile > points[-1][0]:
            return None
        for low, high in zip(points, points[1:]):
            if low[0] <= percentile <= high[0]:
                if high[0] == low[0]:
                    return round((low[1] + high[1]) / 2)
                ratio = (percentile - low[0]) / (high[0] - low[0])
                return round(low[1] + (high[1] - low[1]) * ratio)
        return points[-1][1]

    def _interpolate(self, score: float) -> int | None:
        if len(self.rank_points) < 2 or score < self.rank_points[-1][0] or score > self.rank_points[0][0]:
            return None
        for high, low in zip(self.rank_points, self.rank_points[1:]):
            high_score, high_rank = high
            low_score, low_rank = low
            if low_score <= score <= high_score:
                ratio = (high_score - score) / (high_score - low_score)
                return round(high_rank + (low_rank - high_rank) * ratio)
        return self.rank_points[-1][1]
