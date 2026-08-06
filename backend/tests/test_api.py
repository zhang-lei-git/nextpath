from fastapi.testclient import TestClient
from uuid import uuid4

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
            json={"student_name": "小远", "junior_school": "示例初中", "grade": "初三", "target_school": "西安高新第一中学"},
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
                "scores": {"math": 96},
            },
        )
    dashboard = client.get("/api/v1/dashboard", headers=headers)
    reports = client.get("/api/v1/reports", headers=headers)
    assert profile.status_code == 200
    assert created.status_code == 201
    assert dashboard.status_code == 200
    assert dashboard.json()["latest_exam"]["total_score"] == 615
    assert dashboard.json()["latest_exam"]["grade_size"] == 680
    assert dashboard.json()["forecast"]["target_gap"] is None
    assert reports.status_code == 200
    assert reports.json()
    html = client.get(f"/api/v1/reports/{reports.json()[0]['id']}/html", headers=headers)
    assert html.status_code == 200
    assert "升学分析报告" in html.text


def test_seven_mock_exams_generate_saved_reports_and_support_correction() -> None:
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
        assert len(reports.json()) == 7
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
        assert len(updated_reports.json()) == 8
        published = client.get(f"/api/v1/reports/published/{updated_reports.json()[0]['id']}")
        assert published.status_code == 200
        assert "历次模考成绩与位置变化" in published.text
