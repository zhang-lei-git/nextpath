"""Evidence-aware fusion for a student's pre-exam admissions position.

The two inputs are deliberately kept separate: a score can be distorted by a
particular mock paper, while a grade rank is conditional on the junior school.
They become more useful together, but are never treated as independent facts
with zero uncertainty.
"""

from dataclasses import dataclass
from math import sqrt
from typing import Iterable

from app.services.position_engine import CalibrationPoint


DEFAULT_FUSION_PARAMETERS = {
    "score_channel_base_uncertainty_pp": 8.0,
    "rank_channel_prior_uncertainty_pp": 12.0,
    "rank_channel_calibrated_uncertainty_pp": 5.0,
    "rank_channel_min_samples": 15,
    "fusion_conflict_threshold_pp": 8.0,
    "fusion_conflict_uncertainty_multiplier": 1.35,
    "fusion_correlation_inflation": 1.25,
    "difficulty_stage_uncertainty_pp": {
        "一模": 6.0,
        "二模": 5.0,
        "三模": 4.0,
        "月考": 8.0,
        "期中": 8.0,
        "期末": 7.0,
        "周测": 10.0,
    },
    # Only reviewed profiles with enough evidence may move a score estimate.
    "school_difficulty_profiles": {},
    "difficulty_profile_min_samples": 20,
}


@dataclass(frozen=True)
class PositionChannel:
    name: str
    percentile_range: tuple[float, float]
    center: float
    uncertainty_pp: float
    sample_count: int = 0
    method: str = ""
    difficulty_applied: bool = False

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "percentile_range": self.percentile_range,
            "center": self.center,
            "uncertainty_pp": self.uncertainty_pp,
            "sample_count": self.sample_count,
            "method": self.method,
            "difficulty_applied": self.difficulty_applied,
        }


@dataclass(frozen=True)
class FusedPosition:
    percentile_range: tuple[float, float] | None
    center: float | None
    method: str
    confidence: str
    score_weight: float | None = None
    rank_weight: float | None = None
    conflict_pp: float | None = None

    def as_dict(self) -> dict:
        return {
            "percentile_range": self.percentile_range,
            "center": self.center,
            "method": self.method,
            "confidence": self.confidence,
            "score_weight": self.score_weight,
            "rank_weight": self.rank_weight,
            "conflict_pp": self.conflict_pp,
        }


class PositionFusionEngine:
    def __init__(self, parameters: dict | None = None) -> None:
        self.parameters = {**DEFAULT_FUSION_PARAMETERS, **(parameters or {})}

    def score_channel(
        self,
        percentile_range: tuple[float, float] | None,
        *,
        junior_school: str | None,
        assessment_stage: str | None,
    ) -> PositionChannel | None:
        if not percentile_range:
            return None
        low, high = percentile_range
        center = (low + high) / 2
        uncertainty = float(self.parameters["score_channel_base_uncertainty_pp"])
        uncertainty += self._stage_uncertainty(assessment_stage)
        profile = self._difficulty_profile(junior_school, assessment_stage)
        applied = profile is not None
        if profile:
            center += float(profile.get("percentile_shift_pp", 0))
            uncertainty += max(0, float(profile.get("residual_uncertainty_pp", 0)))
        return self._channel(
            "score",
            center,
            uncertainty,
            sample_count=int(profile.get("sample_count", 0)) if profile else 0,
            method="score_bridge_with_verified_difficulty" if applied else "score_bridge",
            difficulty_applied=applied,
        )

    def rank_channel(
        self,
        *,
        grade_rank: int | None,
        grade_size: int | None,
        candidate_count: int | None,
        calibration_points: Iterable[CalibrationPoint],
    ) -> PositionChannel | None:
        if not grade_rank or not grade_size or grade_rank > grade_size:
            return None
        local_percentile = grade_rank / grade_size * 100
        points = tuple(calibration_points)
        calibrated = self._calibrated_percentile(local_percentile, points, candidate_count)
        min_samples = int(self.parameters["rank_channel_min_samples"])
        if calibrated is not None and len(points) >= min_samples:
            return self._channel(
                "rank",
                calibrated,
                float(self.parameters["rank_channel_calibrated_uncertainty_pp"]),
                sample_count=len(points),
                method="junior_school_calibration",
            )
        return self._channel(
            "rank",
            local_percentile,
            float(self.parameters["rank_channel_prior_uncertainty_pp"]),
            sample_count=len(points),
            method="junior_school_percentile_prior",
        )

    def fuse(self, score: PositionChannel | None, rank: PositionChannel | None) -> FusedPosition:
        available = [item for item in (score, rank) if item]
        if not available:
            return FusedPosition(None, None, "insufficient_data", "low")
        if len(available) == 1:
            only = available[0]
            return FusedPosition(only.percentile_range, only.center, f"{only.name}_only", "low")

        score_precision = 1 / max(score.uncertainty_pp, 0.1) ** 2
        rank_precision = 1 / max(rank.uncertainty_pp, 0.1) ** 2
        score_weight = score_precision / (score_precision + rank_precision)
        rank_weight = 1 - score_weight
        center = score.center * score_weight + rank.center * rank_weight
        conflict = abs(score.center - rank.center)
        combined_uncertainty = sqrt(1 / (score_precision + rank_precision)) * float(
            self.parameters["fusion_correlation_inflation"]
        )
        conflict_threshold = float(self.parameters["fusion_conflict_threshold_pp"])
        if conflict > conflict_threshold:
            combined_uncertainty *= float(self.parameters["fusion_conflict_uncertainty_multiplier"])
            low = min(score.percentile_range[0], rank.percentile_range[0], center - combined_uncertainty)
            high = max(score.percentile_range[1], rank.percentile_range[1], center + combined_uncertainty)
            confidence = "low"
            method = "dual_channel_conflict_review"
        else:
            low, high = center - combined_uncertainty, center + combined_uncertainty
            confidence = "high" if score.difficulty_applied and rank.sample_count >= int(self.parameters["rank_channel_min_samples"]) else "medium"
            method = "dual_channel_fusion"
        return FusedPosition(
            self._clamp_range(low, high),
            round(self._clamp(center), 2),
            method,
            confidence,
            round(score_weight, 3),
            round(rank_weight, 3),
            round(conflict, 2),
        )

    def _difficulty_profile(self, junior_school: str | None, assessment_stage: str | None) -> dict | None:
        if not junior_school:
            return None
        profiles = self.parameters.get("school_difficulty_profiles", {})
        if not isinstance(profiles, dict):
            return None
        school = self._normalize_school(junior_school)
        keys = (f"{school}|{assessment_stage}", f"{school}|all", school)
        for key in keys:
            profile = profiles.get(key)
            if not isinstance(profile, dict) or not profile.get("verified"):
                continue
            if int(profile.get("sample_count", 0)) >= int(self.parameters["difficulty_profile_min_samples"]):
                return profile
        return None

    def _stage_uncertainty(self, assessment_stage: str | None) -> float:
        stages = self.parameters.get("difficulty_stage_uncertainty_pp", {})
        return float(stages.get(assessment_stage, stages.get("default", 6.0))) if isinstance(stages, dict) else 6.0

    @staticmethod
    def _calibrated_percentile(
        local_percentile: float, points: tuple[CalibrationPoint, ...], candidate_count: int | None
    ) -> float | None:
        if not candidate_count or len(points) < 2:
            return None
        mapped = sorted(
            ((
                item.grade_rank / item.grade_size * 100,
                item.final_city_rank / (item.final_candidate_count or candidate_count) * 100,
            ) for item in points),
            key=lambda item: item[0],
        )
        if local_percentile < mapped[0][0] or local_percentile > mapped[-1][0]:
            return None
        for low, high in zip(mapped, mapped[1:]):
            if low[0] <= local_percentile <= high[0]:
                if low[0] == high[0]:
                    return (low[1] + high[1]) / 2
                ratio = (local_percentile - low[0]) / (high[0] - low[0])
                return low[1] + (high[1] - low[1]) * ratio
        return mapped[-1][1]

    @classmethod
    def _channel(
        cls, name: str, center: float, uncertainty: float, *, sample_count: int, method: str, difficulty_applied: bool = False
    ) -> PositionChannel:
        return PositionChannel(
            name=name,
            percentile_range=cls._clamp_range(center - uncertainty, center + uncertainty),
            center=round(cls._clamp(center), 2),
            uncertainty_pp=round(uncertainty, 2),
            sample_count=sample_count,
            method=method,
            difficulty_applied=difficulty_applied,
        )

    @staticmethod
    def _normalize_school(name: str) -> str:
        return "".join(name.replace("（", "(").replace("）", ")").split())

    @staticmethod
    def _clamp(value: float) -> float:
        return min(99.9, max(0.1, value))

    @classmethod
    def _clamp_range(cls, low: float, high: float) -> tuple[float, float]:
        return (round(cls._clamp(min(low, high)), 2), round(cls._clamp(max(low, high)), 2))
