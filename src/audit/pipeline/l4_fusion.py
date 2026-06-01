from __future__ import annotations

from ..domain.enums import RiskLevel, ViolationCategory
from ..domain.models import FinalDecision, L3Result, LayerResult


def fuse(l1: LayerResult, l2: LayerResult, l3: L3Result) -> FinalDecision:
    max_score = max(l1.score, l2.score, l3.score)
    risk = _risk_from_score(max_score)
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


def _risk_from_score(score: float) -> RiskLevel:
    if score >= 0.85:
        return RiskLevel.VIOLATION
    if score >= 0.5:
        return RiskLevel.WARNING
    if score >= 0.2:
        return RiskLevel.HINT
    return RiskLevel.COMPLIANT


def _winning_category(l1: LayerResult, l2: LayerResult, l3: L3Result) -> str:
    candidates = [
        (l3.score, _category_from_l3(l3)),
        (l2.score, _category_from_hits(l2)),
        (l1.score, _category_from_hits(l1)),
    ]
    return max(candidates, key=lambda item: item[0])[1] or ViolationCategory.OTHER.value


def _category_from_l3(l3: L3Result) -> str:
    if l3.category:
        return l3.category.value
    return _category_from_hits(l3)


def _category_from_hits(result: LayerResult) -> str:
    return result.hits[0].category.value if result.hits else ""
