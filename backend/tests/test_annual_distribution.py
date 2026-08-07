from app.services.annual_distribution import AnnualDistributionModel


def test_annual_distribution_scales_score_and_candidate_coordinates() -> None:
    curve = AnnualDistributionModel().project(
        region="西安",
        target_year=2026,
        reference_year=2025,
        historical_points=((820, 1), (780, 2000), (700, 15000), (610, 49900)),
        historical_full_mark=820,
        historical_candidate_count=49900,
        target_full_mark=640,
        target_candidate_count=52000,
        source_release_id="release-2025",
    )

    assert curve is not None
    assert curve.target_year == 2026
    assert curve.reference_year == 2025
    assert curve.candidate_count == 52000
    assert curve.source_release_id == "release-2025"
    assert curve.points[0] == (640, 1)
    assert all(
        high_score > low_score and high_rank < low_rank
        for (high_score, high_rank), (low_score, low_rank) in zip(curve.points, curve.points[1:])
    )


def test_annual_distribution_estimate_is_monotonic() -> None:
    curve = AnnualDistributionModel({"rank_interval_ratio": 0.08}).project(
        region="西安",
        target_year=2026,
        reference_year=2025,
        historical_points=((820, 1), (780, 2000), (700, 15000), (610, 49900)),
        historical_full_mark=820,
        historical_candidate_count=49900,
        target_full_mark=640,
    )

    assert curve is not None
    high = curve.estimate(600)
    low = curve.estimate(550)
    assert high.rank is not None and low.rank is not None
    assert high.rank < low.rank


def test_backtest_uses_a_separate_validation_curve() -> None:
    result = AnnualDistributionModel({"rank_interval_ratio": 0.1, "minimum_rank_interval": 1000}).backtest(
        region="西安",
        training_year=2024,
        training_points=((800, 1), (700, 12000), (600, 48000)),
        training_full_mark=800,
        training_candidate_count=48000,
        validation_year=2025,
        validation_points=((820, 1), (717.5, 12500), (615, 50000)),
        validation_full_mark=820,
        validation_candidate_count=50000,
    )

    assert result.sample_size == 3
    assert result.monotonic is True
    assert result.median_absolute_rank_error is not None
    assert result.interval_coverage is not None
