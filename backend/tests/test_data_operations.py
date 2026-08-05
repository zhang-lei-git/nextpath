from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app


def test_only_reviewed_and_released_facts_are_consumable(monkeypatch) -> None:
    monkeypatch.setattr(settings, "data_admin_key", "data-ops-test-key")
    headers = {"X-Data-Admin-Key": "data-ops-test-key"}
    region = f"数据治理测试区-{uuid4().hex}"
    year = 2027

    with TestClient(app) as client:
        source = client.post(
            "/api/v1/data/sources",
            headers=headers,
            json={
                "name": "测试教育主管部门",
                "source_type": "official",
                "reliability": "official",
                "homepage_url": "https://example.invalid/education",
            },
        )
        assert source.status_code == 201

        sources = client.get("/api/v1/data/sources", headers=headers)
        assert sources.status_code == 200
        assert any(item["id"] == source.json()["id"] for item in sources.json())

        evidence = client.post(
            "/api/v1/data/evidence",
            headers=headers,
            json={
                "source_id": source.json()["id"],
                "title": "2027 年招生计划通知",
                "url": "https://example.invalid/plan-2027",
                "excerpt": "西安高新第一中学统招计划 800 人。",
            },
        )
        assert evidence.status_code == 201

        evidence_list = client.get("/api/v1/data/evidence", headers=headers)
        assert evidence_list.status_code == 200
        assert any(item["id"] == evidence.json()["id"] for item in evidence_list.json())

        fact = client.post(
            "/api/v1/data/facts",
            headers=headers,
            json={
                "fact_type": "admission",
                "entity_name": "西安高新第一中学",
                "field": "统招计划",
                "region": region,
                "reference_year": year,
                "scope": {"batch": "第一批次"},
                "value": {"count": 800, "unit": "人"},
                "evidence_ids": [evidence.json()["id"]],
                "confidence": "official",
            },
        )
        assert fact.status_code == 201
        fact_id = fact.json()["id"]
        assert fact.json()["status"] == "pending_review"

        before_release = client.get(
            "/api/v1/data/consumer/admissions",
            params={"region": region, "reference_year": year},
        )
        assert before_release.status_code == 200
        assert before_release.json()["facts"] == []

        rejected_release = client.post(
            "/api/v1/data/releases",
            headers=headers,
            json={
                "name": "2027 招录数据初版",
                "region": region,
                "reference_year": year,
                "fact_ids": [fact_id],
            },
        )
        assert rejected_release.status_code == 422

        reviewed = client.post(
            f"/api/v1/data/facts/{fact_id}/review",
            headers=headers,
            json={"decision": "approved", "note": "已核对官方通知"},
        )
        assert reviewed.status_code == 200
        assert reviewed.json()["status"] == "approved"

        release = client.post(
            "/api/v1/data/releases",
            headers=headers,
            json={
                "name": "2027 招录数据初版",
                "region": region,
                "reference_year": year,
                "fact_ids": [fact_id],
            },
        )
        assert release.status_code == 201
        assert release.json()["fact_count"] == 1

        releases = client.get("/api/v1/data/releases", headers=headers)
        assert releases.status_code == 200
        assert any(item["id"] == release.json()["id"] for item in releases.json())

        consumed = client.get(
            "/api/v1/data/consumer/admissions",
            params={"region": region, "reference_year": year},
        )
    assert consumed.status_code == 200
    assert consumed.json()["facts"][0]["value"]["count"] == 800
    assert consumed.json()["facts"][0]["evidence"][0]["source_type"] == "official"


def test_document_ingestion_creates_traceable_evidence(monkeypatch) -> None:
    monkeypatch.setattr(settings, "data_admin_key", "data-ingestion-test-key")
    headers = {"X-Data-Admin-Key": "data-ingestion-test-key"}
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/data/ingestions/documents",
            headers=headers,
            data={"title": "招生计划整理"},
            files={"file": ("招生计划.txt", "2026 年普通高中招生计划。包含招生计划和志愿规则。", "text/plain")},
        )
        assert response.status_code == 201, response.text
        ingestion = response.json()
        assert ingestion["status"] == "extracted"
        assert ingestion["evidence_id"]
        assert "招生计划" in ingestion["extraction_text"]
        assert ingestion["suggested_facts"]

        evidence = client.get("/api/v1/data/evidence", headers=headers)
        assert any(item["id"] == ingestion["evidence_id"] for item in evidence.json())
