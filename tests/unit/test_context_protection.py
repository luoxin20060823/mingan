from audit.domain.enums import RiskLevel, ViolationCategory
from audit.domain.models import HitDetail, L3Result, LayerResult
from audit.pipeline.l4_fusion import fuse


def _hit(layer: str, category: ViolationCategory, level: RiskLevel, fragment: str):
    return HitDetail(
        layer=layer,
        engine="test",
        matched_word=fragment,
        original_fragment=fragment,
        start=0,
        end=len(fragment),
        category=category,
        level=level,
    )


def test_discussion_context_reduces_non_specific_rule_warnings_when_l3_is_compliant():
    l1 = LayerResult(
        score=0.6,
        hits=[_hit("L1", ViolationCategory.OTHER, RiskLevel.WARNING, "讨论性别议题")],
        elapsed_ms=1,
    )
    l2 = LayerResult(score=0.0, hits=[], elapsed_ms=1)
    l3 = L3Result(score=0.0, hits=[], risk_level=RiskLevel.COMPLIANT, elapsed_ms=1)

    decision = fuse(l1, l2, l3)

    assert decision.risk_level in {RiskLevel.COMPLIANT, RiskLevel.HINT}


def test_discussion_context_does_not_reduce_specific_violation_when_l3_is_compliant():
    l1 = LayerResult(
        score=0.85,
        hits=[_hit("L1", ViolationCategory.FRAUD, RiskLevel.VIOLATION, "保证金返利")],
        elapsed_ms=1,
    )
    l2 = LayerResult(score=0.0, hits=[], elapsed_ms=1)
    l3 = L3Result(score=0.0, hits=[], risk_level=RiskLevel.COMPLIANT, elapsed_ms=1)

    decision = fuse(l1, l2, l3)

    assert decision.risk_level == RiskLevel.VIOLATION
