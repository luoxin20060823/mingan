from audit.domain.enums import RiskLevel, ViolationCategory
from audit.domain.models import HitDetail, L3Result, LayerResult
from audit.policy.settings import PolicySettings, RiskThresholds
from audit.pipeline.l4_fusion import fuse


def _hit(layer, category, level):
    return HitDetail(
        layer=layer,
        engine="test",
        matched_word="词",
        original_fragment="词",
        start=0,
        end=1,
        category=category,
        level=level,
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
