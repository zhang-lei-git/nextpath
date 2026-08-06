from datetime import date

from app.services.prediction import BaselinePredictionEngine, PredictionInput
from app.services.published_reference_data import PublishedReferenceData, PublishedSchoolReference


def test_baseline_prediction_is_explainable() -> None:
    reference_data = PublishedReferenceData(
        reference_year=2025,
        rank_source="2025 年一分一段表",
        rank_points=((820, 1), (780, 2000), (700, 15000), (610, 49900)),
        rank_full_mark=820,
        candidate_count=49900,
        school_references=(PublishedSchoolReference("测试高中", 780, "2025 年历史录取参考"),),
    )
    forecast = BaselinePredictionEngine(reference_data).predict(
        PredictionInput(total_score=520, total_full_mark=580, class_rank=28, grade_rank=28, grade_size=680, target_school="测试高中")
    )

    assert forecast.current_percentile is not None
    assert forecast.target_percentile is not None
    assert forecast.target_gap is None
    assert forecast.model_version == "historical-preexam-2026.2"
    assert "不使用本年度一分一段表" in forecast.basis[0]


def test_baseline_prediction_does_not_promise_admission() -> None:
    forecast = BaselinePredictionEngine().predict(
        PredictionInput(total_score=540, class_rank=None, target_school=None)
    )

    assert forecast.confidence == "low"
    assert forecast.target_gap is None
    assert "体育" in forecast.basis[1]


def test_pre_exam_prediction_uses_historical_reference_data() -> None:
    reference_data = PublishedReferenceData(
        reference_year=2025,
        rank_source="2025 年已发布一分一段表",
        rank_points=((820, 1), (780, 2000), (700, 15000), (610, 49900)),
        rank_full_mark=820,
        candidate_count=49900,
        school_references=(PublishedSchoolReference("测试高中", 780, "2025 年已发布招生参考"),),
        policy_summary="2025 年已发布政策摘要。",
    )
    engine = BaselinePredictionEngine(reference_data)
    prediction_input = PredictionInput(
        total_score=520, total_full_mark=580, physical_estimate=54, class_rank=None,
        target_school="测试高中", analysis_year=2026, analysis_date=date(2026, 3, 15),
    )

    forecast = engine.predict(prediction_input)
    report = engine.build_report(prediction_input)

    assert forecast.reference_year == 2025
    assert forecast.projected_total_range == (571, 577)
    assert forecast.historical_equivalent_score_range == (731.6, 739.3)
    assert forecast.score_bridge_method == "subject_bridge_rate_projection"
    assert forecast.current_percentile is not None
    assert "2025 年已发布一分一段表" in forecast.basis[0]
    assert "2025 年已发布招生参考" in report.target_summary
    assert "中考前只使用" in report.policy_summary
