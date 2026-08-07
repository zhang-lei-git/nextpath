from datetime import date

from app.services.prediction import BaselinePredictionEngine, PredictionInput
from app.services.published_reference_data import PublishedReferenceData, PublishedSchoolReference
from app.services.position_engine import CalibrationPoint


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
        PredictionInput(
            total_score=520,
            total_full_mark=580,
            class_rank=28,
            grade_rank=28,
            grade_size=680,
            target_school="测试高中",
            analysis_year=2026,
            analysis_date=date(2026, 3, 15),
        )
    )

    assert forecast.current_percentile is not None
    assert forecast.target_percentile is not None
    assert forecast.target_gap is None
    assert forecast.model_version == "historical-preexam-2026.5"
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
        total_score=520, total_full_mark=580, physical_score=54, class_rank=None,
        target_school="测试高中", analysis_year=2026, analysis_date=date(2026, 3, 15),
    )

    forecast = engine.predict(prediction_input)
    report = engine.build_report(prediction_input)

    assert forecast.reference_year == 2025
    assert forecast.projected_total_range == (574, 574)
    assert forecast.historical_equivalent_score_range is not None
    assert forecast.score_bridge_method == "subject_bridge_rate_projection"
    assert forecast.current_percentile is not None
    assert forecast.position_method == "score_only"
    assert "score" in forecast.position_channels
    assert "2025 年已发布一分一段表" in forecast.basis[0]
    assert "2025 年已发布招生参考" in report.target_summary
    assert "中考前只使用" in report.policy_summary


def test_rank_validation_does_not_move_parent_projection_without_a_score_change() -> None:
    reference_data = PublishedReferenceData(
        reference_year=2025,
        rank_source="2025 年一分一段表",
        rank_points=((820, 1), (780, 2000), (700, 15000), (610, 49900)),
        rank_full_mark=820,
        candidate_count=49900,
    )
    engine = BaselinePredictionEngine(
        reference_data,
        position_parameters={"rank_channel_min_samples": 2},
        calibration_points=(
            CalibrationPoint(10, 100, 3000, 50000),
            CalibrationPoint(20, 100, 6000, 50000),
        ),
    )

    forecast = engine.predict(PredictionInput(
        total_score=520,
        total_full_mark=580,
        physical_score=54,
        class_rank=None,
        grade_rank=20,
        grade_size=100,
        target_school=None,
        junior_school="测试初中",
        assessment_stage="一模",
        analysis_year=2026,
        analysis_date=date(2026, 3, 15),
    ))

    without_rank = engine.predict(PredictionInput(
        total_score=520,
        total_full_mark=580,
        physical_score=54,
        class_rank=None,
        target_school=None,
        junior_school="测试初中",
        assessment_stage="一模",
        analysis_year=2026,
        analysis_date=date(2026, 3, 15),
    ))

    assert forecast.position_method == "score_only"
    assert set(forecast.position_channels) == {"score", "rank"}
    assert forecast.position_channels["rank"]["sample_count"] == 2
    assert forecast.position_conflict_pp is None
    assert forecast.reasonable_projection is not None
    assert without_rank.reasonable_projection is not None
    assert forecast.reasonable_projection.current_percentile == without_rank.reasonable_projection.current_percentile


def test_missing_physical_score_defaults_to_full_mark_for_position_calculation() -> None:
    forecast = BaselinePredictionEngine().predict(PredictionInput(
        total_score=520,
        total_full_mark=580,
        class_rank=None,
        target_school=None,
    ))

    assert forecast.projected_total_range == (580, 580)
    assert "满分 60 分" in forecast.basis[1]


def test_two_parent_facing_scenarios_keep_current_and_projected_results_separate() -> None:
    forecast = BaselinePredictionEngine().predict(PredictionInput(
        total_score=520,
        total_full_mark=640,
        class_rank=None,
        target_school=None,
        analysis_year=2026,
        score_history=((480, 640, 2026), (520, 640, 2026)),
    ))

    assert forecast.current_snapshot is not None
    assert forecast.reasonable_projection is not None
    assert forecast.current_snapshot.total_range == (580, 580)
    assert forecast.current_snapshot.total_full_mark == 640
    assert forecast.reasonable_projection.total_range == (594, 614)
    assert forecast.reasonable_projection.summary.startswith("已结合历次成绩变化")
