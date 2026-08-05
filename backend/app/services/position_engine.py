from dataclasses import dataclass


@dataclass(frozen=True)
class PositionEstimate:
    rank: int | None
    rank_range: tuple[int, int]


class PositionEngine:
    """Maps an observed score to an admissions position on a published rank curve."""

    def __init__(self, rank_points: tuple[tuple[float, int], ...], parameters: dict | None = None) -> None:
        self.rank_points = tuple(sorted(rank_points, reverse=True))
        self.parameters = parameters or {}

    def estimate(self, score: float) -> PositionEstimate:
        rank = self._interpolate(score)
        if rank is None:
            return PositionEstimate(rank=None, rank_range=(0, 0))
        ratio = float(self.parameters.get("rank_interval_ratio", 0.06))
        minimum = int(self.parameters.get("minimum_rank_interval", 400))
        width = max(minimum, round(rank * ratio))
        return PositionEstimate(rank=rank, rank_range=(max(1, rank - width), rank + width))

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
