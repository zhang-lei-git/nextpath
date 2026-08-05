from app.services.prediction import BaselinePredictionEngine, PredictionInput
from app.services.published_reference_data import PublishedReferenceData, PublishedSchoolReference


def test_baseline_prediction_is_explainable() -> None:
    forecast = BaselinePredictionEngine().predict(
        PredictionInput(total_score=615, class_rank=28, target_school="西安高新第一中学")
    )

    assert forecast.tier == "省示范高中层"
    assert forecast.target_gap == 0
    assert forecast.model_version == "baseline-2026.1"
    assert len(forecast.basis) == 2


def test_baseline_prediction_does_not_promise_admission() -> None:
    forecast = BaselinePredictionEngine().predict(
        PredictionInput(total_score=540, class_rank=None, target_school=None)
    )

    assert forecast.confidence == "low"
    assert forecast.target_gap is None
    assert "全区参考位置" in forecast.basis[1]


def test_prediction_prefers_published_reference_data() -> None:
    reference_data = PublishedReferenceData(
        reference_year=2027,
        rank_source="2027 年已发布一分一段表",
        rank_points=((600, 1000), (590, 2000)),
        school_references=(PublishedSchoolReference("测试高中", 596, "2027 年已发布招生参考"),),
        policy_summary="2027 年已发布政策摘要。",
    )
    engine = BaselinePredictionEngine(reference_data)
    prediction_input = PredictionInput(total_score=595, class_rank=None, target_school="测试高中")

    forecast = engine.predict(prediction_input)
    report = engine.build_report(prediction_input)

    assert forecast.reference_year == 2027
    assert forecast.estimated_rank_range == (1100, 1900)
    assert forecast.target_gap == 1
    assert "2027 年已发布一分一段表" in forecast.basis[0]
    assert "2027 年已发布招生参考" in report.target_summary
    assert report.policy_summary == "2027 年已发布政策摘要。"
