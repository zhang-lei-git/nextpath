from fastapi.testclient import TestClient

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
    assert profile.status_code == 200
    assert created.status_code == 201
    assert dashboard.status_code == 200
    assert dashboard.json()["latest_exam"]["total_score"] == 615
    assert dashboard.json()["latest_exam"]["grade_size"] == 680
    assert dashboard.json()["forecast"]["target_gap"] == 0
