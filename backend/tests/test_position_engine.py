from app.services.position_engine import CalibrationPoint, PositionEngine


def test_school_mapping_requires_enough_samples_and_blends_with_rank_curve() -> None:
    points = ((620, 1_000), (600, 3_000), (580, 6_000))
    calibration = (
        CalibrationPoint(10, 100, 900),
        CalibrationPoint(30, 100, 2_700),
        CalibrationPoint(50, 100, 4_800),
        CalibrationPoint(70, 100, 7_000),
    )
    engine = PositionEngine(
        points,
        {
            "rank_interval_ratio": 0.06,
            "minimum_rank_interval": 400,
            "school_mapping_min_samples": 4,
            "school_mapping_weight": 0.5,
        },
        calibration,
    )

    estimate = engine.estimate(600, grade_rank=30, grade_size=100)

    assert estimate.rank == 2_850
    assert estimate.rank_range == (2_450, 3_250)
    assert estimate.method == "rank_curve_with_school_mapping"
    assert estimate.calibration_sample_count == 4


def test_school_mapping_falls_back_when_student_grade_size_is_missing() -> None:
    engine = PositionEngine(
        ((620, 1_000), (600, 3_000), (580, 6_000)),
        {"school_mapping_min_samples": 2},
        (CalibrationPoint(10, 100, 900), CalibrationPoint(30, 100, 2_700)),
    )

    estimate = engine.estimate(600, grade_rank=30)

    assert estimate.rank == 3_000
    assert estimate.method == "rank_curve"
