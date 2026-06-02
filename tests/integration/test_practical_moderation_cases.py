from fastapi.testclient import TestClient

from audit.main import create_app


def _client(tmp_path, monkeypatch):
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "audit.db"))
    return TestClient(create_app())


def test_fraud_case_gets_specific_category(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)

    response = client.post("/words", json={"word": "刷单返利", "category": "其他", "level": "违规"})
    assert response.status_code == 201

    audit = client.post("/audit/text", json={"text": "兼职刷单返利，稳赚包赔"})
    assert audit.status_code == 200
    body = audit.json()
    assert body["risk_level"] == "违规"
    assert body["violation_category"] == "诈骗"
    assert any(hit["category"] == "诈骗" for hit in body["hit_details"])


def test_traffic_diversion_case_gets_specific_category(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)

    response = client.post("/words", json={"word": "加微信私聊", "category": "其他", "level": "警告"})
    assert response.status_code == 201

    audit = client.post("/audit/text", json={"text": "想了解更多请加微信私聊"})
    assert audit.status_code == 200
    body = audit.json()
    assert body["risk_level"] in {"警告", "违规"}
    assert body["violation_category"] == "引流"


def test_minor_safety_case_gets_specific_category(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)

    response = client.post("/words", json={"word": "未成年裸聊", "category": "色情", "level": "违规"})
    assert response.status_code == 201

    audit = client.post("/audit/text", json={"text": "传播未成年裸聊内容"})
    assert audit.status_code == 200
    body = audit.json()
    assert body["risk_level"] == "违规"
    assert body["violation_category"] == "未成年人风险"
