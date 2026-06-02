from __future__ import annotations

from ..domain.enums import RiskLevel, ViolationCategory
from ..domain.models import FinalDecision, L3Result, LayerResult
from ..policy.settings import PolicySettings

SPECIFIC_CATEGORY_PRIORITY = {
    ViolationCategory.MINOR_SAFETY.value: 90,
    ViolationCategory.FRAUD.value: 85,
    ViolationCategory.TRAFFIC_DIVERSION.value: 75,
    ViolationCategory.TERROR.value: 70,
    ViolationCategory.PORN.value: 65,
    ViolationCategory.POLITICS.value: 60,
    ViolationCategory.ILLEGAL_AD.value: 50,
    ViolationCategory.ABUSE.value: 45,
    ViolationCategory.VULGAR.value: 40,
    ViolationCategory.OTHER.value: 0,
    "": -1,
}


def fuse(l1: LayerResult, l2: LayerResult, l3: L3Result, policy: PolicySettings | None = None) -> FinalDecision:
    policy = policy or PolicySettings()
    max_score = max(l1.score, l2.score, l3.score)
    risk = _risk_from_score(max_score, policy)
    category = "" if risk == RiskLevel.COMPLIANT else _winning_category(l1, l2, l3)
    l1_available = l1.elapsed_ms >= 0
    l2_available = l2.elapsed_ms >= 0
    l3_available = l3.elapsed_ms >= 0 and not l3.error

    confidence = max_score
    if risk == RiskLevel.COMPLIANT:
        confidence = max(0.8, 1.0 - max_score)
    if not (l1_available and l2_available and l3_available):
        confidence = min(confidence, 0.7)

    return FinalDecision(
        risk_level=risk,
        category=category,
        confidence_score=round(confidence, 4),
        l1_score=l1.score,
        l2_score=l2.score,
        l3_score=l3.score,
        l1_hits=l1.hits,
        l2_hits=l2.hits,
        l3_hits=l3.hits,
        l1_available=l1_available,
        l2_available=l2_available,
        l3_available=l3_available,
    )


def _risk_from_score(score: float, policy: PolicySettings | None = None) -> RiskLevel:
    policy = policy or PolicySettings()
    thresholds = policy.risk_thresholds
    if score >= thresholds.violation:
        return RiskLevel.VIOLATION
    if score >= thresholds.warning:
        return RiskLevel.WARNING
    if score >= thresholds.hint:
        return RiskLevel.HINT
    return RiskLevel.COMPLIANT


def _winning_category(l1: LayerResult, l2: LayerResult, l3: L3Result) -> str:
    candidates = [
        *_categories_from_result(l3.score, l3.hits, _category_from_l3(l3)),
        *_categories_from_result(l2.score, l2.hits),
        *_categories_from_result(l1.score, l1.hits),
    ]
    best = max(candidates, key=lambda item: (item[0], item[2]))
    if best[1] == ViolationCategory.OTHER.value:
        specific_candidates = [item for item in candidates if item[2] > SPECIFIC_CATEGORY_PRIORITY[ViolationCategory.OTHER.value]]
        if specific_candidates:
            return max(specific_candidates, key=lambda item: (item[2], item[0]))[1]
    return best[1] or ViolationCategory.OTHER.value


def _categories_from_result(
    score: float, hits, preferred_category: str = ""
) -> list[tuple[float, str, int]]:
    categories = [preferred_category] if preferred_category else []
    categories.extend(hit.category.value for hit in hits)
    if not categories:
        return [(score, "", -1)]
    return [(score, category, SPECIFIC_CATEGORY_PRIORITY.get(category, 0)) for category in categories]


def _category_from_l3(l3: L3Result) -> str:
    if l3.category:
        return l3.category.value
    return _category_from_hits(l3)


def _category_from_hits(result: LayerResult) -> str:
    return result.hits[0].category.value if result.hits else ""
