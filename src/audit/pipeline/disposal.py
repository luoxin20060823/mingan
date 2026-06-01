from __future__ import annotations

from ..domain.enums import PlatformAction, RiskLevel
from ..domain.models import DisposalSuggestion, FinalDecision, HitDetail


HIGH_RISK_CATEGORIES = {"涉政", "暴恐", "色情"}


def build_disposal(decision: FinalDecision, hits: list[HitDetail]) -> DisposalSuggestion:
    action = _action_for(decision.risk_level, decision.category)
    messages = {
        RiskLevel.COMPLIANT: "内容已通过审核。",
        RiskLevel.HINT: "内容已发布，请遵守社区规范。",
        RiskLevel.WARNING: "内容存在风险，已提交人工复核或部分折叠。",
        RiskLevel.VIOLATION: "内容因违反社区规范已被处置，请修改后重试。",
    }
    keywords = " / ".join(h.matched_word for h in hits if h.matched_word) or "无显性命中"
    category = decision.category or "合规"
    note = f"[{decision.risk_level.value}][{category}] 触发命中：{keywords}"
    return DisposalSuggestion(platform_action=action, user_message=messages[decision.risk_level], operation_note=note[:500])


def _action_for(risk: RiskLevel, category: str) -> PlatformAction:
    if risk in {RiskLevel.COMPLIANT, RiskLevel.HINT}:
        return PlatformAction.PASS
    if risk == RiskLevel.WARNING:
        return PlatformAction.MANUAL_REVIEW if category in HIGH_RISK_CATEGORIES else PlatformAction.FOLD
    return PlatformAction.BLOCK if category in HIGH_RISK_CATEGORIES else PlatformAction.DELETE
