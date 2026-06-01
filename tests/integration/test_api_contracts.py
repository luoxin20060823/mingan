from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from audit.main import create_app
from audit.repository.audit_repo import AuditRepository


def _client(tmp_path, monkeypatch):
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "audit.db"))
    return TestClient(create_app())


def _insert_record(app, text: str, risk_level: str, category: str, created_at: datetime) -> None:
    AuditRepository(app.state.db).insert_record(
        text=text,
        risk_level=risk_level,
        violation_category=category,
        confidence_score=0.9,
        l1_score=0.9,
        l2_score=0.0,
        l3_score=0.0,
        hit_details_json="[]",
        llm_explanation="",
        disposal_suggestion_json='{"platform_action":"delete","user_message":"x","operation_note":"x"}',
        processing_time_json='{"l1_ms":0,"l2_ms":0,"l3_ms":0,"total_ms":0}',
        created_at=created_at.isoformat(),
    )


def test_history_filters_by_time_range_and_rejects_reversed_range(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    app = client.app
    old = datetime(2026, 1, 1, tzinfo=timezone.utc)
    new = old + timedelta(days=1)
    _insert_record(app, "旧记录", "违规", "其他", old)
    _insert_record(app, "新记录", "违规", "其他", new)

    response = client.get("/history", params={"start_time": new.isoformat(), "end_time": new.isoformat()})

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["text"] == "新记录"

    bad = client.get("/history", params={"start_time": new.isoformat(), "end_time": old.isoformat()})
    assert bad.status_code == 400


def test_history_rejects_invalid_enum_and_pagination_values(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)

    assert client.get("/history", params={"risk_level": "非法"}).status_code == 400
    assert client.get("/history", params={"category": "非法"}).status_code == 400
    assert client.get("/history", params={"page": 0}).status_code == 400
    assert client.get("/history", params={"page_size": 101}).status_code == 400


def test_words_reject_invalid_filters_and_trim_blank_word(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)

    assert client.get("/words", params={"category": "非法"}).json()["error"]["message"] == "invalid category"
    assert client.get("/words", params={"level": "非法"}).json()["error"]["message"] == "invalid level"
    assert client.get("/words", params={"page": 0}).json()["error"]["message"] == "invalid pagination"
    assert client.get("/words", params={"page_size": 101}).json()["error"]["message"] == "invalid pagination"
    assert client.post("/words", json={"word": "   ", "category": "其他", "level": "违规"}).status_code == 400


def test_words_delete_rejects_builtin_entries(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    listed = client.get("/words?page_size=1").json()
    builtin_id = listed["items"][0]["id"]

    deleted = client.delete(f"/words/{builtin_id}")

    assert deleted.status_code == 400
    assert deleted.json()["error"]["message"] == "builtin words cannot be deleted"
    assert client.get("/words?page_size=1").json()["total"] == listed["total"]


def test_audit_batch_rolls_back_all_records_when_one_insert_fails(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)

    with client.app.state.db.connect() as conn:
        conn.execute(
            """
            CREATE TRIGGER fail_second_batch_insert
            BEFORE INSERT ON audit_records
            WHEN (SELECT COUNT(*) FROM audit_records) = 1
            BEGIN
                SELECT RAISE(ABORT, 'forced failure');
            END;
            """
        )
        conn.commit()

    response = client.post("/audit/batch", json={"texts": ["正常内容1", "正常内容2"]})

    assert response.status_code == 500
    with client.app.state.db.connect() as conn:
        total = conn.execute("SELECT COUNT(*) AS c FROM audit_records").fetchone()["c"]
    assert total == 0


def test_audit_batch_validation_reports_size_and_item_index(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)

    empty = client.post("/audit/batch", json={"texts": []})
    assert empty.status_code == 400
    assert "batch size out of range" in empty.text

    too_many = client.post("/audit/batch", json={"texts": ["正常"] * 51})
    assert too_many.status_code == 400
    assert "batch size out of range" in too_many.text

    too_long = client.post("/audit/batch", json={"texts": ["正常", "长" * 2001]})
    assert too_long.status_code == 400
    assert "index 1" in too_long.text


def test_audit_text_rejects_blank_text_without_persisting(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)

    response = client.post("/audit/text", json={"text": "   "})

    assert response.status_code == 400
    assert "error" in response.json()
    assert client.get("/history").json()["total"] == 0


def test_custom_word_create_delete_takes_effect_for_subsequent_audits(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)

    created = client.post("/words", json={"word": "独有测试词", "category": "其他", "level": "违规"})
    assert created.status_code == 201
    word_id = created.json()["id"]

    hit = client.post("/audit/text", json={"text": "这是一条独有测试词"})
    assert hit.status_code == 200
    assert any(item["matched_word"] == "独有测试词" for item in hit.json()["hit_details"])

    deleted = client.delete(f"/words/{word_id}")
    assert deleted.status_code == 204

    missed = client.post("/audit/text", json={"text": "这是一条独有测试词"})
    assert missed.status_code == 200
    assert not any(item["matched_word"] == "独有测试词" for item in missed.json()["hit_details"])


def test_audit_text_uses_regex_and_variant_seed_resources(tmp_path, monkeypatch):
    seed_path = tmp_path / "sensitive_words.csv"
    seed_path.write_text(
        "word,category,level\n坏词,其他,违规\n"
        + "\n".join(f"补齐词{i},其他,提示" for i in range(999))
        + "\n",
        encoding="utf-8",
    )
    homophone_path = tmp_path / "homophones.json"
    homophone_path.write_text('{"坏": ["壞"]}', encoding="utf-8")
    glyph_path = tmp_path / "glyph.json"
    glyph_path.write_text('{"坏": ["坯"]}', encoding="utf-8")
    regex_path = tmp_path / "regex_rules.yaml"
    regex_path.write_text(
        '- name: phone\n  pattern: "1[3-9]\\\\d{9}"\n  category: "违法广告"\n  level: "警告"\n',
        encoding="utf-8",
    )
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "audit.db"))
    monkeypatch.setenv("SEED_PATH", str(seed_path))
    monkeypatch.setenv("HOMOPHONE_PATH", str(homophone_path))
    monkeypatch.setenv("GLYPH_PATH", str(glyph_path))
    monkeypatch.setenv("REGEX_RULES_PATH", str(regex_path))

    client = TestClient(create_app())

    regex_response = client.post("/audit/text", json={"text": "联系 13800138000"})
    assert regex_response.status_code == 200
    assert any(hit["engine"] == "regex:phone" for hit in regex_response.json()["hit_details"])

    homophone_response = client.post("/audit/text", json={"text": "这里有壞词"})
    assert homophone_response.status_code == 200
    assert any(hit["engine"] == "homophone" for hit in homophone_response.json()["hit_details"])
