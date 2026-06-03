from audit.domain.enums import RiskLevel
from audit.domain.enums import ViolationCategory
from audit.domain.models import FinalDecision, HitDetail
from audit.policy.settings import PolicySettings
from audit.pipeline.disposal import build_disposal


def test_violation_high_risk_category_blocks():
    decision = FinalDecision(risk_level=RiskLevel.VIOLATION, category="涉政", confidence_score=0.9)
    suggestion = build_disposal(decision, [])
    assert suggestion.platform_action.value == "block"
    assert "违规" in suggestion.operation_note


def test_warning_low_risk_category_folds():
    decision = FinalDecision(risk_level=RiskLevel.WARNING, category="辱骂", confidence_score=0.6)
    suggestion = build_disposal(decision, [])
    assert suggestion.platform_action.value == "fold"


def test_hint_risk_gets_hint_action():
    decision = FinalDecision(risk_level=RiskLevel.HINT, category="低俗", confidence_score=0.25)

    suggestion = build_disposal(decision, [])

    assert suggestion.platform_action.value == "hint"


def test_low_confidence_generic_hint_still_passes():
    decision = FinalDecision(risk_level=RiskLevel.HINT, category="违法广告", confidence_score=0.2)
    hit = HitDetail(
        layer="L1",
        engine="ahocorasick",
        matched_word="招聘",
        original_fragment="招聘",
        start=0,
        end=2,
        category=ViolationCategory.ILLEGAL_AD,
        level=RiskLevel.HINT,
        flags=["low_confidence_generic"],
    )

    suggestion = build_disposal(decision, [hit])

    assert suggestion.platform_action.value == "pass"


def test_disposal_note_includes_explainable_hit_details():
    decision = FinalDecision(risk_level=RiskLevel.HINT, category="违法广告", confidence_score=0.2)
    hit = HitDetail(
        layer="L1",
        engine="ahocorasick",
        matched_word="招聘",
        original_fragment="招聘",
        start=0,
        end=2,
        category=ViolationCategory.ILLEGAL_AD,
        level=RiskLevel.HINT,
        flags=["low_confidence_generic"],
    )

    suggestion = build_disposal(decision, [hit])

    assert "L1/ahocorasick/违法广告/提示:招聘" in suggestion.operation_note
    assert "low_confidence_generic" in suggestion.operation_note


def test_disposal_uses_configured_high_risk_categories():
    decision = FinalDecision(risk_level=RiskLevel.VIOLATION, category="诈骗", confidence_score=0.9)
    policy = PolicySettings(high_risk_categories=[ViolationCategory.FRAUD])

    suggestion = build_disposal(decision, [], policy)

    assert suggestion.platform_action.value == "block"
