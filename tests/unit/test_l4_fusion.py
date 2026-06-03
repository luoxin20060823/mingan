from audit.domain.enums import RiskLevel, ViolationCategory
from audit.domain.models import HitDetail, L3Result, LayerResult
from audit.policy.settings import PolicySettings, RiskThresholds
from audit.pipeline.l4_fusion import fuse


def _hit(layer, category, level, flags=None):
    return HitDetail(
        layer=layer,
        engine="test",
        matched_word="词",
        original_fragment="词",
        start=0,
        end=1,
        category=category,
        level=level,
        flags=flags or [],
    )


def test_l4_maps_max_score_to_risk_level_and_category():
    decision = fuse(
        LayerResult(score=0.0, hits=[], elapsed_ms=1),
        LayerResult(score=0.6, hits=[_hit("L2", ViolationCategory.ABUSE, RiskLevel.WARNING)], elapsed_ms=1),
        L3Result(score=0.0, hits=[], elapsed_ms=1),
    )
    assert decision.risk_level == RiskLevel.WARNING
    assert decision.category == "辱骂"


def test_l4_l3_error_limits_confidence_and_marks_unavailable():
    decision = fuse(
        LayerResult(score=0.9, hits=[_hit("L1", ViolationCategory.OTHER, RiskLevel.VIOLATION)], elapsed_ms=1),
        LayerResult(score=0.0, hits=[], elapsed_ms=1),
        L3Result(score=0.0, hits=[], elapsed_ms=1, error="timeout"),
    )
    assert decision.confidence_score <= 0.7
    assert decision.l3_available is False


def test_l4_prefers_specific_category_over_other_at_same_score():
    decision = fuse(
        LayerResult(
            score=0.5,
            hits=[
                _hit("L1", ViolationCategory.OTHER, RiskLevel.WARNING),
                _hit("L1", ViolationCategory.TRAFFIC_DIVERSION, RiskLevel.WARNING),
            ],
            elapsed_ms=1,
        ),
        LayerResult(score=0.0, hits=[], elapsed_ms=1),
        L3Result(score=0.0, hits=[], elapsed_ms=1),
    )
    assert decision.category == "引流"


def test_l4_uses_configured_risk_thresholds():
    decision = fuse(
        LayerResult(score=0.75, hits=[_hit("L1", ViolationCategory.OTHER, RiskLevel.WARNING)], elapsed_ms=1),
        LayerResult(score=0.0, hits=[], elapsed_ms=1),
        L3Result(score=0.0, hits=[], elapsed_ms=1),
        PolicySettings(risk_thresholds=RiskThresholds(hint=0.1, warning=0.4, violation=0.7)),
    )
    assert decision.risk_level == RiskLevel.VIOLATION


def test_l4_prefers_l3_specific_category_when_semantic_risk_is_high():
    decision = fuse(
        LayerResult(score=0.9, hits=[_hit("L1", ViolationCategory.ILLEGAL_AD, RiskLevel.VIOLATION)], elapsed_ms=1),
        LayerResult(score=0.0, hits=[], elapsed_ms=1),
        L3Result(
            score=0.95,
            hits=[_hit("L3", ViolationCategory.FRAUD, RiskLevel.VIOLATION)],
            risk_level=RiskLevel.VIOLATION,
            category=ViolationCategory.FRAUD,
            elapsed_ms=1,
        ),
    )

    assert decision.category == "诈骗"


def test_l4_downgrades_other_only_variant_hits_when_l3_is_compliant():
    decision = fuse(
        LayerResult(score=0.5, hits=[_hit("L1", ViolationCategory.ILLEGAL_AD, RiskLevel.WARNING)], elapsed_ms=1),
        LayerResult(score=0.9, hits=[_hit("L2", ViolationCategory.OTHER, RiskLevel.WARNING)], elapsed_ms=1),
        L3Result(score=0.0, hits=[], risk_level=RiskLevel.COMPLIANT, elapsed_ms=1),
    )

    assert decision.risk_level == RiskLevel.WARNING


def test_l4_downgrades_low_confidence_generic_l1_hits_when_l3_is_compliant():
    decision = fuse(
        LayerResult(
            score=0.5,
            hits=[_hit("L1", ViolationCategory.ILLEGAL_AD, RiskLevel.WARNING, ["low_confidence_generic"])],
            elapsed_ms=1,
        ),
        LayerResult(score=0.2, hits=[], elapsed_ms=1),
        L3Result(score=0.0, hits=[], risk_level=RiskLevel.COMPLIANT, elapsed_ms=1),
    )

    assert decision.risk_level in {RiskLevel.COMPLIANT, RiskLevel.HINT}
