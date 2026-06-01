from fastapi.testclient import TestClient

from audit.main import create_app
from audit.settings import Settings


def _client(tmp_path, monkeypatch):
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "audit.db"))
    return TestClient(create_app())


def test_audit_text_history_and_word_crud(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)

    audit = client.post("/audit/text", json={"text": "这里有坏词"})
    assert audit.status_code == 200
    body = audit.json()
    assert body["risk_level"] == "违规"
    assert body["violation_category"] == "其他"

    history = client.get("/history")
    assert history.status_code == 200
    assert history.json()["total"] >= 1

    created = client.post("/words", json={"word": "测试新增词", "category": "其他", "level": "违规"})
    assert created.status_code == 201
    word_id = created.json()["id"]

    listed = client.get("/words")
    assert listed.status_code == 200
    assert any(item["word"] == "测试新增词" for item in listed.json()["items"])

    deleted = client.delete(f"/words/{word_id}")
    assert deleted.status_code == 204
