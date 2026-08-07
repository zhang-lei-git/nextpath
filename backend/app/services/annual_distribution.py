from dataclasses import dataclass

from app.services.position_engine import PositionEngine, PositionEstimate


@dataclass(frozen=True)
class AnnualDistributionProjection:
    region: str
    target_year: int
    reference_year: int
    model_version: str
    target_full_mark: float
    candidate_count: int
    points: tuple[tuple[float, int], ...]
    source_release_id: str | None = None

    def estimate(self, score: float, parameters: dict | None = None) -> PositionEstimate:
        return PositionEngine(self.points, parameters).estimate(score)

    def score_for_percentile(self, percentile: float) -> float | None:
        rank = min(self.candidate_count, max(1, percentile / 100 * self.candidate_count))
        if len(self.points) < 2 or rank < self.points[0][1] or rank > self.points[-1][1]:
            return None
        for high, low in zip(self.points, self.points[1:]):
            high_score, high_rank = high
            low_score, low_rank = low
            if high_rank <= rank <= low_rank:
                if low_rank == high_rank:
                    return round((high_score + low_score) / 2, 1)
                ratio = (rank - high_rank) / (low_rank - high_rank)
                return round(high_score - (high_score - low_score) * ratio, 1)
        return self.points[-1][0]

    def score_range_for_percentiles(self, percentile_range: tuple[float, float]) -> tuple[float, float] | None:
        scores = [self.score_for_percentile(value) for value in percentile_range]
        scores = [score for score in scores if score is not None]
        return (min(scores), max(scores)) if len(scores) == 2 else None


@dataclass(frozen=True)
class AnnualDistributionBacktest:
    sample_size: int
    median_absolute_rank_error: float | None
    interval_coverage: float | None
    monotonic: bool


class AnnualDistributionModel:
    """Cold-start projection of a target-year score/rank curve.

    The baseline preserves the historical percentile distribution while moving
    score and candidate-count coordinates to the target cohort. It is deliberately
    simple, versioned and backtestable so later statistical models can replace it
    without changing prediction consumers.
    """

    version = "annual-curve-scale-v1"

    def __init__(self, parameters: dict | None = None, model_version: str | None = None) -> None:
        self.parameters = parameters or {}
        if model_version:
            self.version = model_version

    def project(
        self,
        *,
        region: str,
        target_year: int,
        reference_year: int,
        historical_points: tuple[tuple[float, int], ...],
        historical_full_mark: float,
        historical_candidate_count: int,
        target_full_mark: float,
        target_candidate_count: int | None = None,
        source_release_id: str | None = None,
    ) -> AnnualDistributionProjection | None:
        if len(historical_points) < 2 or historical_full_mark <= 0 or target_full_mark <= 0:
            return None
        target_candidates = target_candidate_count or round(
            historical_candidate_count * float(self.parameters.get("candidate_count_multiplier", 1.0))
        )
        target_candidates = max(1, target_candidates)
        score_shift = float(self.parameters.get("target_score_shift", 0.0))
        projected: list[tuple[float, int]] = []
        for score, rank in historical_points:
            target_score = min(target_full_mark, max(0, score / historical_full_mark * target_full_mark + score_shift))
            target_rank = min(target_candidates, max(1, round(rank / historical_candidate_count * target_candidates)))
            projected.append((round(target_score, 2), target_rank))
        points = self._monotonic_points(projected)
        if len(points) < 2:
            return None
        return AnnualDistributionProjection(
            region=region,
            target_year=target_year,
            reference_year=reference_year,
            model_version=self.version,
            target_full_mark=target_full_mark,
            candidate_count=target_candidates,
            points=points,
            source_release_id=source_release_id,
        )

    def backtest(
        self,
        *,
        region: str,
        training_year: int,
        training_points: tuple[tuple[float, int], ...],
        training_full_mark: float,
        training_candidate_count: int,
        validation_year: int,
        validation_points: tuple[tuple[float, int], ...],
        validation_full_mark: float,
        validation_candidate_count: int,
    ) -> AnnualDistributionBacktest:
        projection = self.project(
            region=region,
            target_year=validation_year,
            reference_year=training_year,
            historical_points=training_points,
            historical_full_mark=training_full_mark,
            historical_candidate_count=training_candidate_count,
            target_full_mark=validation_full_mark,
            target_candidate_count=validation_candidate_count,
        )
        if not projection:
            return AnnualDistributionBacktest(0, None, None, False)
        errors: list[float] = []
        covered = 0
        for score, actual_rank in validation_points:
            estimate = projection.estimate(score, self.parameters)
            if estimate.rank is None:
                continue
            errors.append(abs(estimate.rank - actual_rank))
            if estimate.rank_range[0] <= actual_rank <= estimate.rank_range[1]:
                covered += 1
        errors.sort()
        median = errors[len(errors) // 2] if errors else None
        monotonic = all(
            high_score > low_score and high_rank < low_rank
            for (high_score, high_rank), (low_score, low_rank) in zip(projection.points, projection.points[1:])
        )
        return AnnualDistributionBacktest(
            sample_size=len(errors),
            median_absolute_rank_error=median,
            interval_coverage=round(covered / len(errors), 4) if errors else None,
            monotonic=monotonic,
        )

    @staticmethod
    def _monotonic_points(points: list[tuple[float, int]]) -> tuple[tuple[float, int], ...]:
        ordered = sorted(points, key=lambda item: item[0], reverse=True)
        result: list[tuple[float, int]] = []
        last_rank = 0
        for score, rank in ordered:
            rank = max(last_rank + (1 if result else 0), rank)
            if result and score == result[-1][0]:
                result[-1] = (score, max(result[-1][1], rank))
            else:
                result.append((score, rank))
            last_rank = result[-1][1]
        return tuple(result)
