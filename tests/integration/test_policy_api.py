from fastapi.testclient import TestClient

from audit.main import create_app


def _client(tmp_path, monkeypatch):
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "audit.db"))
    return TestClient(create_app())


def test_policy_api_get_and_update(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)

    current = client.get("/policy")
    assert current.status_code == 200
    assert current.json()["risk_thresholds"]["violation"] == 0.85

    updated = client.put(
        "/policy",
        json={
            "risk_thresholds": {"hint": 0.1, "warning": 0.3, "violation": 0.6},
            "high_risk_categories": ["诈骗"],
        },
    )
    assert updated.status_code == 200
    assert updated.json()["risk_thresholds"]["violation"] == 0.6
    assert updated.json()["high_risk_categories"] == ["诈骗"]


def test_policy_thresholds_affect_subsequent_audits(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    client.post("/words", json={"word": "策略测试词", "category": "其他", "level": "警告"})

    before = client.post("/audit/text", json={"text": "这里有策略测试词"})
    assert before.status_code == 200
    assert before.json()["risk_level"] == "警告"

    updated = client.put(
        "/policy",
        json={
            "risk_thresholds": {"hint": 0.1, "warning": 0.3, "violation": 0.45},
            "high_risk_categories": ["暴恐"],
        },
    )
    assert updated.status_code == 200

    after = client.post("/audit/text", json={"text": "这里有策略测试词"})
    assert after.status_code == 200
    assert after.json()["risk_level"] == "违规"


def test_policy_api_rejects_invalid_threshold_order(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)

    response = client.put(
        "/policy",
        json={
            "risk_thresholds": {"hint": 0.5, "warning": 0.3, "violation": 0.6},
            "high_risk_categories": ["暴恐"],
        },
    )

    assert response.status_code == 400
