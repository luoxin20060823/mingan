import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from audit.main import create_app


RISK_ORDER = {"合规": 0, "提示": 1, "警告": 2, "违规": 3}
CASEBOOK = Path("tests/fixtures/moderation_cases.jsonl")


def _cases():
    return [json.loads(line) for line in CASEBOOK.read_text(encoding="utf-8").splitlines() if line.strip()]


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "audit.db"))
    monkeypatch.setenv("DEEPSEEK_API_KEY", "")
    return TestClient(create_app())


@pytest.mark.parametrize("case", _cases(), ids=lambda item: item["id"])
def test_moderation_casebook(client, case):
    for word in case.get("custom_words", []):
        response = client.post("/words", json=word)
        assert response.status_code in {201, 409}

    response = client.post("/audit/text", json={"text": case["text"]})

    assert response.status_code == 200
    body = response.json()
    hits = body["hit_details"]

    if "min_risk" in case:
        assert RISK_ORDER[body["risk_level"]] >= RISK_ORDER[case["min_risk"]]
    if "max_risk" in case:
        assert RISK_ORDER[body["risk_level"]] <= RISK_ORDER[case["max_risk"]]
    if "expected_category" in case:
        assert body["violation_category"] == case["expected_category"]
    if "expected_action" in case:
        assert body["disposal_suggestion"]["platform_action"] == case["expected_action"]
    if "expected_action_any" in case:
        assert body["disposal_suggestion"]["platform_action"] in case["expected_action_any"]
    if "must_have_flag" in case:
        assert any(case["must_have_flag"] in hit["flags"] for hit in hits)
    if "must_have_engine" in case:
        assert any(hit["engine"] == case["must_have_engine"] for hit in hits)
