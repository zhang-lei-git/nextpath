from app.services.school_boundary import SchoolAdmissionObservation, SchoolBoundaryModel


def observation(year: int, rank: int, *, plan: int | None = None, previous: int | None = None, anomaly: bool = False):
    return SchoolAdmissionObservation(
        school="测试高中",
        reference_year=year,
        rank=rank,
        candidate_count=50000,
        plan=plan,
        previous_year_plan=previous,
        anomaly=anomaly,
    )


def test_school_boundary_uses_multiple_years_and_returns_a_range() -> None:
    boundary = SchoolBoundaryModel().estimate(
        "测试高中",
        (observation(2025, 5000), observation(2024, 5300), observation(2023, 4800)),
        52000,
    )

    assert boundary is not None
    assert boundary.observation_count == 3
    assert boundary.rank_range[0] < boundary.rank_range[1]
    assert boundary.confidence == "high"


def test_more_admission_places_move_the_boundary_and_anomaly_widens_it() -> None:
    model = SchoolBoundaryModel()
    stable = model.estimate(
        "测试高中",
        (observation(2025, 5000), observation(2024, 5100), observation(2023, 4900)),
        50000,
    )
    expanded = model.estimate(
        "测试高中",
        (observation(2025, 5000, plan=550, previous=500), observation(2024, 5100), observation(2023, 4900, anomaly=True)),
        50000,
    )

    assert stable is not None and expanded is not None
    assert sum(expanded.rank_range) / 2 > sum(stable.rank_range) / 2
    assert expanded.rank_range[1] - expanded.rank_range[0] > stable.rank_range[1] - stable.rank_range[0]
