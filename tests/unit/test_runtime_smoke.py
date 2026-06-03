from __future__ import annotations

import json
import os

import pytest
from scripts import runtime_smoke


def test_response_json_parses_object() -> None:
    resp = runtime_smoke.Response(200, '{"status":"ok"}', {})

    assert runtime_smoke.expect_json_object(resp, "health") == {"status": "ok"}


def test_extract_action_accepts_nested_disposal_suggestion() -> None:
    assert (
        runtime_smoke.extract_action({"disposal_suggestion": {"platform_action": "delete"}})
        == "delete"
    )


def test_runtime_smoke_accepts_common_batch_shape(monkeypatch) -> None:
    calls: list[tuple[str, str, object | None]] = []

    def fake_request(base_url: str, method: str, path: str, payload: object | None = None, timeout: float = 20.0):
        calls.append((method, path, payload))
        if path == "/health":
            return runtime_smoke.Response(200, json.dumps({"status": "ok", "semantic_mode": "local"}), {})
        if path == "/static/index.html":
            return runtime_smoke.Response(200, "<html></html>", {})
        if path == "/audit/text":
            return runtime_smoke.Response(
                200,
                json.dumps({"risk_level": "警告", "action": "manual_review"}, ensure_ascii=False),
                {},
            )
        if path == "/audit/batch":
            return runtime_smoke.Response(200, json.dumps({"items": []}), {})
        if path.startswith("/history"):
            return runtime_smoke.Response(200, json.dumps({"items": []}), {})
        if path.startswith("/words"):
            return runtime_smoke.Response(200, json.dumps({"items": []}), {})
        if path.startswith("/rules"):
            return runtime_smoke.Response(200, json.dumps({"items": []}), {})
        if path == "/policy":
            return runtime_smoke.Response(200, json.dumps({"rules": []}), {})
        raise AssertionError(f"unexpected path: {path}")

    monkeypatch.setattr(runtime_smoke, "request", fake_request)

    checks = runtime_smoke.run("http://example.test")

    assert "audit batch ok" in checks
    assert any(path == "/audit/text" for _, path, _ in calls)


@pytest.mark.skipif(not os.getenv("AUDIT_LIVE_BASE_URL"), reason="set AUDIT_LIVE_BASE_URL to run live smoke checks")
def test_runtime_smoke_live_service() -> None:
    checks = runtime_smoke.run(os.environ["AUDIT_LIVE_BASE_URL"])

    assert "console html ok" in checks
    assert "history ok" in checks
