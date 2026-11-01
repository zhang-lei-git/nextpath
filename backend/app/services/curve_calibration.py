"""Offline curve reconstruction experiment, never imported by production prediction.

Anchors are target-year observations, so holdout errors measure interpolation only;
they are NOT evidence of pre-exam forecasting quality or next-year generalization.
"""
from dataclasses import dataclass
from math import isfinite
from statistics import mean, median


def interpolate(points: tuple[tuple[float, int], ...], score: float) -> float | None:
    ordered = sorted(points, reverse=True)
    if len(ordered) < 2 or not ordered[-1][0] <= score <= ordered[0][0]:
        return None
    for (high, high_rank), (low, low_rank) in zip(ordered, ordered[1:]):
        if low <= score <= high:
            return high_rank + (high - score) / (high - low) * (low_rank - high_rank)
    return None


def validate_curve(points: tuple[tuple[float, int], ...], full_mark: float, candidates: int | None) -> list[str]:
    warnings = []
    ordered = sorted(points, reverse=True)
    if len(ordered) < 2:
        return ['曲线至少需要两个点']
    if any(not isfinite(score) or not 0 <= score <= full_mark or rank < 1 for score, rank in ordered):
        warnings.append('曲线含越界分数或无效位次')
    if any(high <= low or high_rank >= low_rank for (high, high_rank), (low, low_rank) in zip(ordered, ordered[1:])):
        warnings.append('曲线分数或累计位次不严格单调')
    if candidates is None:
        warnings.append('缺少全体考生人数；禁止以截断曲线末位累计人数代替')
    elif max(rank for _, rank in ordered) > candidates:
        warnings.append('声明的考生人数小于曲线最大累计位次，百分位口径不可用')
    return warnings


def metrics(rows: list[dict], field: str) -> dict:
    errors = [row[field] for row in rows if row.get(field) is not None]
    return {
        'samples': len(errors),
        'mae': round(mean(abs(value) for value in errors), 2) if errors else None,
        'median_absolute_error': round(median(abs(value) for value in errors), 2) if errors else None,
        'bias': round(mean(errors), 2) if errors else None,
    }


@dataclass(frozen=True)
class PiecewiseCalibration:
    anchors: tuple[tuple[float, int], ...]
    target_year: int
    source_release_id: str

    def estimate(self, score: float) -> float | None:
        return interpolate(self.anchors, score)


def fit_holdout(points: tuple[tuple[float, int], ...], *, target_year: int, release_id: str, stride: int = 10):
    if stride < 2:
        raise ValueError('stride must be at least 2')
    ordered = sorted(points, reverse=True)
    anchor_indices = set(range(0, len(ordered), stride)) | {0, len(ordered) - 1}
    anchors = tuple(point for index, point in enumerate(ordered) if index in anchor_indices)
    if len(anchors) < 2 or validate_curve(anchors, max(score for score, _ in anchors), max(rank for _, rank in anchors)):
        raise ValueError('Invalid calibration anchors')
    model = PiecewiseCalibration(anchors, target_year, release_id)
    holdout = [point for index, point in enumerate(ordered) if index not in anchor_indices]
    return model, holdout
