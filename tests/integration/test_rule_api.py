from fastapi.testclient import TestClient

from audit.main import create_app


def _client(tmp_path, monkeypatch):
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "audit.db"))
    return TestClient(create_app())


def test_builtin_regex_rules_are_imported_and_not_deletable(tmp_path, monkeypatch):
    regex_path = tmp_path / "regex_rules.yaml"
    regex_path.write_text(
        '- name: invite_code\n  pattern: "邀请码[:：]?[A-Z0-9]{6}"\n  category: "引流"\n  level: "警告"\n',
        encoding="utf-8",
    )
    monkeypatch.setenv("REGEX_RULES_PATH", str(regex_path))
    client = _client(tmp_path, monkeypatch)

    listed = client.get("/rules")

    assert listed.status_code == 200
    body = listed.json()
    assert body["total"] == 1
    rule = body["items"][0]
    assert rule["name"] == "invite_code"
    assert rule["source"] == "builtin"
    deleted = client.delete(f"/rules/{rule['id']}")
    assert deleted.status_code == 400


def test_custom_regex_rule_takes_effect_and_can_be_deleted(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)

    created = client.post(
        "/rules",
        json={"name": "invite_code", "pattern": "邀请码[:：]?[A-Z0-9]{6}", "category": "引流", "level": "警告"},
    )
    assert created.status_code == 201
    rule_id = created.json()["id"]

    hit = client.post("/audit/text", json={"text": "请输入邀请码ABC123"})
    assert hit.status_code == 200
    assert any(item["engine"] == "regex:invite_code" for item in hit.json()["hit_details"])

    deleted = client.delete(f"/rules/{rule_id}")
    assert deleted.status_code == 204

    missed = client.post("/audit/text", json={"text": "请输入邀请码ABC123"})
    assert missed.status_code == 200
    assert not any(item["engine"] == "regex:invite_code" for item in missed.json()["hit_details"])


def test_rule_api_supports_keyword_search(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    client.post(
        "/rules",
        json={"name": "special_invite", "pattern": "暗号[:：]?[A-Z0-9]{4}", "category": "引流", "level": "警告"},
    )
    client.post(
        "/rules",
        json={"name": "ordinary_code", "pattern": "普通码[:：]?[A-Z0-9]{4}", "category": "其他", "level": "提示"},
    )

    by_name = client.get("/rules", params={"q": "special", "page_size": 100})
    by_pattern = client.get("/rules", params={"q": "暗号", "page_size": 100})

    assert by_name.status_code == 200
    assert by_name.json()["total"] == 1
    assert by_name.json()["items"][0]["name"] == "special_invite"
    assert by_pattern.status_code == 200
    assert by_pattern.json()["total"] == 1
    assert by_pattern.json()["items"][0]["name"] == "special_invite"


def test_rule_api_rejects_invalid_regex(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)

    response = client.post(
        "/rules",
        json={"name": "bad", "pattern": "[", "category": "其他", "level": "提示"},
    )

    assert response.status_code == 400
