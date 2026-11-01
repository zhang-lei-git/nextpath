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


def test_decay_uses_calendar_year_gaps_and_extreme_plan_growth_is_bounded():
    model = SchoolBoundaryModel({'year_decay': 0.5})
    recent = model.estimate('测试高中',(observation(2025,5000),observation(2024,15000)),50000)
    older = model.estimate('测试高中',(observation(2025,5000),observation(2020,15000)),50000)
    assert sum(older.percentile_range) < sum(recent.percentile_range)
    extreme = model.estimate('测试高中',(observation(2025,49000,plan=10000,previous=100),),50000)
    assert 1 <= extreme.rank_range[0] <= extreme.rank_range[1] <= 50000


def test_versioned_school_parameters_reject_invalid_values(monkeypatch):
    from fastapi import HTTPException
    import asyncio
    from types import SimpleNamespace
    from app.services.analysis_model_service import AnalysisModelService, DEFAULT_SCHOOL_BOUNDARY_PARAMETERS
    from app.domain.schemas import AnalysisModelUpdate
    service=AnalysisModelService(None)
    async def existing(_):
        return SimpleNamespace(parameters=DEFAULT_SCHOOL_BOUNDARY_PARAMETERS,analysis_type='school_boundary')
    monkeypatch.setattr(service.repository,'model_by_id',existing)
    import pytest
    for params in [{'year_decay':2},{'preferred_observation_count':1.5},{'plan_elasticity':-1}]:
        with pytest.raises(HTTPException) as error:
            asyncio.run(service.update_model('test',AnalysisModelUpdate(status='active',parameters=params)))
        assert error.value.status_code==422
