from app.services.position_engine import CalibrationPoint
from app.services.position_fusion import PositionFusionEngine


def test_fuses_score_and_calibrated_rank_with_inverse_uncertainty_weights() -> None:
    engine = PositionFusionEngine({"rank_channel_min_samples": 2})
    score = engine.score_channel((8, 10), junior_school="测试初中", assessment_stage="一模")
    rank = engine.rank_channel(
        grade_rank=20,
        grade_size=200,
        candidate_count=50000,
        calibration_points=(
            CalibrationPoint(10, 100, 3000),
            CalibrationPoint(20, 100, 6000),
        ),
    )

    fused = engine.fuse(score, rank)

    assert score is not None and rank is not None
    assert fused.method == "dual_channel_fusion"
    assert fused.score_weight is not None and fused.rank_weight is not None
    assert fused.rank_weight > fused.score_weight
    assert fused.percentile_range is not None
    assert fused.percentile_range[0] < fused.center < fused.percentile_range[1]


def test_conflicting_channels_expand_range_instead_of_hiding_disagreement() -> None:
    engine = PositionFusionEngine({"fusion_conflict_threshold_pp": 3})
    score = engine.score_channel((3, 4), junior_school=None, assessment_stage="一模")
    rank = engine.rank_channel(
        grade_rank=40,
        grade_size=100,
        candidate_count=50000,
        calibration_points=(),
    )

    fused = engine.fuse(score, rank)

    assert fused.method == "dual_channel_conflict_review"
    assert fused.confidence == "low"
    assert fused.conflict_pp is not None and fused.conflict_pp > 3
    assert fused.percentile_range is not None
    assert fused.percentile_range[0] <= score.percentile_range[0]
    assert fused.percentile_range[1] >= rank.percentile_range[1]


def test_verified_school_difficulty_profile_is_required_before_adjustment() -> None:
    parameters = {
        "school_difficulty_profiles": {
            "测试初中|一模": {
                "verified": True,
                "sample_count": 24,
                "percentile_shift_pp": -2.5,
                "residual_uncertainty_pp": 1.0,
            }
        }
    }
    adjusted = PositionFusionEngine(parameters).score_channel((10, 12), junior_school="测试 初中", assessment_stage="一模")
    unverified = PositionFusionEngine({
        "school_difficulty_profiles": {"测试初中|一模": {"verified": False, "sample_count": 99, "percentile_shift_pp": -9}}
    }).score_channel((10, 12), junior_school="测试初中", assessment_stage="一模")

    assert adjusted is not None and adjusted.difficulty_applied
    assert adjusted.center == 8.5
    assert unverified is not None and not unverified.difficulty_applied
    assert unverified.center == 11
