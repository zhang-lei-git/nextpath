from datetime import date

from app.services.scoring_scheme import ScoreBridgeModel, scoring_scheme


def test_official_scoring_schemes_are_explicit() -> None:
    scheme_2025 = scoring_scheme(2025)
    scheme_2026 = scoring_scheme(2026)

    assert scheme_2025 and sum(scheme_2025.counted_subjects.values()) == 820
    assert scheme_2026 and sum(scheme_2026.counted_subjects.values()) == 640
    assert set(scheme_2025.counted_subjects) - set(scheme_2026.counted_subjects) == {"chemistry", "biology", "geography"}


def test_bridge_projects_removed_subjects_instead_of_comparing_raw_scores() -> None:
    result = ScoreBridgeModel().bridge((571, 577), 2026, 2025)

    assert result is not None
    assert result.target_equivalent_range == (731.6, 739.3)
    assert result.projected_subjects == ("biology", "chemistry", "geography")


def test_bridge_uses_known_removed_subject_scores_when_available() -> None:
    result = ScoreBridgeModel().bridge(
        (577, 577), 2026, 2025,
        {"chemistry": 52, "biology": 55, "geography": 56},
    )

    assert result is not None
    assert result.target_equivalent_range == (740, 740)
    assert result.projected_subjects == ()


def test_bridge_rejects_policy_information_not_yet_available() -> None:
    result = ScoreBridgeModel().bridge((560, 560), 2026, 2025, as_of_date=date(2025, 3, 1))

    assert result is None


def test_reverse_bridge_removes_known_non_counted_subjects() -> None:
    result = ScoreBridgeModel().bridge(
        (740, 740), 2025, 2026,
        {"chemistry": 52, "biology": 55, "geography": 56},
    )

    assert result is not None
    assert result.target_equivalent_range == (577, 577)
