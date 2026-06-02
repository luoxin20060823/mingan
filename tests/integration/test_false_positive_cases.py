from fastapi.testclient import TestClient

from audit.main import create_app


def _client(tmp_path, monkeypatch):
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "audit.db"))
    return TestClient(create_app())


def test_normal_recruitment_text_is_not_blocked_by_generic_term(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)

    response = client.post("/audit/text", json={"text": "我们正在招聘后端工程师，欢迎投递简历。"})

    assert response.status_code == 200
    body = response.json()
    assert body["risk_level"] in {"合规", "提示"}
    assert body["disposal_suggestion"]["platform_action"] == "pass"
    assert any("low_confidence_generic" in hit["flags"] for hit in body["hit_details"])


def test_risky_part_time_scam_context_still_blocks(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)

    response = client.post("/audit/text", json={"text": "兼职刷单返利稳赚，先垫付后提现。"})

    assert response.status_code == 200
    body = response.json()
    assert body["risk_level"] == "违规"
    assert body["disposal_suggestion"]["platform_action"] in {"delete", "block"}
