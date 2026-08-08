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
    assert forecast.prediction_level == "basic"
    assert forecast.current_percentile is not None
    assert forecast.position_method == "score_only"
    assert "score" in forecast.position_channels
    assert "2025 年已发布一分一段表" in forecast.basis[0]
    assert "历史录取位置" in report.target_summary
    assert "2025 年已发布招生参考" in report.data_sources
    assert "中考前只使用" in report.policy_summary


def test_rank_validation_moves_score_and_position_through_the_same_curve() -> None:
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
        class_type_standard="重点",
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

    assert forecast.position_method == "dual_channel_fusion"
    assert set(forecast.position_channels) == {"score", "rank"}
    assert forecast.position_channels["rank"]["sample_count"] == 2
    assert forecast.position_conflict_pp is not None
    assert forecast.reasonable_projection is not None
    assert without_rank.reasonable_projection is not None
    assert forecast.reasonable_projection.current_percentile != without_rank.reasonable_projection.current_percentile
    assert forecast.reasonable_projection.total_range != without_rank.reasonable_projection.total_range


def test_remaining_time_limits_projection_change() -> None:
    engine = BaselinePredictionEngine()
    common = dict(
        total_score=500,
        total_full_mark=580,
        class_rank=None,
        target_school=None,
        analysis_year=2026,
        score_history=((450, 580, 2026), (500, 580, 2026)),
    )

    early = engine.predict(PredictionInput(**common, analysis_date=date(2026, 3, 20)))
    late = engine.predict(PredictionInput(**common, analysis_date=date(2026, 6, 18)))

    assert early.reasonable_projection is not None
    assert late.reasonable_projection is not None
    early_range = early.reasonable_projection.total_range
    late_range = late.reasonable_projection.total_range
    assert early_range is not None and late_range is not None
    assert late_range[1] - late_range[0] < early_range[1] - early_range[0]
    assert late_range[1] < early_range[1]


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
    assert forecast.reasonable_projection.total_range == (584, 624)
    assert forecast.reasonable_projection.summary.startswith("已结合历次成绩变化")


def test_target_comparison_keeps_rank_gap_as_a_range() -> None:
    reference_data = PublishedReferenceData(
        reference_year=2025,
        rank_source="2025 年一分一段表",
        rank_points=((820, 1), (780, 2000), (700, 15000), (610, 49900)),
        rank_full_mark=820,
        candidate_count=49900,
        school_references=(PublishedSchoolReference("测试高中", 700, "历史录取参考"),),
    )
    forecast = BaselinePredictionEngine(reference_data).predict(PredictionInput(
        total_score=520,
        total_full_mark=580,
        class_rank=None,
        grade_rank=28,
        grade_size=680,
        junior_school="测试初中",
        class_type_standard="重点",
        target_school="测试高中",
        analysis_year=2026,
        analysis_date=date(2026, 3, 15),
    ))

    assert forecast.prediction_level == "complete"
    assert forecast.target_comparison is not None
    assert forecast.target_comparison.current_gap_rank_range is not None
    assert forecast.target_comparison.projected_gap_rank_range is None
    assert forecast.current_snapshot is not None
    assert forecast.current_snapshot.range_usable is True


def test_multiple_school_observations_create_boundary_and_tiers() -> None:
    references = tuple(
        PublishedSchoolReference(
            "测试高中",
            score,
            f"{year} 年录取参考",
            reference_year=year,
            rank=rank,
            candidate_count=50000,
            plan=520 if year == 2025 else None,
            previous_year_plan=500 if year == 2025 else None,
        )
        for year, score, rank in ((2025, 700, 10000), (2024, 695, 10500), (2023, 705, 9600))
    ) + (
        PublishedSchoolReference("保底高中", 650, "2025 年录取参考", reference_year=2025, rank=22000, candidate_count=50000),
    )
    reference_data = PublishedReferenceData(
        reference_year=2025,
        rank_source="2025 年一分一段表",
        rank_points=((820, 1), (780, 2000), (700, 10000), (650, 22000), (610, 49900)),
        rank_full_mark=820,
        candidate_count=50000,
        school_references=references,
    )
    forecast = BaselinePredictionEngine(reference_data).predict(PredictionInput(
        total_score=510,
        total_full_mark=580,
        class_rank=None,
        grade_rank=150,
        grade_size=1000,
        junior_school="测试初中",
        class_type_standard="重点",
        target_school="测试高中",
        analysis_year=2026,
        analysis_date=date(2026, 3, 20),
    ))

    assert forecast.target_comparison is not None
    assert forecast.target_comparison.school_rank_range[0] < forecast.target_comparison.school_rank_range[1]
    assert "保底高中" in forecast.school_tiers["safe"] or "保底高中" in forecast.school_tiers["match"]
    assert all(len(items) <= 5 for items in forecast.school_tiers.values())


def test_basic_or_overwide_prediction_does_not_list_specific_schools() -> None:
    reference_data = PublishedReferenceData(
        reference_year=2025,
        rank_source="2025 年一分一段表",
        rank_points=((820, 1), (780, 2000), (700, 15000), (610, 49900)),
        rank_full_mark=820,
        candidate_count=49900,
        school_references=(PublishedSchoolReference("测试高中", 700, "历史录取参考"),),
    )
    forecast = BaselinePredictionEngine(reference_data).predict(PredictionInput(
        total_score=520,
        total_full_mark=580,
        class_rank=None,
        target_school="测试高中",
        analysis_year=2026,
        analysis_date=date(2026, 3, 15),
    ))

    assert forecast.prediction_level == "basic"
    assert forecast.reasonable_projection is not None
    assert forecast.school_tiers == {"reach": [], "match": [], "safe": []}


def test_rank_history_changes_the_joint_projection() -> None:
    reference_data = PublishedReferenceData(
        reference_year=2025,
        rank_source="2025 年一分一段表",
        rank_points=((820, 1), (780, 2000), (700, 15000), (610, 49900)),
        rank_full_mark=820,
        candidate_count=49900,
    )
    engine = BaselinePredictionEngine(reference_data)
    common = dict(
        total_score=500,
        total_full_mark=580,
        physical_score=60,
        class_rank=None,
        grade_rank=100,
        grade_size=1000,
        target_school=None,
        junior_school="测试初中",
        class_type_standard="平行",
        assessment_stage="一模",
        analysis_year=2026,
        analysis_date=date(2026, 3, 20),
        score_history=((480, 580, 2026), (500, 580, 2026)),
    )

    improving = engine.predict(PredictionInput(**common, rank_history=((180, 1000), (140, 1000), (100, 1000))))
    flat = engine.predict(PredictionInput(**common, rank_history=((100, 1000), (100, 1000))))

    assert improving.reasonable_projection is not None
    assert flat.reasonable_projection is not None
    assert improving.reasonable_projection.current_percentile < flat.reasonable_projection.current_percentile
    assert improving.reasonable_projection.total_range[0] > flat.reasonable_projection.total_range[0]
