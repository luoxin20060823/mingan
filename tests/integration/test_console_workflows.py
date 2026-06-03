from fastapi.testclient import TestClient

from audit.main import create_app


def _client(tmp_path, monkeypatch):
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "audit.db"))
    monkeypatch.setenv("DEEPSEEK_API_KEY", "")
    return TestClient(create_app())


def test_console_workflows_exercise_audit_history_words_rules_and_policy(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)

    single = client.post("/audit/text", json={"text": "我们正在招聘审核运营，欢迎投递简历。"})
    assert single.status_code == 200
    assert single.json()["disposal_suggestion"]["platform_action"] == "pass"

    batch = client.post("/audit/batch", json={"texts": ["正常社区讨论", "扫描二维码进群领取福利"]})
    assert batch.status_code == 200
    assert len(batch.json()["results"]) == 2
    assert batch.json()["results"][1]["violation_category"] == "引流"

    history = client.get("/history", params={"page_size": 10})
    assert history.status_code == 200
    assert history.json()["total"] == 3

    word = client.post("/words", json={"word": "控制台测试词", "category": "辱骂", "level": "警告"})
    assert word.status_code == 201
    word_id = word.json()["id"]
    words = client.get("/words", params={"category": "辱骂", "level": "警告", "page_size": 100})
    assert words.status_code == 200
    assert any(item["word"] == "控制台测试词" for item in words.json()["items"])
    word_audit = client.post("/audit/text", json={"text": "这里包含控制台测试词"})
    assert word_audit.status_code == 200
    assert any(hit["matched_word"] == "控制台测试词" for hit in word_audit.json()["hit_details"])

    rule = client.post(
        "/rules",
        json={"name": "console_invite", "pattern": "暗号[:：]?[A-Z0-9]{4}", "category": "引流", "level": "警告"},
    )
    assert rule.status_code == 201
    rule_id = rule.json()["id"]
    rules = client.get("/rules", params={"category": "引流", "level": "警告", "page_size": 100})
    assert rules.status_code == 200
    assert any(item["name"] == "console_invite" for item in rules.json()["items"])
    rule_audit = client.post("/audit/text", json={"text": "私聊发送暗号AB12"})
    assert rule_audit.status_code == 200
    assert any(hit["engine"] == "regex:console_invite" for hit in rule_audit.json()["hit_details"])

    policy = client.put(
        "/policy",
        json={
            "risk_thresholds": {"hint": 0.1, "warning": 0.3, "violation": 0.45},
            "high_risk_categories": ["引流"],
        },
    )
    assert policy.status_code == 200
    after_policy = client.post("/audit/text", json={"text": "私聊发送暗号AB12"})
    assert after_policy.status_code == 200
    assert after_policy.json()["risk_level"] == "违规"
    assert after_policy.json()["disposal_suggestion"]["platform_action"] == "block"

    assert client.delete(f"/rules/{rule_id}").status_code == 204
    assert client.delete(f"/words/{word_id}").status_code == 204
