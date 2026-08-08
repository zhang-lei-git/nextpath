from fastapi.testclient import TestClient
from uuid import uuid4

from app.core.config import settings
from app.main import app


def test_health() -> None:
    with TestClient(app) as client:
        response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_exam_creation_and_dashboard() -> None:
    headers = {"X-Demo-User": "test-family"}
    with TestClient(app) as client:
        profile = client.put(
            "/api/v1/profile",
            headers=headers,
            json={
                "student_name": "小远", "junior_school": "示例初中", "grade": "初三",
                "class_type_raw": "创新班", "class_type_standard": "创新",
                "target_school": "西安高新第一中学",
            },
        )
        created = client.post(
            "/api/v1/exams",
            headers=headers,
            json={
                "name": "测试月考",
                "exam_date": "2026-08-03",
                "total_score": 615,
                "class_rank": 28,
                "grade_rank": 28,
                "grade_size": 680,
                "exam_scope": "九年级总复习范围",
                "participant_scope": "年级",
                "participant_count": 680,
                "paper_version": "校内A卷",
                "scores": {"math": 96},
            },
        )
    dashboard = client.get("/api/v1/dashboard", headers=headers)
    reports = client.get("/api/v1/reports", headers=headers)
    assert profile.status_code == 200
    assert profile.json()["class_type_standard"] == "创新"
    assert created.status_code == 201
    assert dashboard.status_code == 200
    assert dashboard.json()["latest_exam"]["total_score"] == 615
    assert dashboard.json()["latest_exam"]["physical_score"] == 60
    assert dashboard.json()["latest_exam"]["grade_size"] == 680
    assert dashboard.json()["latest_exam"]["participant_scope"] == "年级"
    assert dashboard.json()["forecast"]["target_gap"] is None
    assert dashboard.json()["forecast"]["current_snapshot"]["title"] == "当前现状"
    assert dashboard.json()["forecast"]["reasonable_projection"]["title"] == "合理预测"
    assert reports.status_code == 200
    assert reports.json()
    detail = client.get(f"/api/v1/reports/{reports.json()[0]['id']}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["content"]["target"] == "西安高新第一中学"
    assert detail.json()["content"]["kpis"]
    unauthorized_detail = client.get(
        f"/api/v1/reports/{reports.json()[0]['id']}",
        headers={"X-Demo-User": "another-family"},
    )
    assert unauthorized_detail.status_code == 404
    html = client.get(f"/api/v1/reports/{reports.json()[0]['id']}/html", headers=headers)
    assert html.status_code == 200
    assert "升学分析报告" in html.text
    assert "当前现状" in html.text
    assert "合理预测" in html.text
    assert "政策提示" not in html.text
    assert "数据来源与可信度说明" not in html.text
    assert "已使用" not in html.text


def test_seven_mock_exams_generate_saved_reports_and_support_correction(monkeypatch) -> None:
    monkeypatch.setattr(settings, "report_signing_secret", "report-test-secret")
    headers = {"X-Demo-User": f"seven-exam-family-{uuid4().hex}"}
    score_rows = {"chinese": 112, "math": 118, "english": 115, "physics": 78, "history": 60, "politics": 57, "pe": 60}
    with TestClient(app) as client:
        assert client.put(
            "/api/v1/profile",
            headers=headers,
            json={"student_name": "小航", "junior_school": "示例初中", "grade": "初三", "target_school": "西安高新第一中学"},
        ).status_code == 200
        exam_ids = []
        for year, month, score, rank in ((2025, 9, 586, 240), (2025, 10, 590, 216), (2025, 11, 593, 196), (2025, 12, 596, 176), (2026, 1, 600, 152), (2026, 3, 604, 130), (2026, 4, 608, 108)):
            payload = {
                "name": f"{month}月模考",
                "exam_date": f"{year}-{month:02d}-15",
                "total_score": score,
                "grade_rank": rank,
                "grade_size": 680,
                "scores": score_rows,
            }
            response = client.post("/api/v1/exams", headers=headers, json=payload)
            assert response.status_code == 201, response.text
            exam_ids.append(response.json()["id"])
        reports = client.get("/api/v1/reports", headers=headers)
        assert reports.status_code == 200
        assert len([item for item in reports.json() if item["report_type"] == "exam"]) == 7
        assert len([item for item in reports.json() if item["report_type"] == "monthly"]) == 7
        corrected = client.put(
            f"/api/v1/exams/{exam_ids[0]}",
            headers=headers,
            json={
                "name": "9月模考（已核对）", "exam_date": "2025-09-15", "total_score": 588,
                "grade_rank": 230, "grade_size": 680, "scores": score_rows,
            },
        )
        assert corrected.status_code == 200
        updated_reports = client.get("/api/v1/reports", headers=headers)
        assert len([item for item in updated_reports.json() if item["report_type"] == "exam"]) == 8
        monthly = [item for item in updated_reports.json() if item["report_type"] == "monthly"]
        assert len(monthly) == 7
        assert sum(item["period_key"] == "2025-09" for item in monthly) == 1
        report_id = updated_reports.json()[0]["id"]
        unsigned = client.get(f"/api/v1/reports/published/{report_id}")
        assert unsigned.status_code == 422
        access = client.post(f"/api/v1/reports/{report_id}/access", headers=headers)
        assert access.status_code == 200
        denied = client.post(
            f"/api/v1/reports/{report_id}/access",
            headers={"X-Demo-User": f"other-family-{uuid4().hex}"},
        )
        assert denied.status_code == 404
        published = client.get(access.json()["url"])
        assert published.status_code == 200
        assert "历次模考成绩与位置变化" in published.text
        assert client.get(access.json()["url"] + "x").status_code == 401


def test_analysis_records_missing_data_as_idempotent_gap(monkeypatch) -> None:
    monkeypatch.setattr(settings, "data_admin_key", "analysis-gap-test-key")
    owner = f"gap-family-{uuid4().hex}"
    target = f"待补边界高中-{uuid4().hex}"
    family_headers = {"X-Demo-User": owner}
    admin_headers = {"X-Data-Admin-Key": "analysis-gap-test-key"}
    with TestClient(app) as client:
        assert client.put(
            "/api/v1/profile",
            headers=family_headers,
            json={
                "student_name": "小策",
                "junior_school": "待补映射初中",
                "grade": "初三",
                "class_type_standard": "未知",
                "target_school": target,
            },
        ).status_code == 200
        assert client.post(
            "/api/v1/exams",
            headers=family_headers,
            json={
                "name": "一模",
                "exam_date": "2026-03-20",
                "total_score": 520,
                "grade_rank": 180,
                "grade_size": 900,
            },
        ).status_code == 201
        assert client.get("/api/v1/dashboard", headers=family_headers).status_code == 200
        assert client.get("/api/v1/dashboard", headers=family_headers).status_code == 200
        gaps = client.get(
            "/api/v1/data/gaps", headers=admin_headers, params={"status": "open"}
        )
        assert gaps.status_code == 200
        target_gap = next(
            item for item in gaps.json()
            if item["gap_type"] == "school_boundary"
            and item["details"].get("target_school") == target
        )
        assert target_gap["affected_users"] == 1
