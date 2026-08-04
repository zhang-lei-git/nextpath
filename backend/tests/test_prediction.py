from app.services.prediction import BaselinePredictionEngine, PredictionInput


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
