from __future__ import annotations

from ..domain.enums import RiskLevel, ViolationCategory


GENERIC_TERMS = {
    "兼职",
    "招聘",
    "网络",
    "客服",
    "本店",
    "淘宝",
    "代购",
    "到货",
    "有意者",
    "QQ",
    "qq",
}

LOW_QUALITY_TERMS = {
    "完成",
    "价格",
    "可验",
    "口暴",
    "信息",
    "一个",
}

ESCALATION_CONTEXT = {
    ViolationCategory.ILLEGAL_AD: ("刷单", "返利", "博彩", "贷款", "套现", "私聊", "加微信", "进群", "包赔", "稳赚"),
    ViolationCategory.FRAUD: ("转账", "垫付", "返利", "保证金", "验证码", "银行卡", "跑分", "资金盘"),
    ViolationCategory.TRAFFIC_DIVERSION: ("私聊", "加微信", "加v", "加V", "进群", "联系方式", "二维码"),
}


def is_low_quality_seed_term(word: str, category: ViolationCategory) -> bool:
    normalized = word.strip()
    if not normalized:
        return True
    if len(normalized) <= 1:
        return True
    if normalized in LOW_QUALITY_TERMS:
        return True
    if normalized in GENERIC_TERMS:
        return False
    if category in {ViolationCategory.POLITICS, ViolationCategory.ILLEGAL_AD} and len(normalized) <= 2:
        return True
    if category == ViolationCategory.OTHER and len(normalized) <= 2 and normalized.isascii():
        return True
    return False


def adjust_hit_confidence(word: str, category: ViolationCategory, level: RiskLevel, text: str) -> tuple[RiskLevel, list[str]]:
    if word not in GENERIC_TERMS:
        return level, []
    context = ESCALATION_CONTEXT.get(category, ())
    if any(token in text for token in context):
        return level, ["generic_with_risk_context"]
    if level == RiskLevel.VIOLATION:
        return RiskLevel.HINT, ["low_confidence_generic"]
    if level == RiskLevel.WARNING:
        return RiskLevel.HINT, ["low_confidence_generic"]
    return level, ["low_confidence_generic"]


def is_local_technical_url(fragment: str) -> bool:
    lowered = fragment.lower()
    return any(
        token in lowered
        for token in (
            "127.0.0.1",
            "localhost",
            "0.0.0.0",
            "[::1]",
            "file://",
        )
    )


def is_common_benign_term(word: str) -> bool:
    return word.strip() in LOW_QUALITY_TERMS
