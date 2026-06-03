from fastapi.testclient import TestClient

from audit.main import create_app


def test_health_reports_runtime_readiness(tmp_path, monkeypatch):
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "audit.db"))
    monkeypatch.setenv("DEEPSEEK_API_KEY", "")
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] == "ok"
    assert body["semantic_mode"] == "local_fallback"
    assert body["word_count"] > 0
    assert body["enabled_rule_count"] > 0


def test_health_reports_llm_semantic_mode_when_api_key_is_configured(tmp_path, monkeypatch):
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "audit.db"))
    monkeypatch.setenv("DEEPSEEK_API_KEY", "key")
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["semantic_mode"] == "llm"
