from app.services.ocr_service import parse_score_text


def test_parse_score_text_keeps_parent_confirmation_fields() -> None:
    result = parse_score_text(
        "初三一模考试\n语文：102 数学:110 英语 108\n物理：68 道法：70 历史：54\n年级第120名 年级共680人 班级第8名"
    )
    assert result["name"] == "初三一模考试"
    assert result["scores"]["pe"] == 60
    assert result["total_score"] == 572
    assert result["grade_rank"] == 120
    assert result["grade_size"] == 680
    assert result["class_rank"] == 8


def test_mobile_score_card_with_values_before_labels() -> None:
    result = parse_score_text(
        "详情页 D4 2026届D4班 考试时间：2026-03-10 详情 模考一 "
        "学生的成绩单 30 430.5 班级排名 总分 班级 D4班 1 排名 平均分 最高分 "
        "语文 89.50 数学 94.00 英语 98.00 物理 59.00 道法 59.00 历史 31.00 家长签字"
    )
    assert result["name"] == "模考一"
    assert str(result["exam_date"]) == "2026-03-10"
    assert result["class_rank"] == 30
    assert result["total_score"] == 490.5
    assert result["grade_rank"] is None
