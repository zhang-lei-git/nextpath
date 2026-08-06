from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class ScoringScheme:
    year: int
    total_full_mark: float
    counted_subjects: dict[str, float]
    published_on: date
    source_title: str
    source_url: str


@dataclass(frozen=True)
class ScoreBridgeResult:
    source_year: int
    target_year: int
    source_total_range: tuple[float, float]
    target_equivalent_range: tuple[float, float]
    method: str
    projected_subjects: tuple[str, ...]
    source: str


SCORING_SCHEMES = {
    2025: ScoringScheme(
        year=2025,
        total_full_mark=820,
        counted_subjects={
            "chinese": 120, "math": 120, "english": 120, "physics": 80,
            "politics": 80, "chemistry": 60, "history": 60, "pe": 60,
            "biology": 60, "geography": 60,
        },
        published_on=date(2025, 2, 20),
        source_title="西安市教育局关于调整中考计分科目的通知",
        source_url="https://edu.xa.gov.cn/xwzx/tzgg/1892376145395486722.html",
    ),
    2026: ScoringScheme(
        year=2026,
        total_full_mark=640,
        counted_subjects={
            "chinese": 120, "math": 120, "english": 120, "physics": 80,
            "politics": 80, "history": 60, "pe": 60,
        },
        published_on=date(2025, 3, 15),
        source_title="西安市教育局中考计分科目调整通知及年度考试通知",
        source_url="https://edu.xa.gov.cn/xwzx/tzgg/1892376145395486722.html",
    ),
}


class ScoreBridgeModel:
    """Converts score composition, never rank or admission outcome, across years."""

    version = "subject-bridge-v1"

    def bridge(
        self,
        source_total_range: tuple[float, float],
        source_year: int,
        target_year: int,
        subject_scores: dict[str, float] | None = None,
        as_of_date: date | None = None,
    ) -> ScoreBridgeResult | None:
        source = SCORING_SCHEMES.get(source_year)
        target = SCORING_SCHEMES.get(target_year)
        if not source or not target:
            return None
        if as_of_date and (source.published_on > as_of_date or target.published_on > as_of_date):
            return None
        subject_scores = subject_scores or {}
        common = set(source.counted_subjects) & set(target.counted_subjects)
        added = tuple(sorted(set(target.counted_subjects) - common))
        removed = set(source.counted_subjects) - common
        common_full_mark = sum(source.counted_subjects[key] for key in common)
        removed_known = sum(subject_scores.get(key, 0) for key in removed if key in subject_scores)
        removed_missing_full_mark = sum(source.counted_subjects[key] for key in removed if key not in subject_scores)
        added_known = sum(subject_scores.get(key, 0) for key in added if key in subject_scores)
        added_known_full_mark = sum(target.counted_subjects[key] for key in added if key in subject_scores)
        added_missing_full_mark = sum(target.counted_subjects[key] for key in added if key not in subject_scores)
        converted = []
        for total in source_total_range:
            remaining_score = max(0, total - removed_known)
            remaining_full_mark = max(1, common_full_mark + removed_missing_full_mark)
            common_rate = min(1, remaining_score / remaining_full_mark)
            common_score = common_rate * common_full_mark
            converted.append(common_score + added_known + common_rate * added_missing_full_mark)
        method = "subject_bridge_with_observed_scores" if added_known_full_mark else "subject_bridge_rate_projection"
        return ScoreBridgeResult(
            source_year=source_year,
            target_year=target_year,
            source_total_range=source_total_range,
            target_equivalent_range=(round(min(converted), 1), round(max(converted), 1)),
            method=method,
            projected_subjects=tuple(key for key in added if key not in subject_scores),
            source=f"{source.source_title}；{target.source_title}",
        )


def scoring_scheme(year: int) -> ScoringScheme | None:
    return SCORING_SCHEMES.get(year)
