from __future__ import annotations

from ..domain.enums import PlatformAction, RiskLevel
from ..domain.models import DisposalSuggestion, FinalDecision, HitDetail
from ..policy.settings import PolicySettings


def build_disposal(decision: FinalDecision, hits: list[HitDetail], policy: PolicySettings | None = None) -> DisposalSuggestion:
    policy = policy or PolicySettings()
    action = _action_for(decision.risk_level, decision.category, policy.high_risk_category_values())
    messages = {
        RiskLevel.COMPLIANT: "内容已通过审核。",
        RiskLevel.HINT: "内容已发布，请遵守社区规范。",
        RiskLevel.WARNING: "内容存在风险，已提交人工复核或部分折叠。",
        RiskLevel.VIOLATION: "内容因违反社区规范已被处置，请修改后重试。",
    }
    category = decision.category or "合规"
    note = f"[{decision.risk_level.value}][{category}] {_explain_hits(hits)}"
    return DisposalSuggestion(platform_action=action, user_message=messages[decision.risk_level], operation_note=note[:500])


def _action_for(risk: RiskLevel, category: str, high_risk_categories: set[str] | None = None) -> PlatformAction:
    high_risk_categories = high_risk_categories or PolicySettings().high_risk_category_values()
    if risk in {RiskLevel.COMPLIANT, RiskLevel.HINT}:
        return PlatformAction.PASS
    if risk == RiskLevel.WARNING:
        return PlatformAction.MANUAL_REVIEW if category in high_risk_categories else PlatformAction.FOLD
    return PlatformAction.BLOCK if category in high_risk_categories else PlatformAction.DELETE


def _explain_hits(hits: list[HitDetail]) -> str:
    visible_hits = [hit for hit in hits if hit.matched_word or hit.flags]
    if not visible_hits:
        return "无显性命中"
    parts = []
    for hit in visible_hits[:5]:
        word = hit.matched_word or hit.original_fragment or "无显性词"
        flags = f", flags={','.join(hit.flags)}" if hit.flags else ""
        parts.append(f"{hit.layer}/{hit.engine}/{hit.category.value}/{hit.level.value}:{word}{flags}")
    if len(visible_hits) > 5:
        parts.append(f"另有{len(visible_hits) - 5}条命中")
    return "命中明细：" + "；".join(parts)
