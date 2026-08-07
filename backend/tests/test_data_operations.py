from uuid import uuid4

import httpx
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.services.data_service import DataService


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


def test_non_production_and_future_releases_are_not_consumable(monkeypatch) -> None:
    monkeypatch.setattr(settings, "data_admin_key", "data-boundary-test-key")
    headers = {"X-Data-Admin-Key": "data-boundary-test-key"}
    region = f"数据边界测试区-{uuid4().hex}"
    year = 2028

    with TestClient(app) as client:
        fact = client.post(
            "/api/v1/data/facts",
            headers=headers,
            json={
                "fact_type": "policy",
                "entity_name": "测试政策",
                "field": "中招政策摘要",
                "region": region,
                "reference_year": year,
                "value": {"summary": "只用于边界测试"},
                "confidence": "official",
            },
        )
        assert fact.status_code == 201
        fact_id = fact.json()["id"]
        assert client.post(
            f"/api/v1/data/facts/{fact_id}/review",
            headers=headers,
            json={"decision": "approved"},
        ).status_code == 200

        invalid = client.post(
            "/api/v1/data/releases",
            headers=headers,
            json={
                "name": "错误的测试预测版本",
                "region": region,
                "reference_year": year,
                "fact_ids": [fact_id],
                "environment": "test",
                "data_purpose": "demo_or_backtest",
                "usable_for_prediction": True,
            },
        )
        assert invalid.status_code == 422

        test_release = client.post(
            "/api/v1/data/releases",
            headers=headers,
            json={
                "name": "测试不可预测版本",
                "region": region,
                "reference_year": year,
                "fact_ids": [fact_id],
                "environment": "test",
                "data_purpose": "demo_or_backtest",
                "usable_for_prediction": False,
            },
        )
        assert test_release.status_code == 201
        assert test_release.json()["usable_for_prediction"] is False

        unavailable = client.get(
            "/api/v1/data/consumer/policies",
            params={"region": region, "reference_year": year},
        )
        assert unavailable.status_code == 200
        assert unavailable.json()["facts"] == []

        future_release = client.post(
            "/api/v1/data/releases",
            headers=headers,
            json={
                "name": "尚未生效的生产版本",
                "region": region,
                "reference_year": year,
                "fact_ids": [fact_id],
                "environment": "production",
                "data_purpose": "forecast",
                "usable_for_prediction": True,
                "valid_from": "2099-01-01T00:00:00Z",
            },
        )
        assert future_release.status_code == 201

        still_unavailable = client.get(
            "/api/v1/data/consumer/policies",
            params={"region": region, "reference_year": year},
        )
        assert still_unavailable.status_code == 200
        assert still_unavailable.json()["facts"] == []


def test_collection_run_detects_changes_and_exposes_step_logs(monkeypatch) -> None:
    monkeypatch.setattr(settings, "data_admin_key", "collection-run-test-key")
    monkeypatch.setattr(DataService, "_validate_collect_url", staticmethod(lambda _: None))
    original_client = httpx.AsyncClient

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("plan.pdf"):
            return httpx.Response(
                200,
                headers={"content-type": "application/pdf"},
                content=b"%PDF-1.4 test attachment",
            )
        return httpx.Response(
            200,
            headers={"content-type": "text/html; charset=utf-8"},
            text='<html><body><h1>2028 年招生计划</h1><p>学校志愿规则已发布。</p><a href="/plan.pdf">附件</a></body></html>',
        )

    def mock_client(*_, **__) -> httpx.AsyncClient:
        return original_client(transport=httpx.MockTransport(handler))

    monkeypatch.setattr("app.services.data_service.httpx.AsyncClient", mock_client)
    headers = {"X-Data-Admin-Key": "collection-run-test-key"}
    with TestClient(app) as client:
        job = client.post(
            "/api/v1/data/collection-jobs",
            headers=headers,
            json={
                "name": "教育局招生计划",
                "target_url": "https://example.com/admission",
                "region": "西安",
                "data_type": "admission",
                "interval_minutes": 60,
            },
        )
        assert job.status_code == 201, job.text

        paused = client.patch(
            f"/api/v1/data/collection-jobs/{job.json()['id']}",
            headers=headers,
            json={"is_active": False, "owner": "数据运营"},
        )
        assert paused.status_code == 200
        assert paused.json()["is_active"] is False
        assert paused.json()["owner"] == "数据运营"
        assert client.patch(
            f"/api/v1/data/collection-jobs/{job.json()['id']}",
            headers=headers,
            json={"is_active": True},
        ).status_code == 200

        first = client.post(f"/api/v1/data/collection-jobs/{job.json()['id']}/run", headers=headers)
        assert first.status_code == 200, first.text
        assert first.json()["status"] == "extracted"

        runs = client.get(
            "/api/v1/data/collection-runs",
            headers=headers,
            params={"job_id": job.json()["id"]},
        )
        assert runs.status_code == 200
        assert runs.json()[0]["status"] == "pending_review"
        detail = client.get(f"/api/v1/data/collection-runs/{runs.json()[0]['id']}", headers=headers)
        assert detail.status_code == 200
        assert detail.json()["snapshots"][0]["change_type"] == "new"
        assert detail.json()["snapshots"][0]["attachment_hash"]
        assert len(detail.json()["snapshots"][0]["diff_summary"]["attachments"]) == 1
        assert [item["step_name"] for item in detail.json()["steps"]] == ["capture", "extract", "normalize"]

        candidates = client.get(
            "/api/v1/data/facts",
            headers=headers,
            params={"status": "pending_review"},
        )
        assert any(item["scope"].get("collection_job_id") == job.json()["id"] for item in candidates.json())

        second = client.post(f"/api/v1/data/collection-jobs/{job.json()['id']}/run", headers=headers)
        assert second.status_code == 200
        assert second.json()["status"] == "unchanged"
        latest_runs = client.get(
            "/api/v1/data/collection-runs",
            headers=headers,
            params={"job_id": job.json()["id"]},
        ).json()
        assert latest_runs[0]["status"] == "unchanged"
        unchanged_detail = client.get(
            f"/api/v1/data/collection-runs/{latest_runs[0]['id']}", headers=headers
        ).json()
        assert unchanged_detail["snapshots"][0]["change_type"] == "unchanged"
        assert [item["step_name"] for item in unchanged_detail["steps"]] == ["capture"]

        before_reprocess = [
            item for item in candidates.json()
            if item["scope"].get("collection_job_id") == job.json()["id"]
        ]
        reprocessed = client.post(
            f"/api/v1/data/collection-runs/{runs.json()[0]['id']}/reprocess",
            headers=headers,
            json={},
        )
        assert reprocessed.status_code == 200, reprocessed.text
        after_reprocess = [
            item for item in client.get(
                "/api/v1/data/facts", headers=headers, params={"status": "pending_review"}
            ).json()
            if item["scope"].get("collection_job_id") == job.json()["id"]
        ]
        assert len(after_reprocess) == len(before_reprocess)
        reprocess_run = client.get(
            "/api/v1/data/collection-runs",
            headers=headers,
            params={"job_id": job.json()["id"]},
        ).json()[0]
        assert reprocess_run["trigger_type"] == "reprocess"
        assert reprocess_run["status"] == "normalized"


def test_failed_collection_run_can_retry_within_limit(monkeypatch) -> None:
    monkeypatch.setattr(settings, "data_admin_key", "collection-retry-test-key")
    monkeypatch.setattr(DataService, "_validate_collect_url", staticmethod(lambda _: None))
    original_client = httpx.AsyncClient
    should_fail = {"value": True}

    def handler(_: httpx.Request) -> httpx.Response:
        if should_fail["value"]:
            return httpx.Response(503, text="temporarily unavailable")
        return httpx.Response(
            200,
            headers={"content-type": "text/html; charset=utf-8"},
            text="<html><body><h1>2029 年中招政策</h1><p>志愿填报规则。</p></body></html>",
        )

    def mock_client(*_, **__) -> httpx.AsyncClient:
        return original_client(transport=httpx.MockTransport(handler))

    monkeypatch.setattr("app.services.data_service.httpx.AsyncClient", mock_client)
    headers = {"X-Data-Admin-Key": "collection-retry-test-key"}
    with TestClient(app) as client:
        job = client.post(
            "/api/v1/data/collection-jobs",
            headers=headers,
            json={
                "name": f"失败重试-{uuid4().hex}",
                "target_url": "https://example.com/policy",
                "region": "西安",
                "data_type": "policy",
                "max_retries": 1,
            },
        )
        assert job.status_code == 201
        failed = client.post(
            f"/api/v1/data/collection-jobs/{job.json()['id']}/run", headers=headers
        )
        assert failed.status_code == 422
        failed_run = client.get(
            "/api/v1/data/collection-runs",
            headers=headers,
            params={"job_id": job.json()["id"], "status": "failed"},
        ).json()[0]
        assert failed_run["attempt"] == 1

        should_fail["value"] = False
        retried = client.post(
            f"/api/v1/data/collection-runs/{failed_run['id']}/retry", headers=headers
        )
        assert retried.status_code == 200, retried.text
        latest = client.get(
            "/api/v1/data/collection-runs",
            headers=headers,
            params={"job_id": job.json()["id"]},
        ).json()[0]
        assert latest["trigger_type"] == "retry"
        assert latest["attempt"] == 2
        assert client.post(
            f"/api/v1/data/collection-runs/{latest['id']}/retry", headers=headers
        ).status_code == 409


def test_governance_rules_detect_conflicts_and_expose_text_changes(monkeypatch) -> None:
    monkeypatch.setattr(settings, "data_admin_key", "governance-workbench-test-key")
    monkeypatch.setattr(DataService, "_validate_collect_url", staticmethod(lambda _: None))
    original_client = httpx.AsyncClient
    page = {
        "text": "<html><body><h1>2030 年招生计划</h1><p>计划招收 600 人。</p></body></html>"
    }

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-type": "text/html; charset=utf-8"},
            text=page["text"],
        )

    def mock_client(*_, **__) -> httpx.AsyncClient:
        return original_client(transport=httpx.MockTransport(handler))

    monkeypatch.setattr("app.services.data_service.httpx.AsyncClient", mock_client)
    headers = {"X-Data-Admin-Key": "governance-workbench-test-key"}
    suffix = uuid4().hex
    version = f"admission-{suffix}"
    job_name = f"招生采集-{suffix}"
    canonical_name = f"标准学校-{suffix}"

    with TestClient(app) as client:
        rule = client.post(
            "/api/v1/data/governance-rules",
            headers=headers,
            json={
                "name": "招生数据标准化",
                "version": version,
                "rules": {
                    "field_aliases": {"招生计划": "招生名额"},
                    "entity_aliases": {job_name: canonical_name},
                    "allowed_fact_types": ["admission"],
                },
            },
        )
        assert rule.status_code == 201, rule.text
        assert client.post(
            "/api/v1/data/governance-rules",
            headers=headers,
            json={"name": "重复版本", "version": version, "rules": {}},
        ).status_code == 409
        assert any(
            item["version"] == version
            for item in client.get("/api/v1/data/governance-rules", headers=headers).json()
        )

        existing = client.post(
            "/api/v1/data/facts",
            headers=headers,
            json={
                "fact_type": "admission",
                "entity_name": canonical_name,
                "field": "招生名额",
                "region": "西安",
                "reference_year": 2030,
                "value": {"count": 580},
                "confidence": "official",
            },
        )
        assert existing.status_code == 201
        assert client.post(
            f"/api/v1/data/facts/{existing.json()['id']}/review",
            headers=headers,
            json={"decision": "approved"},
        ).status_code == 200

        invalid_job = client.post(
            "/api/v1/data/collection-jobs",
            headers=headers,
            json={
                "name": "无效规则任务",
                "target_url": "https://example.com/invalid",
                "governance_rule_version": f"missing-{suffix}",
            },
        )
        assert invalid_job.status_code == 422

        job = client.post(
            "/api/v1/data/collection-jobs",
            headers=headers,
            json={
                "name": job_name,
                "target_url": "https://example.com/admission",
                "region": "西安",
                "data_type": "admission",
                "governance_rule_version": version,
            },
        )
        assert job.status_code == 201, job.text
        first = client.post(
            f"/api/v1/data/collection-jobs/{job.json()['id']}/run", headers=headers
        )
        assert first.status_code == 200, first.text

        facts = client.get(
            "/api/v1/data/facts", headers=headers, params={"status": "pending_review"}
        ).json()
        candidate = next(
            item for item in facts
            if item["scope"].get("collection_job_id") == job.json()["id"]
            and item["field"] == "招生名额"
        )
        assert candidate["entity_name"] == canonical_name
        assert candidate["scope"]["conflict_fact_ids"] == [existing.json()["id"]]

        alerts = client.get(
            "/api/v1/data/alerts", headers=headers, params={"status": "open"}
        )
        assert alerts.status_code == 200
        alert = next(
            item for item in alerts.json()
            if item["details"].get("candidate_fact_id") == candidate["id"]
        )
        assert alert["severity"] == "high"
        resolved = client.patch(
            f"/api/v1/data/alerts/{alert['id']}",
            headers=headers,
            json={"status": "resolved"},
        )
        assert resolved.status_code == 200
        assert resolved.json()["resolved_at"]

        page["text"] = (
            "<html><body><h1>2030 年招生计划</h1>"
            "<p>计划调整为招收 620 人。</p><p>新增定向生说明。</p></body></html>"
        )
        second = client.post(
            f"/api/v1/data/collection-jobs/{job.json()['id']}/run", headers=headers
        )
        assert second.status_code == 200, second.text
        latest_run = client.get(
            "/api/v1/data/collection-runs",
            headers=headers,
            params={"job_id": job.json()["id"]},
        ).json()[0]
        detail = client.get(
            f"/api/v1/data/collection-runs/{latest_run['id']}", headers=headers
        ).json()
        text_diff = detail["snapshots"][0]["diff_summary"]["text_diff"]
        assert text_diff["similarity"] < 1
        assert text_diff["added_count"] > 0
        assert text_diff["removed_count"] > 0
