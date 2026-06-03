"""Runtime smoke checks for the moderation API.

Run this after starting the service, for example:

    python scripts/runtime_smoke.py --base-url http://127.0.0.1:8010

The script intentionally uses only the Python standard library so it works in
fresh local environments without installing extra tooling.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any


@dataclass
class Response:
    status: int
    body: str
    headers: dict[str, str]

    def json(self) -> Any:
        return json.loads(self.body)


def request(
    base_url: str,
    method: str,
    path: str,
    payload: Any | None = None,
    timeout: float = 20.0,
) -> Response:
    url = urllib.parse.urljoin(base_url.rstrip("/") + "/", path.lstrip("/"))
    url_parts = urllib.parse.urlsplit(url)
    if url_parts.query:
        query = urllib.parse.quote(url_parts.query, safe="=&")
        url = urllib.parse.urlunsplit(
            (url_parts.scheme, url_parts.netloc, url_parts.path, query, url_parts.fragment)
        )
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json; charset=utf-8"

    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return Response(resp.status, body, dict(resp.headers.items()))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return Response(exc.code, body, dict(exc.headers.items()))


def expect_status(resp: Response, expected: int, label: str) -> None:
    if resp.status != expected:
        raise AssertionError(f"{label}: expected HTTP {expected}, got {resp.status}: {resp.body[:500]}")


def expect_json_object(resp: Response, label: str) -> dict[str, Any]:
    try:
        data = resp.json()
    except json.JSONDecodeError as exc:
        raise AssertionError(f"{label}: response is not JSON: {resp.body[:500]}") from exc
    if not isinstance(data, dict):
        raise AssertionError(f"{label}: expected JSON object, got {type(data).__name__}")
    return data


def first_present(data: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = data.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def extract_action(data: dict[str, Any]) -> str | None:
    action = first_present(data, ("action", "disposal", "suggestion"))
    if action:
        return action

    disposal_suggestion = data.get("disposal_suggestion")
    if isinstance(disposal_suggestion, dict):
        platform_action = disposal_suggestion.get("platform_action")
        if isinstance(platform_action, str) and platform_action:
            return platform_action
    return None


def run(base_url: str) -> list[str]:
    checks: list[str] = []

    health = request(base_url, "GET", "/health")
    expect_status(health, 200, "health")
    health_data = expect_json_object(health, "health")
    if health_data.get("status") not in {"ok", "healthy"}:
        raise AssertionError(f"health: unexpected status payload: {health_data}")
    checks.append(f"health ok ({health_data.get('semantic_mode', 'unknown semantic mode')})")

    index = request(base_url, "GET", "/static/index.html")
    expect_status(index, 200, "static console")
    if "<html" not in index.body.lower():
        raise AssertionError("static console: response does not look like HTML")
    checks.append("console html ok")

    audit = request(
        base_url,
        "POST",
        "/audit/text",
        {"text": "先交保证金，完成刷单任务后返利提现。"},
    )
    expect_status(audit, 200, "audit text")
    audit_data = expect_json_object(audit, "audit text")
    risk_level = first_present(audit_data, ("risk_level", "risk", "level"))
    action = extract_action(audit_data)
    if not risk_level:
        raise AssertionError(f"audit text: missing risk level in response: {audit_data}")
    if not action:
        raise AssertionError(f"audit text: missing action in response: {audit_data}")
    checks.append(f"audit text ok ({risk_level}, {action})")

    batch_payloads = (
        {"texts": ["今天正常讨论一下作业安排。", "加我VX领内部返利项目。"]},
        {
            "items": [
                {"id": "normal-1", "text": "今天正常讨论一下作业安排。"},
                {"id": "risk-1", "text": "加我VX领内部返利项目。"},
            ]
        },
    )
    batch_error = None
    for payload in batch_payloads:
        batch = request(base_url, "POST", "/audit/batch", payload)
        if batch.status == 200:
            expect_json_object(batch, "audit batch")
            checks.append("audit batch ok")
            break
        batch_error = batch
    else:
        assert batch_error is not None
        raise AssertionError(f"audit batch: no supported payload shape worked: {batch_error.body[:500]}")

    history = request(base_url, "GET", "/history?page_size=5")
    expect_status(history, 200, "history")
    expect_json_object(history, "history")
    checks.append("history ok")

    for label, path in (
        ("words", "/words?q=诈骗&page_size=5"),
        ("rules", "/rules?q=VX&page_size=5"),
        ("policy", "/policy"),
    ):
        resp = request(base_url, "GET", path)
        expect_status(resp, 200, label)
        expect_json_object(resp, label)
        checks.append(f"{label} ok")

    return checks


def main() -> int:
    parser = argparse.ArgumentParser(description="Run runtime smoke checks against a running audit API.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8010")
    args = parser.parse_args()

    try:
        checks = run(args.base_url)
    except Exception as exc:
        print(f"runtime smoke failed: {exc}", file=sys.stderr)
        return 1

    print("runtime smoke passed")
    for check in checks:
        print(f"- {check}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
