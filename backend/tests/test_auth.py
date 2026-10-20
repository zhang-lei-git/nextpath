import httpx
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app


def test_wechat_login_issues_family_token(monkeypatch) -> None:
    monkeypatch.setattr(settings, "wechat_app_id", "wx-test")
    monkeypatch.setattr(settings, "wechat_app_secret", "secret")
    monkeypatch.setattr(settings, "auth_signing_secret", "auth-test-secret")
    monkeypatch.setattr(settings, "allow_demo_identity", True)
    original_client = httpx.AsyncClient

    def mock_client(*_, **__) -> httpx.AsyncClient:
        return original_client(transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json={"openid": "family-openid", "session_key": "unused"})
        ))

    monkeypatch.setattr(httpx, "AsyncClient", mock_client)
    with TestClient(app) as client:
        legacy_owner = "internal-auth-migration-test"
        legacy_profile = client.put(
            "/api/v1/profile",
            headers={"X-Demo-User": legacy_owner},
            json={"student_name": "小迁", "junior_school": "迁移测试初中", "grade": "初三"},
        )
        assert legacy_profile.status_code == 200
        # Legacy migration is only supported in an explicitly enabled development environment.
        login = client.post(
            "/api/v1/auth/wechat",
            json={"code": "temporary-code", "legacy_owner_id": legacy_owner},
        )
        assert login.status_code == 200
        token = login.json()["access_token"]
        profile = client.get("/api/v1/profile", headers={"Authorization": f"Bearer {token}"})
        assert profile.status_code == 200
        assert profile.json()["student_name"] == "小迁"


def test_family_api_rejects_missing_identity_when_demo_mode_is_disabled(monkeypatch) -> None:
    monkeypatch.setattr(settings, "allow_demo_identity", False)
    with TestClient(app) as client:
        response = client.get("/api/v1/profile")
    assert response.status_code == 401


def test_production_login_cannot_claim_legacy_profile(monkeypatch) -> None:
    from uuid import uuid4
    from app.core.tokens import issue_token
    monkeypatch.setattr(settings, "wechat_app_id", "wx-test")
    monkeypatch.setattr(settings, "wechat_app_secret", "secret")
    monkeypatch.setattr(settings, "auth_signing_secret", "auth-test-secret")
    monkeypatch.setattr(settings, "allow_demo_identity", False)
    legacy = "internal-" + uuid4().hex
    original_client = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda *_, **__: original_client(transport=httpx.MockTransport(
        lambda request: httpx.Response(200, json={"openid": "consent-" + legacy})
    )))
    legacy_headers = {"Authorization": "Bearer " + issue_token(
        {"type": "family", "owner_id": legacy}, "auth-test-secret", 60
    )}
    with TestClient(app) as client:
        assert client.put('/api/v1/profile', headers=legacy_headers, json={
            'student_name': '旧档案', 'junior_school': '示例初中', 'grade': '初三'
        }).status_code == 200
        result = client.post('/api/v1/auth/wechat', json={
            'code': 'test', 'legacy_owner_id': legacy,
            'guardian_consent': True, 'privacy_version': '2026-10-20'
        })
        assert result.status_code == 200
        headers = {'Authorization': 'Bearer ' + result.json()['access_token']}
        assert client.get('/api/v1/profile', headers=headers).json()['student_name'] == ''
        assert client.get('/api/v1/profile', headers=legacy_headers).json()['student_name'] == '旧档案'
