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
