from __future__ import annotations

import json
import time

import httpx

from ..domain.enums import RiskLevel, ViolationCategory
from ..domain.models import HitDetail, L3Result
from ..settings import Settings

ALLOWED_RISK_LEVELS = tuple(level.value for level in RiskLevel)
ALLOWED_CATEGORIES = tuple(category.value for category in ViolationCategory)

SYSTEM_PROMPT = """你是中文内容安全审核员，负责补充规则引擎无法稳定识别的语义风险。
请按通用内容平台审核逻辑判断整段文本，不要因为单个普通词语就判违规。
只输出 JSON，不要输出 Markdown、解释性前缀或多余文本。"""

PROTECTIVE_CONTEXT = ("反诈", "提醒", "不要相信", "不要提供", "警惕", "防范", "举报", "案例分析", "科普")

LOCAL_SEMANTIC_RULES = (
    {
        "category": ViolationCategory.MINOR_SAFETY,
        "risk": RiskLevel.VIOLATION,
        "score": 0.92,
        "signals": (
            ("未成年", "未成年人", "未满", "幼女", "儿童", "学生妹", "萝莉"),
            ("裸照", "裸聊", "开房", "性", "诱导", "私密照", "约炮"),
        ),
        "reason": "本地语义兜底：未成年人相关词与性/诱导风险同现。",
    },
    {
        "category": ViolationCategory.FRAUD,
        "risk": RiskLevel.VIOLATION,
        "score": 0.88,
        "signals": (
            ("刷单", "返利", "提现", "保证金", "垫付", "稳赚", "包赔", "验证码", "银行卡"),
            ("先交", "转账", "缴纳", "付款", "返现", "任务", "客服", "群"),
        ),
        "reason": "本地语义兜底：资金/返利/验证码等诈骗信号组合出现。",
    },
    {
        "category": ViolationCategory.TRAFFIC_DIVERSION,
        "risk": RiskLevel.WARNING,
        "score": 0.62,
        "signals": (
            ("私聊", "加微信", "加v", "加V", "二维码", "进群", "电报", "Telegram", "tg", "TG"),
            ("联系", "领取", "福利", "资料", "详情", "咨询", "交易"),
        ),
        "reason": "本地语义兜底：站外联系或进群引流信号组合出现。",
    },
    {
        "category": ViolationCategory.ILLEGAL_AD,
        "risk": RiskLevel.WARNING,
        "score": 0.72,
        "signals": (
            ("包赢", "博彩", "盘口", "娱乐城", "返388", "送100", "下注", "邀请码"),
            ("私信", "联系", "添加", "领取", "扶持", "开业", "平台", "企鹅", "旺旺"),
        ),
        "reason": "本地语义兜底：博彩返利、邀请码或平台推广信号组合出现。",
    },
    {
        "category": ViolationCategory.ILLEGAL_AD,
        "risk": RiskLevel.WARNING,
        "score": 0.68,
        "signals": (
            ("抄小说", "发图文", "小红书", "发布员", "代发", "兼职"),
            ("赚r", "赚钱", "一单一结", "现结", "感兴趣", "了解一下", "吗"),
        ),
        "reason": "本地语义兜底：黑产任务、代发或异常兼职广告信号组合出现。",
    },
)


def build_l3_messages(text: str) -> list[dict[str, str]]:
    risk_levels = "、".join(ALLOWED_RISK_LEVELS)
    categories = "、".join(ALLOWED_CATEGORIES)
    user_prompt = f"""请审核以下中文内容，并严格返回一个 JSON 对象。

可选 risk_level：{risk_levels}
可选 category：{categories}。当 risk_level 为“合规”时，category 必须为空字符串。

JSON 字段必须完整：
{{
  "risk_level": "合规|提示|警告|违规",
  "category": "涉政|暴恐|色情|辱骂|违法广告|诈骗|引流|未成年人风险|低俗|其他 或 空字符串",
  "reason": "用一句话说明主要依据，避免泄露绕过方法",
  "score": 0.0
}}

审核原则：
- 明显诈骗、诱导私下交易、保证金返利、钓鱼链接、仿冒客服，优先归为“诈骗”。
- 诱导加群、私聊、外部平台联系、规避平台交易，优先归为“引流”。
- 涉及未成年人性暗示、诱导、伤害或不当接触，优先归为“未成年人风险”。
- 粗俗擦边但未达到色情或辱骂强度，可归为“低俗”。
- 正常招聘、兼职信息、新闻报道、科普教育、合规商品说明、风险提示和反诈宣传，不应仅因出现敏感词而判违规。
- 无法确定时使用较低风险等级，并在 reason 中说明不确定性。

待审核文本：
<<<
{text}
>>>"""
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]


class L3SemanticEngine:
    def __init__(self, settings: Settings | None = None, client: httpx.AsyncClient | None = None):
        self.settings = settings or Settings()
        self.client = client

    async def classify(self, text: str) -> L3Result:
        start = time.perf_counter()
        if not self.settings.deepseek_api_key:
            return self._local_fallback_result(text, start)
        try:
            local_result = self._local_fallback_result(text, start)
            data = await self._request(text)
            risk, category, score, reason = self._parse_response_data(data)
            if risk == RiskLevel.COMPLIANT and local_result.risk_level in {RiskLevel.WARNING, RiskLevel.VIOLATION}:
                return local_result
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
            "messages": build_l3_messages(text),
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

    @staticmethod
    def _parse_response_data(data: dict) -> tuple[RiskLevel, ViolationCategory | None, float, str]:
        risk = _parse_risk_level(data["risk_level"])
        category = _parse_category(data["category"], risk)
        score = _parse_score(data["score"])
        reason = str(data["reason"]).strip()
        if not reason:
            raise ValueError("missing reason")
        return risk, category, score, reason

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

    def _local_fallback_result(self, text: str, start: float) -> L3Result:
        normalized = text.casefold()
        if _has_protective_context(normalized):
            return L3Result(
                score=0.0,
                hits=[],
                risk_level=RiskLevel.COMPLIANT,
                category=None,
                explanation="本地语义兜底：检测到反诈、提醒或科普语境，未触发语义风险。",
                elapsed_ms=self._elapsed(start),
            )

        for rule in LOCAL_SEMANTIC_RULES:
            matched = _matched_signal_groups(normalized, rule["signals"])
            if len(matched) != len(rule["signals"]):
                continue
            category = rule["category"]
            risk = rule["risk"]
            hit = HitDetail(
                layer="L3",
                engine="local_semantic",
                matched_word=",".join(matched)[:50],
                original_fragment=text[:200],
                start=0,
                end=min(len(text), 200),
                category=category,
                level=risk,
                flags=["local_fallback"],
            )
            return L3Result(
                score=rule["score"],
                hits=[hit],
                risk_level=risk,
                category=category,
                explanation=rule["reason"],
                elapsed_ms=self._elapsed(start),
            )

        return L3Result(
            score=0.0,
            hits=[],
            risk_level=RiskLevel.COMPLIANT,
            category=None,
            explanation="本地语义兜底：未发现明确语义风险。",
            elapsed_ms=self._elapsed(start),
        )

    @staticmethod
    def _elapsed(start: float) -> int:
        return max(0, int((time.perf_counter() - start) * 1000))


def _parse_risk_level(value: object) -> RiskLevel:
    try:
        return RiskLevel(str(value).strip())
    except ValueError as exc:
        raise ValueError(f"invalid risk_level: {value}") from exc


def _parse_category(value: object, risk: RiskLevel) -> ViolationCategory | None:
    raw_category = str(value).strip()
    if risk == RiskLevel.COMPLIANT:
        return None
    if not raw_category:
        raise ValueError("invalid category: empty for non-compliant risk")
    try:
        return ViolationCategory(raw_category)
    except ValueError as exc:
        raise ValueError(f"invalid category: {raw_category}") from exc


def _parse_score(value: object) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid score: {value}") from exc


def _has_protective_context(text: str) -> bool:
    return any(token.casefold() in text for token in PROTECTIVE_CONTEXT)


def _matched_signal_groups(text: str, groups: tuple[tuple[str, ...], ...]) -> list[str]:
    matched: list[str] = []
    for group in groups:
        token = next((candidate for candidate in group if candidate.casefold() in text), "")
        if token:
            matched.append(token)
    return matched
