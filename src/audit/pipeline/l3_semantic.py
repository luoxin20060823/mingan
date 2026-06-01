from __future__ import annotations

import json
import time

import httpx

from ..domain.enums import RiskLevel, ViolationCategory
from ..domain.models import HitDetail, L3Result
from ..settings import Settings


class L3SemanticEngine:
    def __init__(self, settings: Settings | None = None, client: httpx.AsyncClient | None = None):
        self.settings = settings or Settings()
        self.client = client

    async def classify(self, text: str) -> L3Result:
        start = time.perf_counter()
        if not self.settings.deepseek_api_key:
            return self._error_result(text, start, "missing_api_key")
        try:
            data = await self._request(text)
            risk = RiskLevel(data["risk_level"])
            raw_category = data["category"]
            category = None if raw_category == RiskLevel.COMPLIANT.value else ViolationCategory(raw_category)
            score = max(0.0, min(1.0, float(data["score"])))
            reason = str(data["reason"])
            hits: list[HitDetail] = []
            if risk != RiskLevel.COMPLIANT:
                hits.append(
                    HitDetail(
                        layer="L3",
                        engine="llm",
                        matched_word=text[:50],
                        original_fragment=text,
                        start=0,
                        end=len(text),
                        category=category or ViolationCategory.OTHER,
                        level=risk,
                    )
                )
            return L3Result(
                score=score,
                hits=hits,
                risk_level=risk,
                category=category,
                explanation=reason[:1000] + ("..." if len(reason) > 1000 else ""),
                elapsed_ms=self._elapsed(start),
            )
        except Exception as exc:
            return self._error_result(text, start, f"{type(exc).__name__}: {str(exc)[:200]}")

    async def _request(self, text: str) -> dict:
        payload = {
            "model": self.settings.deepseek_model,
            "messages": [
                {"role": "system", "content": "你是中文内容安全审核员。请仅输出 JSON。"},
                {"role": "user", "content": text},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.0,
        }
        headers = {"Authorization": f"Bearer {self.settings.deepseek_api_key}"}
        url = f"{self.settings.deepseek_base_url}/chat/completions"
        if self.client:
            response = await self.client.post(url, headers=headers, json=payload)
        else:
            timeout = httpx.Timeout(connect=2, read=self.settings.deepseek_timeout_seconds, write=2, pool=2)
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        data = json.loads(content)
        for field in ("risk_level", "category", "reason", "score"):
            if field not in data:
                raise ValueError(f"missing {field}")
        return data

    def _error_result(self, text: str, start: float, error: str) -> L3Result:
        hit = HitDetail(
            layer="L3",
            engine="llm",
            matched_word="",
            original_fragment=text[:50],
            start=0,
            end=0,
            category=ViolationCategory.OTHER,
            level=RiskLevel.WARNING,
            flags=["l3_error"],
        )
        return L3Result(
            score=0.0,
            hits=[hit],
            risk_level=None,
            category=None,
            explanation=f"L3 错误：{error}",
            error=error,
            elapsed_ms=self._elapsed(start),
        )

    @staticmethod
    def _elapsed(start: float) -> int:
        return max(0, int((time.perf_counter() - start) * 1000))
